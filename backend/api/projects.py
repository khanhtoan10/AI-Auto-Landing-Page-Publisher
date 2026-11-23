import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from schemas.project import ProjectCreate, ProjectUpdate
from services.github_service import (
    create_github_repo,
    push_landing_page_assets,
    enable_github_pages,
    get_github_pages_build_status,
    wait_for_github_pages_built,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


def _render_project_html(project: dict) -> str:
    campaign_name = project.get("campaign_name") or "Landing Page"
    product_name = project.get("product_name") or campaign_name
    description = project.get("product_description") or ""
    price = project.get("price")
    price_html = f"<p><strong>Giá:</strong> {price}</p>" if price is not None else ""
    image_url = project.get("image_url") or ""
    img_html = f'<img src="{image_url}" alt="{product_name}" style="max-width:100%;height:auto;" />' if image_url else ""

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{campaign_name}</title>
</head>
<body>
  <main style="max-width:800px;margin:40px auto;font-family:sans-serif;padding:0 16px;">
    <h1>{product_name}</h1>
    <p>{description}</p>
    {price_html}
    {img_html}
  </main>
</body>
</html>
"""


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
async def deploy_project(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """
    POST /projects/{id}/deploy
    Luồng xuất bản: render -> tạo repo (nếu chưa có) -> push -> bật Pages -> đợi build xong -> ghi log deployments.
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
        html_content = _render_project_html(project)

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
            slug = re.sub(r"[^a-zA-Z0-9-]+", "-", (project.get("campaign_name") or "")).strip("-").lower()
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
        commit_sha = push_result.get("commit_sha") or "latest"

        db.execute(
            text("UPDATE deployments SET status = :status, commit_sha = :sha WHERE id = :id"),
            {"status": "Enabling Pages", "sha": commit_sha, "id": deployment_id},
        )
        db.commit()

        enable_github_pages(owner=owner, repo_name=repo_name)

        # Đồng bộ trạng thái build GitHub Pages: chỉ đánh dấu Success khi đã build xong
        db.execute(
            text("UPDATE deployments SET status = :status WHERE id = :id"),
            {"status": "Building", "id": deployment_id},
        )
        db.commit()

        build_info = wait_for_github_pages_built(owner=owner, repo_name=repo_name)
        github_pages_url = build_info.get("html_url") or f"https://{owner}.github.io/{repo_name}/"

        end_time = datetime.utcnow()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Success', end_time = :end_time
                WHERE id = :id
                """
            ),
            {"end_time": end_time, "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'published', published_url = :url WHERE id = :id"),
            {"url": github_pages_url, "id": project["id"]},
        )
        db.commit()

        return {
            "success": True,
            "message": "Deploy landing page thành công.",
            "data": {
                "deployment_id": deployment_id,
                "project_id": project["id"],
                "repo_url": repo_url,
                "github_pages_url": github_pages_url,
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


@router.get("/{project_id}/deploy-status")
async def get_project_deploy_status(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """
    GET /projects/{id}/deploy-status
    Kiểm tra trạng thái build GitHub Pages thực tế và chỉ trả link truy cập khi đã build xong.
    """
    latest_dep = (
        db.execute(
            text(
                """
                SELECT id, status, commit_sha, error_message, start_time, end_time
                FROM deployments
                WHERE project_id = :project_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"project_id": project["id"]},
        )
        .mappings()
        .first()
    )

    repo_url = project.get("repo_url")
    if not repo_url:
        return {
            "success": True,
            "data": {
                "project_id": project["id"],
                "deploy_status": latest_dep["status"] if latest_dep else "NotDeployed",
                "pages_build_status": "not_configured",
                "is_built": False,
                "github_pages_url": None,
                "error_message": latest_dep["error_message"] if latest_dep else None,
            },
        }

    parts = repo_url.rstrip("/").split("/")
    owner, repo_name = parts[-2], parts[-1]
    build_info = get_github_pages_build_status(owner=owner, repo_name=repo_name)
    build_status = (build_info.get("status") or "building").lower()
    is_built = build_status == "built"

    if latest_dep and latest_dep["status"] not in ("Success", "Failed"):
        if is_built:
            pages_url = build_info.get("html_url") or f"https://{owner}.github.io/{repo_name}/"
            db.execute(
                text("UPDATE deployments SET status = 'Success', end_time = :now WHERE id = :id"),
                {"now": datetime.utcnow(), "id": latest_dep["id"]},
            )
            db.execute(
                text("UPDATE projects SET status = 'published', published_url = :url WHERE id = :id"),
                {"url": pages_url, "id": project["id"]},
            )
            db.commit()
        elif build_status == "errored":
            db.execute(
                text(
                    """
                    UPDATE deployments
                    SET status = 'Failed', error_message = :err, end_time = :now
                    WHERE id = :id
                    """
                ),
                {"err": build_info.get("error"), "now": datetime.utcnow(), "id": latest_dep["id"]},
            )
            db.commit()

    return {
        "success": True,
        "data": {
            "project_id": project["id"],
            "deploy_status": "Success" if is_built else (latest_dep["status"] if latest_dep else "Building"),
            "pages_build_status": build_status,
            "is_built": is_built,
            "github_pages_url": build_info.get("html_url") if is_built else None,
            "error_message": build_info.get("error"),
        },
    }