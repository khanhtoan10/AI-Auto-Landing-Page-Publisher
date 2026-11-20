# Ở đầu file backend/api/projects.py (đã giải quyết conflict Git):
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from models import STATUS_SUCCESS
from schemas.project import ProjectCreate, ProjectUpdate
from services import github_service, template_service
from services.generation_service import ProjectNotFoundError, generate_content_for_project
from services.version_service import create_version

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = logging.getLogger(__name__)


def _error_detail(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message, "details": []}}

DEFAULT_CHANGE_SUMMARY = "Cập nhật landing page: text, giá, link social"


# ── Helpers ──────────────────────────────────────────────────────────
def _json_safe(value: Any) -> Any:
    """Chuyển Decimal/datetime/bytes sang kiểu JSON-serializable."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _parse_raw_json(value: Any) -> Any:
    """raw_json_data có thể là dict hoặc chuỗi JSON tuỳ driver."""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _serialize_project(row: Any) -> dict:
    project = _json_safe(dict(row))
    project["raw_json_data"] = _json_safe(_parse_raw_json(project.get("raw_json_data")))
    return project


def _split_payload(payload: ProjectUpdate) -> tuple[dict, str, str | None]:
    """Tách payload thành (dữ liệu cập nhật DB, change_summary, commit_message)."""
    update_data = payload.model_dump(exclude_unset=True)
    change_summary = (update_data.pop("change_summary", None) or DEFAULT_CHANGE_SUMMARY).strip()
    commit_message = update_data.pop("commit_message", None)

    if "raw_json_data" in update_data and update_data["raw_json_data"] is not None:
        raw_value = update_data["raw_json_data"]
        update_data["raw_json_data"] = (
            raw_value if isinstance(raw_value, str) else json.dumps(raw_value, ensure_ascii=False)
        )

    return update_data, change_summary, commit_message


def _fetch_project(db: Session, project_id: int) -> Any:
    row = (
        db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": project_id})
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Landing page không tồn tại.")
    return row


# ── Endpoints ────────────────────────────────────────────────────────
@router.get("")
async def list_my_projects(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text("SELECT * FROM projects WHERE user_id = :user_id ORDER BY updated_at DESC"),
            {"user_id": current_user["id"]},
        )
        .mappings()
        .all()
    )
    return {"success": True, "data": [_serialize_project(row) for row in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = db.execute(
        text("SELECT id FROM templates WHERE id = :id"), {"id": payload.template_id}
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template khong ton tai")

    result = db.execute(
        text(
            """
            INSERT INTO projects
            (user_id, template_id, campaign_name, product_name, product_description,
             price, image_url, color_theme, messenger_link, tiktok_shop_link, zalo_link, instagram_link, hotline,
             facebook_url, tiktok_url, instagram_url, status)
            VALUES
            (:user_id, :template_id, :campaign_name, :product_name, :product_description,
             :price, :image_url, :color_theme, :messenger_link, :tiktok_shop_link, :zalo_link, :instagram_link, :hotline,
             :facebook_url, :tiktok_url, :instagram_url, 'draft')
            """
        ),
        {**payload.model_dump(), "user_id": current_user["id"]},
    )
    db.commit()

    row = (
        db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": result.lastrowid})
        .mappings()
        .one()
    )
    return {"success": True, "data": _serialize_project(row)}


@router.get("/{project_id}")
async def get_project_detail(
    project: dict = Depends(get_owned_project),
):
    return {"success": True, "data": _serialize_project(project)}


@router.post("/{project_id}/preview")
async def preview_project(
    payload: ProjectUpdate,
    project: dict = Depends(get_owned_project),
):
    """Render xem trước HTML với dữ liệu đang chỉnh sửa, KHÔNG lưu vào database."""
    update_data, _, _ = _split_payload(payload)
    merged = {**project, **update_data}
    merged["raw_json_data"] = _parse_raw_json(merged.get("raw_json_data"))

    rendered_html = template_service.render_landing_page(merged)

    return {
        "success": True,
        "rendered_html": rendered_html,
        "product_name": merged.get("product_name") or "",
        "price": _json_safe(merged.get("price")),
    }


@router.put("/{project_id}")
@router.patch("/{project_id}")
async def update_project(
    payload: ProjectUpdate,
    project: dict = Depends(get_owned_project),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """[BE] API cập nhật landing page.

    1. Cập nhật text / giá / link social / màu sắc / ảnh vào bảng ``projects``.
    2. Render lại toàn bộ HTML qua ``template_service.render_landing_page``.
    3. Push commit mới lên GitHub (fallback SHA mô phỏng khi offline).
    4. Lưu snapshot Append-only vào ``project_versions`` (version_number tự tăng).
    """
    update_data, change_summary, commit_message = _split_payload(payload)

    if not update_data:
        # Không có trường nào thay đổi: vẫn render lại để trả về bản xem trước mới nhất.
        logger.info("Payload rỗng cho project %s, chỉ render lại HTML", project["id"])

    if "template_id" in update_data and update_data["template_id"] is not None:
        template = db.execute(
            text("SELECT id FROM templates WHERE id = :id"),
            {"id": update_data["template_id"]},
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template khong ton tai")

    if update_data:
        set_clauses = ", ".join(f"{col} = :{col}" for col in update_data.keys())
        db.execute(
            text(
                f"UPDATE projects SET {set_clauses}, updated_at = NOW() WHERE id = :id"
            ),
            {**update_data, "id": project["id"]},
        )
        db.commit()

    row = _fetch_project(db, project["id"])
    project_dict = _serialize_project(row)

    rendered_html = template_service.render_landing_page(project_dict)

    warnings: list[str] = []
    repo_url = project_dict.get("repo_url")

    commit_sha = None
    try:
        commit_sha = github_service.push_landing_page_commit(
            repo_url=repo_url,
            html_content=rendered_html,
            commit_message=commit_message
            or f"Cập nhật landing page: {project_dict.get('campaign_name') or project_dict.get('product_name')}",
            file_path="index.html",
        )
    except Exception as exc:  # pragma: no cover - lỗi mạng/hạ tầng
        logger.exception("Push GitHub thất bại cho project %s", project["id"])
        warnings.append(f"Không push được commit GitHub: {exc}")

    version: dict | None = None
    try:
        version = create_version(
            project_id=project_dict["id"],
            html_snapshot=rendered_html,
            json_content=_json_safe(project_dict),
            commit_sha=commit_sha,
            change_summary=change_summary,
            created_by=current_user.get("id") if current_user else None,
        )
    except Exception as exc:  # pragma: no cover - lỗi DB phiên bản
        logger.exception("Không lưu được version cho project %s", project["id"])
        warnings.append(f"Không lưu được phiên bản mới: {exc}")

    version_number = version.get("version_number") if version else None
    version_id = version.get("id") if version else None

    if version_number is not None:
        message = f"Cập nhật landing page thành công! Đã tạo phiên bản v{version_number}."
    else:
        message = "Cập nhật landing page thành công!"

    return {
        "success": True,
        "message": message,
        "data": project_dict,
        "project": project_dict,
        "commit_sha": commit_sha,
        "version_id": version_id,
        "version_number": version_number,
        "rendered_html": rendered_html,
        "github_pages_url": project_dict.get("github_pages_url"),
        "repo_url": repo_url,
        "warnings": warnings,
    }


@router.delete("/{project_id}")
async def delete_project(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project["id"]})
    db.commit()
    return {"success": True, "message": "Đã xóa landing page thành công."}


@router.post("/{project_id}/deploy")
async def deploy_project_guard(
    project: dict = Depends(get_owned_project),
):
    """
    Endpoint deploy đã được khóa bằng get_owned_project (chỉ chủ sở hữu mới được deploy).
    Sẽ nối với github_service khi hoàn thiện luồng xuất bản.
    """
    return {
        "success": True,
        "message": "Xác thực quyền sở hữu hợp lệ để triển khai landing page.",
        "data": {"project_id": project["id"], "status": project["status"]},
    }



@router.post("/{project_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_project_content(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """Sinh nội dung landing page bằng Gemini API, lưu JSON vào DB và render HTML hoàn chỉnh."""
    try:
        generation = generate_content_for_project(db=db, project_id=project["id"])
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("PROJECT_NOT_FOUND", "Landing page không tồn tại."),
        )
    except Exception:
        logger.exception("Lỗi khi sinh/lưu nội dung cho project %s", project["id"])
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail("DATABASE_ERROR", "Lỗi hệ thống khi lưu dữ liệu sinh nội dung."),
        )

    if generation.status != STATUS_SUCCESS or generation.response_json is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_detail(
                "GEMINI_ERROR",
                "Không thể sinh nội dung từ Gemini API. Vui lòng thử lại sau.",
            ),
        )

    # Lấy dữ liệu project mới nhất (đã cập nhật raw_json_data) và render HTML thực tế
    refreshed_row = _fetch_project(db, project["id"])
    project_dict = _serialize_project(refreshed_row)
    rendered_html = template_service.render_landing_page(project_dict)

    return {
        "success": True,
        "rendered_html": rendered_html,
        "data": {
            "id": generation.id,
            "project_id": generation.project_id,
            "status": generation.status,
            "raw_json_data": generation.response_json,
            "response_json": generation.response_json,
            "rendered_html": rendered_html,
            "created_at": generation.created_at.isoformat() if generation.created_at else None,
        },
    }

