"""Kiểm thử tự động cho [BE] API cập nhật landing page.

Bao gồm 6 bài test theo kế hoạch:
  [TEST 1] GET /projects/{id}            - lấy dữ liệu dự án điền vào Form.
  [TEST 2] POST /projects/{id}/preview   - render HTML xem trước, không lưu DB.
  [TEST 3] PUT  /projects/{id}           - cập nhật DB -> render -> push GitHub -> lưu version.
  [TEST 4] project_versions              - số phiên bản tăng và khớp commit_sha.
  [TEST 5] Cập nhật lần 2                - version_number tự tăng (Append-only).
  [TEST 6] Phân quyền                    - trả 404 nếu không tồn tại, 403 nếu không sở hữu.

Chạy từ thư mục backend:
    python scripts/test_update_landing_page.py

Nếu MySQL chưa được cấu hình (backend/.env), script tự chuyển sang chế độ offline:
vẫn kiểm tra template render + GitHub SHA, các bài test DB sẽ được SKIP.
"""

import asyncio
import os
import re
import sys
import uuid

from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):  # Windows console mặc định có thể là cp1258/cp932
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pymysql
from fastapi import HTTPException
from sqlalchemy import text

from api.projects import preview_project, update_project
from core.database import SessionLocal
from core.security import get_owned_project
from schemas.project import ProjectUpdate
from services import github_service, template_service
from services.version_service import get_version_detail, list_versions

PASSED = 0


def check(name: str, condition: bool, detail: str) -> None:
    global PASSED
    if not condition:
        raise AssertionError(f"FAIL {name}: {detail}")
    PASSED += 1
    print(f"PASS {name}: {detail}")


# ── Offline: template render + GitHub helpers ───────────────────────
def run_offline_checks() -> None:
    sample = {
        "id": 1,
        "product_name": "Cà Phê Cold Brew Đắk Lắk",
        "campaign_name": "Ra mắt Cold Brew 2025",
        "product_description": "Cà phê ủ lạnh 24 giờ, 100% Robusta chọn lọc.",
        "price": Decimal("1250000"),
        "color_theme": "#0F766E",
        "image_url": None,
        "facebook_url": "https://facebook.com/coldbrewk",
        "tiktok_url": "https://tiktok.com/@coldbrewk",
        "instagram_url": "https://instagram.com/coldbrewk",
        "repo_url": "https://github.com/example/landing-page-demo",
        "github_pages_url": None,
        "raw_json_data": None,
    }
    html = template_service.render_landing_page(sample)

    check(
        "RENDER 1",
        len(html) > 5000 and html.lstrip().startswith("<!DOCTYPE html>"),
        f"render_landing_page trả về HTML hoàn chỉnh ({len(html)} ký tự)",
    )
    check(
        "RENDER 2",
        "Cà Phê Cold Brew Đắk Lắk" in html and "1.250.000 ₫" in html,
        "HTML chứa tên sản phẩm và giá định dạng VND",
    )
    check(
        "RENDER 3",
        "#0F766E" in html
        and "facebook.com/coldbrewk" in html
        and "tiktok.com/@coldbrewk" in html
        and "instagram.com/coldbrewk" in html,
        "HTML áp dụng color_theme và đủ 3 liên kết mạng xã hội",
    )
    check(
        "RENDER 4",
        "viewport" in html and "sm:grid-cols-2" in html,
        "HTML responsive (viewport + breakpoint Tailwind)",
    )

    check(
        "GITHUB 1",
        github_service.parse_repo_info("https://github.com/owner/repo.git") == ("owner", "repo")
        and github_service.parse_repo_info("git@github.com:owner/repo.git") == ("owner", "repo")
        and github_service.parse_repo_info("https://gitlab.com/owner/repo") is None,
        "parse_repo_info xử lý đúng HTTPS/SSH và từ chối host lạ",
    )
    local_sha = github_service.push_landing_page_commit(
        "https://github.com/example/landing-page-demo", html, "test offline"
    )
    check(
        "GITHUB 2",
        bool(re.fullmatch(r"[0-9a-f]{40}", local_sha)),
        f"fallback commit SHA mô phỏng hợp lệ 40 ký tự hex ({local_sha})",
    )


# ── Online: kiểm thử tích hợp DB + service ──────────────────────────
def run_db_checks() -> None:
    from scripts.init_db import hash_password, init_database

    init_database()
    db = SessionLocal()
    user_ids: list[int] = []
    project_id = None

    try:
        suffix = uuid.uuid4().hex[:8]

        def create_user(name: str) -> dict:
            result = db.execute(
                text(
                    "INSERT INTO users (full_name, email, hashed_password) "
                    "VALUES (:full_name, :email, :hashed_password)"
                ),
                {
                    "full_name": name,
                    "email": f"test-{name.lower().replace(' ', '-')}-{suffix}@example.com",
                    "hashed_password": hash_password("Test12345!"),
                },
            )
            db.commit()
            user_ids.append(int(result.lastrowid))
            return {"id": int(result.lastrowid), "full_name": name}

        owner = create_user("Update Landing Owner")
        stranger = create_user("Update Landing Stranger")

        template_row = db.execute(text("SELECT id FROM templates ORDER BY id LIMIT 1")).first()
        if not template_row:
            raise AssertionError("FAIL: bảng templates rỗng, hãy chạy scripts/init_db.py")
        template_id = int(template_row[0])

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
            {
                "user_id": owner["id"],
                "template_id": template_id,
                "campaign_name": "Chiến dịch ban đầu",
                "product_name": "Sản phẩm ban đầu",
                "product_description": "Mô tả ban đầu của sản phẩm.",
                "price": Decimal("990000"),
                "image_url": None,
                "color_theme": "#4F46E5",
                "facebook_url": None,
                "tiktok_url": None,
                "instagram_url": None,
            },
        )
        db.commit()
        project_id = int(result.lastrowid)

        project_row = (
            db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": project_id})
            .mappings()
            .one()
        )
        project = dict(project_row)

        # TEST 1: GET /projects/{id}
        loaded = get_owned_project(project_id=project_id, current_user=owner, db=db)
        check(
            "TEST 1",
            loaded["id"] == project_id
            and loaded["product_name"] == "Sản phẩm ban đầu"
            and loaded["price"] is not None,
            "GET /projects/{id} trả đúng dữ liệu để điền Form",
        )

        # TEST 2: POST /projects/{id}/preview
        preview = asyncio.run(
            preview_project(
                payload=ProjectUpdate(
                    product_name="Sản phẩm xem trước",
                    price=Decimal("1500000"),
                    color_theme="#123456",
                ),
                project=loaded,
            )
        )
        db_price = db.execute(
            text("SELECT price FROM projects WHERE id = :id"), {"id": project_id}
        ).scalar_one()
        check(
            "TEST 2",
            preview["success"]
            and "Sản phẩm xem trước" in preview["rendered_html"]
            and "1.500.000 ₫" in preview["rendered_html"]
            and "#123456" in preview["rendered_html"]
            and float(db_price) == 990000.0,
            "POST /preview render đúng dữ liệu mới và KHÔNG ghi vào DB",
        )

        # TEST 3: PUT /projects/{id}
        first_payload = ProjectUpdate(
            campaign_name="Chiến dịch cập nhật",
            product_name="Sản phẩm cập nhật",
            product_description="Mô tả mới sau khi chỉnh sửa landing page.",
            price=Decimal("1500000"),
            color_theme="#123456",
            facebook_url="https://facebook.com/updated-page",
            tiktok_url="https://tiktok.com/@updated-page",
            instagram_url="https://instagram.com/updated-page",
            repo_url="https://github.com/example/landing-page-demo",
            github_pages_url="https://example.github.io/landing-page-demo",
            change_summary="Cập nhật lần 1: text, giá, social",
        )
        first = asyncio.run(
            update_project(
                payload=first_payload,
                project=loaded,
                current_user=owner,
                db=db,
            )
        )
        check(
            "TEST 3",
            first["success"]
            and bool(re.fullmatch(r"[0-9a-f]{40}", first["commit_sha"] or ""))
            and first["version_number"] == 1
            and "1.500.000 ₫" in first["rendered_html"]
            and "Sản phẩm cập nhật" in first["rendered_html"]
            and "facebook.com/updated-page" in first["rendered_html"]
            and "#123456" in first["rendered_html"],
            "PUT cập nhật DB, render HTML, push GitHub và trả về version_number=1 + commit_sha",
        )

        db_state = (
            db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": project_id})
            .mappings()
            .one()
        )
        check(
            "TEST 3b",
            db_state["product_name"] == "Sản phẩm cập nhật"
            and float(db_state["price"]) == 1500000.0
            and db_state["facebook_url"] == "https://facebook.com/updated-page"
            and db_state["color_theme"] == "#123456",
            "Bảng projects đã lưu đúng text, giá, social và color_theme",
        )

        # TEST 4: project_versions tăng và khớp commit_sha
        versions = list_versions(project_id)
        detail = get_version_detail(project_id, first["version_id"])
        check(
            "TEST 4",
            len(versions) == 1
            and versions[0]["version_number"] == 1
            and detail is not None
            and detail["commit_sha"] == first["commit_sha"]
            and "Sản phẩm cập nhật" in detail["html_snapshot"],
            "project_versions có 1 bản ghi, version_number=1, commit_sha khớp",
        )

        # TEST 5: cập nhật lần 2 -> version_number tự tăng
        second = asyncio.run(
            update_project(
                payload=ProjectUpdate(
                    price=Decimal("2000000"),
                    change_summary="Cập nhật lần 2: điều chỉnh giá",
                ),
                project=dict(
                    db.execute(
                        text("SELECT * FROM projects WHERE id = :id"), {"id": project_id}
                    )
                    .mappings()
                    .one()
                ),
                current_user=owner,
                db=db,
            )
        )
        versions_after = list_versions(project_id)
        check(
            "TEST 5",
            second["version_number"] == 2
            and len(versions_after) == 2
            and second["commit_sha"] != first["commit_sha"]
            and "2.000.000 ₫" in second["rendered_html"],
            "Cập nhật lần 2 tạo version_number=2 (Append-only) với commit_sha mới",
        )

        # TEST 6: lỗi phân quyền 404 / 403
        status_404 = None
        try:
            get_owned_project(project_id=2_000_000_000, current_user=owner, db=db)
        except HTTPException as exc:
            status_404 = exc.status_code

        status_403 = None
        try:
            get_owned_project(project_id=project_id, current_user=stranger, db=db)
        except HTTPException as exc:
            status_403 = exc.status_code

        check(
            "TEST 6",
            status_404 == 404 and status_403 == 403,
            f"guard trả 404 khi project không tồn tại ({status_404}) và 403 khi không sở hữu ({status_403})",
        )

    finally:
        if project_id is not None:
            db.rollback()
            db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
            db.commit()
        for user_id in user_ids:
            db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        db.commit()
        db.close()


def main() -> None:
    print("=== [BE] Test cập nhật landing page ===")
    run_offline_checks()

    try:
        run_db_checks()
    except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as exc:
        print(
            "\nSKIP các bài test DB: không kết nối được MySQL "
            f"({exc}).\n     Hãy tạo backend/.env từ backend/.env.example rồi chạy lại."
        )
        print(f"\nHoàn tất: {PASSED} kiểm tra offline PASS, 6 bài test DB được SKIP.")
        return

    print(f"\nHoàn tất: {PASSED} kiểm tra PASS.")


if __name__ == "__main__":
    main()
