import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from models import STATUS_SUCCESS
from schemas.project import ProjectCreate, ProjectUpdate
from services import github_service, template_service
from services.generation_service import ProjectNotFoundError, generate_content_for_project
from services.github_service import (
    create_github_repo,
    enable_github_pages,
    push_landing_page_assets,
)
from services.version_service import create_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])

DEFAULT_CHANGE_SUMMARY = "Cập nhật landing page: text, giá, link social"


def _error_detail(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message, "details": []}}


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
    page: int = 1,
    page_size: int = 10,
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Danh sach project cua nguoi dang nhap, phan trang + loc status."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    elif page_size > 100:
        page_size = 100

    offset = (page - 1) * page_size

    where = "user_id = :user_id AND deleted_at IS NULL"
    params: dict = {"user_id": current_user["id"]}

    if status_filter:
        where += " AND status = :status"
        params["status"] = status_filter

    count_row = db.execute(
        text(f"SELECT COUNT(*) AS cnt FROM projects WHERE {where}"),
        params,
    ).mappings().first()
    total = int(count_row["cnt"]) if count_row else 0

    rows = (
        db.execute(
            text(
                f"SELECT * FROM projects WHERE {where} "
                "ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        )
        .mappings()
        .all()
    )

    return {
        "success": True,
        "data": {
            "items": [_serialize_project(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


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
    """Chi tiet project. Tra 404 neu khong ton tai, da xoa mem HOAC thuoc nguoi khac."""
    return {"success": True, "data": _serialize_project(project)}


@router.post("/{project_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_project_content(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """Sinh nội dung landing page bằng Gemini API và lưu kết quả JSON vào Database."""
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

    return {
        "success": True,
        "data": {
            "id": generation.id,
            "project_id": generation.project_id,
            "status": generation.status,
            "raw_json_data": generation.response_json,
            "response_json": generation.response_json,
            "created_at": generation.created_at.isoformat() if generation.created_at else None,
        },
    }


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
    """[BE] API xóa landing page.

- Chỉ chủ sở hữu mới được xóa (đã chặn bởi ``get_owned_project``).
- Gọi GitHub API xóa repository tương ứng nếu project có ``repo_url``.
- Xóa mềm trong DB bằng cách set ``deleted_at`` + ``status = 'deleted'``
      để bảo toàn lịch sử phiên bản và dữ liệu liên quan.
    """
    warnings: list[str] = []
    repo_url = (project.get("repo_url") or "").strip()
    github_status = "skipped"
    github_deleted = False

    if repo_url:
        try:
            result = github_service.delete_github_repo(repo_url)
            github_status = result.get("status") or "skipped"
            github_deleted = bool(result.get("deleted"))
            if github_status == "not_found":
                warnings.append(result.get("reason") or "GitHub repository đã không còn tồn tại.")
            elif github_status == "skipped":
                warnings.append(result.get("reason") or "Bỏ qua bước xóa GitHub repository.")
        except Exception as exc:  # pragma: no cover - lỗi mạng/hạ tầng/token
            logger.exception("Xóa GitHub repo thất bại cho project %s", project["id"])
            github_status = "failed"
            warnings.append(f"Không xóa được GitHub repository: {exc}")
    else:
        warnings.append("Dự án chưa có repo_url nên bỏ qua bước xóa GitHub repository.")

    db.execute(
        text(
            """
            UPDATE projects
            SET deleted_at = NOW(), status = 'deleted', updated_at = NOW()
            WHERE id = :id AND deleted_at IS NULL
            """
        ),
        {"id": project["id"]},
    )
    db.commit()

    return {
        "success": True,
        "message": "Đã xóa landing page thành công.",
        "data": {
            "project_id": project["id"],
            "deleted": True,
            "github_repo_deleted": github_deleted,
            "github_status": github_status,
        },
        "warnings": warnings,
    }


def _render_project_html(db: Session, project: dict) -> str:
    """Render nội dung index.html từ snapshot mới nhất hoặc file template + dữ liệu project."""
    latest_version = db.execute(
        text(
            "SELECT html_snapshot FROM project_versions "
            "WHERE project_id = :pid ORDER BY version_number DESC LIMIT 1"
        ),
        {"pid": project["id"]},
    ).first()
    if latest_version and latest_version[0]:
        return latest_version[0]

    tpl_row = db.execute(
        text("SELECT file_path FROM templates WHERE id = :tid"),
        {"tid": project["template_id"]},
    ).first()

    raw_data = project.get("raw_json_data") or {}
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            raw_data = {}

    context = {
        "campaign_name": project.get("campaign_name") or "",
        "product_name": project.get("product_name") or "",
        "headline": raw_data.get("headline") or project.get("campaign_name") or project.get("product_name") or "",
        "subheadline": raw_data.get("subheadline") or project.get("product_description") or "",
        "product_description": project.get("product_description") or "",
        "price": str(project.get("price") or ""),
        "hero_image_url": raw_data.get("hero_image_url") or project.get("image_url") or "",
        "image_url": project.get("image_url") or "",
        "primary_color": raw_data.get("primary_color") or project.get("color_theme") or "#4f46e5",
        "color_theme": project.get("color_theme") or "#4f46e5",
        "social_facebook": raw_data.get("social_facebook") or project.get("facebook_url") or "#",
        "social_tiktok": raw_data.get("social_tiktok") or project.get("tiktok_url") or "#",
        "social_instagram": raw_data.get("social_instagram") or project.get("instagram_url") or "#",
        **{k: str(v) for k, v in raw_data.items() if v is not None},
    }

    if tpl_row and tpl_row[0]:
        backend_dir = Path(__file__).resolve().parent.parent
        tpl_path = backend_dir / tpl_row[0]
        if tpl_path.exists():
            html = tpl_path.read_text(encoding="utf-8")
            for key, val in context.items():
                html = html.replace(f"{{{{{key}}}}}", str(val))
            return html

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{context['headline']}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800">
  <main class="max-w-3xl mx-auto py-16 px-6 text-center">
    <h1 class="text-4xl font-bold mb-4">{context['headline']}</h1>
    <p class="text-lg text-slate-600 mb-6">{context['subheadline']}</p>
    <p class="text-2xl font-semibold text-indigo-600 mb-8">{context['price']}</p>
  </main>
</body>
</html>"""


@router.post("/{project_id}/deploy")
def deploy_project(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """
    POST /projects/{id}/deploy
    Luồng xuất bản: render -> tạo repo (nếu chưa có) -> push -> bật Pages; ghi từng bước vào deployments.
    """
    now = datetime.utcnow()
    insert_res = db.execute(
        text(
            """
            INSERT INTO deployments (project_id, commit_sha, status, start_time)
            VALUES (:project_id, :commit_sha, :status, :start_time)
            """
        ),
        {
            "project_id": project["id"],
            "commit_sha": "pending",
            "status": "Rendering",
            "start_time": now,
        },
    )
    db.commit()
    deployment_id = insert_res.lastrowid

    try:
        html_content = _render_project_html(db, project)

        db.execute(
            text("UPDATE deployments SET status = :status WHERE id = :id"),
            {"status": "Creating Repo", "id": deployment_id},
        )
        db.commit()

        repo_url = project.get("repo_url")
        if repo_url:
            parts = repo_url.rstrip("/").split("/")
            owner, repo_name = parts[-2], parts[-1]
        else:
            slug = re.sub(r"[^a-zA-Z0-9-]+", "-", project.get("campaign_name", "")).strip("-").lower()
            repo_name = f"lp-{project['id']}-{slug}"[:60].rstrip("-") or f"landing-page-{project['id']}"
            repo_info = create_github_repo(repo_name=repo_name)
            owner = repo_info["full_name"].split("/")[0]
            repo_url = repo_info["html_url"]

            db.execute(
                text("UPDATE projects SET repo_url = :repo_url WHERE id = :id"),
                {"repo_url": repo_url, "id": project["id"]},
            )
            db.commit()

        db.execute(
            text("UPDATE deployments SET status = :status WHERE id = :id"),
            {"status": "Pushing Code", "id": deployment_id},
        )
        db.commit()

        push_result = push_landing_page_assets(
            owner=owner,
            repo_name=repo_name,
            html_content=html_content,
            images=None,
        )
        commit_sha = push_result.get("commit_sha") or "unknown"

        db.execute(
            text("UPDATE deployments SET commit_sha = :sha, status = :status WHERE id = :id"),
            {"sha": commit_sha, "status": "Enabling Pages", "id": deployment_id},
        )
        db.commit()

        pages_url = enable_github_pages(owner=owner, repo_name=repo_name)
        end_time = datetime.utcnow()

        db.execute(
            text(
                """
                UPDATE projects
                SET github_pages_url = :pages_url, status = 'published'
                WHERE id = :id
                """
            ),
            {"pages_url": pages_url, "id": project["id"]},
        )
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Success', github_pages_url = :pages_url, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"pages_url": pages_url, "end_time": end_time, "id": deployment_id},
        )
        db.commit()

        return {
            "success": True,
            "message": "Deploy landing page thành công!",
            "data": {
                "deployment_id": deployment_id,
                "project_id": project["id"],
                "repo_url": repo_url,
                "github_pages_url": pages_url,
                "commit_sha": commit_sha,
                "status": "Success",
            },
        }

    except Exception as exc:
        db.rollback()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Failed', error_message = :err, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"err": str(exc), "end_time": datetime.utcnow(), "id": deployment_id},
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Deploy thất bại: {exc}")