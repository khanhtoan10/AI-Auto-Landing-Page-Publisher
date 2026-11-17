import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from models import STATUS_SUCCESS
from schemas.project import ProjectCreate, ProjectUpdate
from services.generation_service import ProjectNotFoundError, generate_content_for_project

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = logging.getLogger(__name__)


def _error_detail(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message, "details": []}}


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
    return {"success": True, "data": [dict(r) for r in rows]}


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
             price, image_url, color_theme, facebook_url, tiktok_url, instagram_url, status)
            VALUES
            (:user_id, :template_id, :campaign_name, :product_name, :product_description,
             :price, :image_url, :color_theme, :facebook_url, :tiktok_url, :instagram_url, 'draft')
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
    return {"success": True, "data": dict(row)}


@router.get("/{project_id}")
async def get_project_detail(
    project: dict = Depends(get_owned_project),
):
    return {"success": True, "data": project}


@router.put("/{project_id}")
async def update_project(
    payload: ProjectUpdate,
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return {"success": True, "data": project}

    if "template_id" in update_data and update_data["template_id"] is not None:
        template = db.execute(
            text("SELECT id FROM templates WHERE id = :id"),
            {"id": update_data["template_id"]},
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template khong ton tai")

    if "raw_json_data" in update_data and update_data["raw_json_data"] is not None:
        update_data["raw_json_data"] = json.dumps(update_data["raw_json_data"], ensure_ascii=False)

    set_clauses = ", ".join(f"{col} = :{col}" for col in update_data.keys())
    update_data["id"] = project["id"]

    db.execute(
        text(f"UPDATE projects SET {set_clauses} WHERE id = :id"),
        update_data,
    )
    db.commit()

    row = (
        db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": project["id"]})
        .mappings()
        .one()
    )
    return {"success": True, "data": dict(row)}


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