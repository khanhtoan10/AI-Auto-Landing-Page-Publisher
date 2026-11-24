"""Kiểm thử tích hợp Sprint 3 cho Dashboard và Lịch sử xuất bản.

Script chạy hoàn toàn offline với SQLite in-memory, không cần MySQL hay API key:

  1. Ứng dụng FastAPI import được và phục vụ frontend thật tại "/".
  2. Endpoint /projects/stats trả đúng số liệu tổng quan của người dùng.
  3. Endpoint /deployments trả đúng trạng thái active / superseded / failed.
  4. Endpoint /deployments/stats trả đúng tỷ lệ thành công.
  5. Alias /api/v1/deployments và bộ lọc theo project hoạt động.
  6. Request chưa đăng nhập bị chặn 401.

Chạy:
    python backend/scripts/test_sprint3_integration.py
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# SQLite không hỗ trợ kiểu Decimal của Pydantic; adapter này chỉ dùng cho test offline.
sqlite3.register_adapter(Decimal, lambda value: float(value))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.projects as projects_api
from core.database import get_db
from core.security import get_current_user
from main import app

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, full_name TEXT);
CREATE TABLE templates (id INTEGER PRIMARY KEY, name TEXT, file_path TEXT);
CREATE TABLE projects (
    id INTEGER PRIMARY KEY, user_id INTEGER, template_id INTEGER,
    campaign_name TEXT, product_name TEXT, product_description TEXT,
    price NUMERIC, status TEXT, color_theme TEXT, image_url TEXT,
    messenger_link TEXT, tiktok_shop_link TEXT, zalo_link TEXT,
    instagram_link TEXT, hotline TEXT,
    facebook_url TEXT, tiktok_url TEXT, instagram_url TEXT,
    raw_json_data TEXT, github_pages_url TEXT, repo_url TEXT,
    deleted_at DATETIME, created_at DATETIME, updated_at DATETIME
);
CREATE TABLE generations (
    id INTEGER PRIMARY KEY, project_id INTEGER, status TEXT, prompt TEXT, created_at DATETIME
);
CREATE TABLE deployments (
    id INTEGER PRIMARY KEY, project_id INTEGER, commit_sha TEXT, status TEXT,
    github_pages_url TEXT, error_message TEXT, start_time DATETIME, end_time DATETIME
);
CREATE TABLE project_versions (
    id INTEGER PRIMARY KEY, project_id INTEGER, version_number INTEGER,
    html_snapshot TEXT, json_content TEXT, commit_sha TEXT,
    change_summary TEXT, created_by INTEGER, created_at DATETIME
);
"""


def check(name: str, condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(f"FAILED [{name}]: {detail}")
    print(f"PASSED [{name}]: {detail}")


def build_seed_data(engine) -> None:
    now = datetime(2026, 11, 23, 10, 0, 0)
    with engine.begin() as conn:
        for statement in SCHEMA.strip().split(";"):
            if statement.strip():
                conn.execute(text(statement))

        conn.execute(text("INSERT INTO users (id, email, full_name) VALUES (1, 'a@b.c', 'Test User')"))
        conn.execute(text("INSERT INTO templates (id, name) VALUES (1, 'SaaS')"))
        conn.execute(
            text(
                """
                INSERT INTO projects
                (id, user_id, template_id, campaign_name, product_name, product_description,
                 price, status, color_theme, image_url, github_pages_url, repo_url,
                 deleted_at, created_at, updated_at)
                VALUES
                (1, 1, 1, 'Draft Project', 'Draft', 'desc', 100, 'draft', '#4f46e5', NULL, NULL, NULL, NULL, :t1, :t1),
                (2, 1, 1, 'Published Project', 'Published', 'desc', 200, 'published', '#4f46e5', NULL,
                 'https://user.github.io/lp-2', 'https://github.com/user/lp-2', NULL, :t2, :t2),
                (3, 1, 1, 'Deleted Project', 'Deleted', 'desc', 300, 'deleted', '#4f46e5', NULL, NULL, NULL, :t2, :t2, :t2)
                """
            ),
            {"t1": now - timedelta(days=2), "t2": now - timedelta(days=1)},
        )
        conn.execute(
            text("INSERT INTO generations (id, project_id, status, prompt, created_at) VALUES (1, 1, 'success', 'x', :t)"),
            {"t": now},
        )
        conn.execute(
            text("INSERT INTO generations (id, project_id, status, prompt, created_at) VALUES (2, 2, 'failed', 'y', :t)"),
            {"t": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO deployments
                (id, project_id, commit_sha, status, github_pages_url, error_message, start_time, end_time)
                VALUES
                (1, 2, 'aaaa1111', 'Success', 'https://user.github.io/lp-2', NULL, :s1, :e1),
                (2, 2, 'bbbb2222', 'Success', 'https://user.github.io/lp-2', NULL, :s2, :e2),
                (3, 2, 'cccc3333', 'Failed', NULL, 'GitHub token invalid', :s3, :e3)
                """
            ),
            {
                "s1": now - timedelta(days=2),
                "e1": now - timedelta(days=2) + timedelta(seconds=30),
                "s2": now - timedelta(days=1),
                "e2": now - timedelta(days=1) + timedelta(seconds=45),
                "s3": now,
                "e3": now + timedelta(seconds=10),
            },
        )


def run() -> None:
    print("=" * 70)
    print("[SPRINT 3] KIỂM THỬ TÍCH HỢP FRONTEND + BACKEND")
    print("=" * 70)

    client = TestClient(app)

    root = client.get("/")
    check("Frontend tại /", root.status_code == 200 and "Tổng quan" in root.text, f"HTTP {root.status_code}")

    static_page = client.get("/pages/projects.html")
    check("Static page", static_page.status_code == 200, f"HTTP {static_page.status_code}")

    static_js = client.get("/js/api.js")
    check("Static JS", static_js.status_code == 200, f"HTTP {static_js.status_code}")

    unauthorized = client.get("/projects/stats")
    check("Chặn chưa đăng nhập", unauthorized.status_code == 401, f"HTTP {unauthorized.status_code}")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite không có NOW(); đăng ký hàm tương đương để tái sử dụng nguyên SQL của MySQL.
    def _register_now(dbapi_connection, _connection_record):
        dbapi_connection.create_function(
            "NOW",
            0,
            lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "),
        )

    event.listen(engine, "connect", _register_now)
    build_seed_data(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "email": "a@b.c",
        "full_name": "Test User",
    }

    try:
        stats = client.get("/projects/stats")
        check("GET /projects/stats", stats.status_code == 200, f"HTTP {stats.status_code}")
        data = stats.json()["data"]
        check("Tổng dự án", data["total_projects"] == 2, f"{data['total_projects']} dự án (bỏ qua đã xóa)")
        check("Số bản nháp", data["draft_projects"] == 1, f"{data['draft_projects']} bản nháp")
        check("Số đã xuất bản", data["published_projects"] == 1, f"{data['published_projects']} đã xuất bản")
        check("Lượt sinh AI", data["total_generations"] == 2, f"{data['total_generations']} lượt")
        check("Deploy thành công", data["successful_deployments"] == 2, f"{data['successful_deployments']} lượt")
        check("Template", data["total_templates"] == 1, f"{data['total_templates']} template")
        check("Dự án gần đây", len(data["recent_projects"]) == 2, f"{len(data['recent_projects'])} dự án")

        listing = client.get("/deployments")
        check("GET /deployments", listing.status_code == 200, f"HTTP {listing.status_code}")
        items = listing.json()["data"]["items"]
        check("Số deployment", len(items) == 3, f"{len(items)} bản ghi")
        by_id = {item["id"]: item for item in items}
        check("Deployment mới nhất active", by_id[2]["view_status"] == "active", by_id[2]["view_status"])
        check("Deployment cũ superseded", by_id[1]["view_status"] == "superseded", by_id[1]["view_status"])
        check("Deployment lỗi failed", by_id[3]["view_status"] == "failed", by_id[3]["view_status"])
        check("Thời lượng deploy", by_id[2]["duration_seconds"] == 45, f"{by_id[2]['duration_seconds']} giây")
        check("URL công khai", bool(by_id[2]["page_url"]), by_id[2]["page_url"] or "—")

        filtered = client.get("/deployments?status=active")
        check("Lọc active", filtered.json()["data"]["total"] == 1, f"{filtered.json()['data']['total']} kết quả")

        dep_stats = client.get("/deployments/stats").json()["data"]
        check("Tỷ lệ thành công", dep_stats["success_rate"] == 66.7, f"{dep_stats['success_rate']}%")
        check("Số dự án live", dep_stats["live_projects"] == 1, f"{dep_stats['live_projects']} dự án")

        alias = client.get("/api/v1/deployments")
        check("Alias /api/v1/deployments", alias.status_code == 200, f"HTTP {alias.status_code}")

        scoped = client.get("/deployments?project_id=2")
        check("Lọc theo dự án", scoped.json()["data"]["total"] == 3, f"{scoped.json()['data']['total']} kết quả")

        forbidden = client.get("/deployments?project_id=3")
        check("Chặn dự án đã xóa", forbidden.status_code == 404, f"HTTP {forbidden.status_code}")

        alias_stats = client.get("/api/v1/projects/stats")
        check("Alias /api/v1/projects/stats", alias_stats.status_code == 200, f"HTTP {alias_stats.status_code}")

        # ── Luồng CRUD + Deploy thật (mock GitHub/Gemini, SQLite in-memory) ──
        create_res = client.post(
            "/projects",
            json={
                "template_id": 1,
                "campaign_name": "Chiến dịch tích hợp Sprint 3",
                "product_name": "Sản phẩm tích hợp",
                "product_description": "Kiểm thử luồng tạo, sửa, deploy và xóa.",
                "price": 199000,
                "color_theme": "#4f46e5",
                "messenger_link": "m.me/tichhop",
                "hotline": "1900 1234",
            },
        )
        check("POST /projects", create_res.status_code == 201, f"HTTP {create_res.status_code}")
        created = create_res.json()["data"]
        new_id = created["id"]
        check("Dự án mới ở trạng thái nháp", created["status"] == "draft", created["status"])

        detail_res = client.get(f"/projects/{new_id}")
        check("GET /projects/{id}", detail_res.status_code == 200, f"HTTP {detail_res.status_code}")
        check(
            "CTA Messenger được lưu",
            detail_res.json()["data"]["messenger_link"] == "m.me/tichhop",
            str(detail_res.json()["data"]["messenger_link"]),
        )

        preview_res = client.post(
            f"/projects/{new_id}/preview",
            json={"product_name": "Sản phẩm xem trước", "price": 299000},
        )
        check("POST /projects/{id}/preview", preview_res.status_code == 200, f"HTTP {preview_res.status_code}")
        check(
            "Preview trả HTML thật",
            "<html" in preview_res.json().get("rendered_html", "").lower(),
            "rendered_html hợp lệ",
        )

        original_push = projects_api.github_service.push_landing_page_commit
        original_create_version = projects_api.create_version
        original_create_repo = projects_api.create_github_repo
        original_push_assets = projects_api.push_landing_page_assets
        original_enable_pages = projects_api.enable_github_pages
        original_wait_built = projects_api.wait_for_github_pages_built
        original_get_build_status = projects_api.get_github_pages_build_status
        try:
            projects_api.github_service.push_landing_page_commit = lambda **kwargs: "abc123def456"
            projects_api.create_version = lambda **kwargs: {"id": 999, "version_number": 1}
            projects_api.create_github_repo = lambda repo_name: {
                "full_name": f"tester/{repo_name}",
                "html_url": f"https://github.com/tester/{repo_name}",
            }
            projects_api.push_landing_page_assets = lambda **kwargs: {"commit_sha": "abc123def456"}
            projects_api.enable_github_pages = lambda owner, repo_name: f"https://{owner}.github.io/{repo_name}"
            projects_api.wait_for_github_pages_built = lambda owner, repo_name, **kwargs: {
                "status": "built",
                "html_url": f"https://{owner}.github.io/{repo_name}",
                "error": None,
            }
            projects_api.get_github_pages_build_status = lambda owner, repo_name, **kwargs: {
                "status": "built",
                "html_url": f"https://{owner}.github.io/{repo_name}",
                "error": None,
            }

            update_res = client.put(
                f"/projects/{new_id}",
                json={
                    "campaign_name": "Chiến dịch đã cập nhật",
                    "product_name": "Sản phẩm đã cập nhật",
                    "price": 399000,
                    "color_theme": "#10b981",
                    "zalo_link": "0987654321",
                    "hotline": "1900 5678",
                },
            )
            check("PUT /projects/{id}", update_res.status_code == 200, f"HTTP {update_res.status_code}")
            updated = update_res.json()["data"]
            check("Tên chiến dịch được cập nhật", updated["campaign_name"] == "Chiến dịch đã cập nhật", updated["campaign_name"])
            check("CTA Zalo được lưu", updated["zalo_link"] == "0987654321", str(updated["zalo_link"]))
            check("Hotline được cập nhật", updated["hotline"] == "1900 5678", str(updated["hotline"]))

            deploy_res = client.post(f"/projects/{new_id}/deploy")
            check("POST /projects/{id}/deploy", deploy_res.status_code == 200, f"HTTP {deploy_res.status_code}")
            deployed = deploy_res.json()["data"]
            check("Deploy thành công", deployed["status"] == "Success", deployed["status"])
            check("Có URL GitHub Pages", bool(deployed["github_pages_url"]), deployed["github_pages_url"] or "—")

            published_res = client.get(f"/projects/{new_id}")
            check(
                "Dự án chuyển published",
                published_res.json()["data"]["status"] == "published",
                published_res.json()["data"]["status"],
            )

            history_res = client.get(f"/deployments?project_id={new_id}")
            history_items = history_res.json()["data"]["items"]
            check("Lịch sử deploy của dự án mới", len(history_items) == 1, f"{len(history_items)} bản ghi")
            check("Trạng thái hiển thị active", history_items[0]["view_status"] == "active", history_items[0]["view_status"])

            projects_api.enable_github_pages = lambda owner, repo_name: (_ for _ in ()).throw(
                RuntimeError("GitHub Pages API lỗi giả lập")
            )
            failed_res = client.post(f"/projects/{new_id}/deploy")
            check("Deploy lỗi trả HTTP 500", failed_res.status_code == 500, f"HTTP {failed_res.status_code}")

            failed_project = client.get(f"/projects/{new_id}").json()["data"]
            check("Dự án chuyển failed", failed_project["status"] == "failed", failed_project["status"])

            failed_history = client.get(f"/deployments?project_id={new_id}").json()["data"]["items"]
            check("Có bản ghi deploy thất bại", len(failed_history) == 2, f"{len(failed_history)} bản ghi")
            check(
                "Lỗi deploy được lưu",
                "GitHub Pages API lỗi giả lập" in (failed_history[0]["error_message"] or ""),
                failed_history[0]["error_message"] or "—",
            )
        finally:
            projects_api.github_service.push_landing_page_commit = original_push
            projects_api.create_version = original_create_version
            projects_api.create_github_repo = original_create_repo
            projects_api.push_landing_page_assets = original_push_assets
            projects_api.enable_github_pages = original_enable_pages
            projects_api.wait_for_github_pages_built = original_wait_built
            projects_api.get_github_pages_build_status = original_get_build_status
        delete_res = client.delete(f"/projects/{new_id}")
        check("DELETE /projects/{id}", delete_res.status_code == 200, f"HTTP {delete_res.status_code}")
        deleted_detail = client.get(f"/projects/{new_id}")
        check("Dự án đã xóa mềm", deleted_detail.status_code == 404, f"HTTP {deleted_detail.status_code}")
    finally:
        app.dependency_overrides.clear()

    print("=" * 70)
    print("TẤT CẢ KIỂM THỬ SPRINT 3 ĐÃ PASS")
    print("=" * 70)

if __name__ == "__main__":
    run()
