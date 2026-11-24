import json
import re
from datetime import datetime
from pathlib import Path
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
    GitHubRateLimitError,
    GitHubRepoDuplicateError,
    GitHubAuthError,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


def _render_project_html(db: Session, project: dict) -> str:
    """Render nội dung index.html từ snapshot mới nhất hoặc file template + dữ liệu project."""
    # 1. Ưu tiên lấy html_snapshot mới nhất nếu project đã có version
    latest_version = db.execute(
        text(
            "SELECT html_snapshot FROM project_versions "
            "WHERE project_id = :pid ORDER BY version_number DESC LIMIT 1"
        ),
        {"pid": project["id"]},
    ).first()
    if latest_version and latest_version[0]:
        return latest_version[0]

    # 2. Lấy đường dẫn file template từ bảng templates
    tpl_row = db.execute(
        text("SELECT file_path FROM templates WHERE id = :tid"),
        {"tid": project.get("template_id")},
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

    # 3. Fallback HTML chuẩn nếu file template chưa tồn tại trên ổ đĩa
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
                SET status = 'Success', github_pages_url = :url, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"url": github_pages_url, "end_time": end_time, "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'published', github_pages_url = :url WHERE id = :id"),
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
    except GitHubAuthError as exc:
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
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        )
    except GitHubRateLimitError as exc:
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
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        )
    except GitHubRepoDuplicateError as exc:
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
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
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
                text(
                    """
                    UPDATE deployments
                    SET status = 'Success', github_pages_url = :url, end_time = :now
                    WHERE id = :id
                    """
                ),
                {"url": pages_url, "now": datetime.utcnow(), "id": latest_dep["id"]},
            )
            db.execute(
                text("UPDATE projects SET status = 'published', github_pages_url = :url WHERE id = :id"),
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
