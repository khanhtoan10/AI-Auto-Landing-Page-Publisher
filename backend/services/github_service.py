import base64
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"


def _get_headers() -> dict:
    if not GITHUB_TOKEN or GITHUB_TOKEN == "your_github_personal_access_token_here":
        raise ValueError("GITHUB_TOKEN chưa được cấu hình hợp lệ trong file backend/.env")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def upload_file_to_repo(
    owner: str,
    repo_name: str,
    file_path: str,
    content: str | bytes,
    commit_message: str = "Upload landing page asset",
    branch: str = "main",
) -> dict:
    """
    Đẩy 1 file (index.html dạng str hoặc ảnh dạng bytes) lên repo qua GitHub Contents API.
    Tự động lấy sha nếu file đã tồn tại để ghi đè.
    """
    headers = _get_headers()
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contents/{file_path.lstrip('/')}"

    # Chuyển nội dung sang base64
    raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
    encoded_content = base64.b64encode(raw_bytes).decode("utf-8")

    # Kiểm tra xem file đã có trên repo chưa để lấy sha (tránh lỗi 422 khi update)
    sha = None
    check_res = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
    if check_res.status_code == 200:
        sha = check_res.json().get("sha")

    payload = {
        "message": commit_message,
        "content": encoded_content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(url, json=payload, headers=headers, timeout=20)
    if response.status_code in (200, 201):
        data = response.json()
        return {
            "path": file_path,
            "commit_sha": data.get("commit", {}).get("sha"),
            "html_url": data.get("content", {}).get("html_url"),
        }

    error_detail = response.json().get("message", response.text)
    raise RuntimeError(f"Push file '{file_path}' thất bại ({response.status_code}): {error_detail}")


def push_landing_page_assets(
    owner: str,
    repo_name: str,
    html_content: str,
    images: list[dict] | None = None,
    branch: str = "main",
) -> dict:
    """
    Đẩy file index.html và danh sách ảnh (nếu có) lên repository vừa tạo.
    Mỗi phần tử trong images có dạng: {"path": "images/banner.png", "content": <bytes>}
    """
    uploaded_files = []
    latest_commit_sha = None

    # 1. Push các file ảnh trước (nếu có)
    for img in images or []:
        res = upload_file_to_repo(
            owner=owner,
            repo_name=repo_name,
            file_path=img["path"],
            content=img["content"],
            commit_message=f"Add asset {img['path']}",
            branch=branch,
        )
        uploaded_files.append(res["path"])
        latest_commit_sha = res["commit_sha"]

    # 2. Push file index.html
    html_res = upload_file_to_repo(
        owner=owner,
        repo_name=repo_name,
        file_path="index.html",
        content=html_content,
        commit_message="Deploy index.html landing page",
        branch=branch,
    )
    uploaded_files.append(html_res["path"])
    latest_commit_sha = html_res["commit_sha"]

    return {
        "uploaded_files": uploaded_files,
        "commit_sha": latest_commit_sha,
    }


def enable_github_pages(
    owner: str,
    repo_name: str,
    branch: str = "main",
    path: str = "/",
) -> str:
    """
    Gọi API bật GitHub Pages cho repository và trả về URL chuẩn dạng https://username.github.io/repo-name
    """
    headers = _get_headers()
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pages"
    payload = {
        "source": {
            "branch": branch,
            "path": path,
        }
    }

    response = requests.post(url, json=payload, headers=headers, timeout=15)

    # 201: Bật thành công | 409: Pages đã được bật từ trước
    if response.status_code in (201, 409):
        pages_url = f"https://{owner.lower()}.github.io/{repo_name}"
        return pages_url

    error_detail = response.json().get("message", response.text)
    raise RuntimeError(f"Bật GitHub Pages thất bại ({response.status_code}): {error_detail}")

    from sqlalchemy.orm import Session
from backend.models.project import Project


def publish_and_save_project_url(
    db: Session,
    project: Project,
    owner: str,
    repo_name: str,
    html_content: str,
    images: list[dict] | None = None,
) -> dict:
    """
    Đẩy index.html + ảnh lên repo, bật GitHub Pages và lưu URL vào bản ghi project.
    """
    push_result = push_landing_page_assets(
        owner=owner,
        repo_name=repo_name,
        html_content=html_content,
        images=images,
    )
    pages_url = enable_github_pages(owner=owner, repo_name=repo_name)

    # Cập nhật URL vào project (đổi tên thuộc tính nếu model Project đặt tên cột khác)
    if hasattr(project, "github_pages_url"):
        project.github_pages_url = pages_url
    elif hasattr(project, "deploy_url"):
        project.deploy_url = pages_url

    db.commit()
    db.refresh(project)

    return {
        "commit_sha": push_result["commit_sha"],
        "github_pages_url": pages_url,
    }