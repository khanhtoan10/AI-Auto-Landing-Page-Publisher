"""
Unit and Integration Test Suite for Deploy & GitHub Pages Module
Task ID: T02C0C3
Module: Triển khai Landing Page & Đồng bộ trạng thái GitHub Pages
Author: Đinh Nguyễn Khánh Toàn (B25DTCN210)
"""

import base64
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Đảm bảo import được các module trong backend
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Mock jwt modules nếu môi trường chưa cài đặt PyJWT
if "jwt" not in sys.modules:
    jwt_mod = types.ModuleType("jwt")
    jwt_exceptions = types.ModuleType("jwt.exceptions")
    jwt_exceptions.ExpiredSignatureError = type("ExpiredSignatureError", (Exception,), {})
    jwt_exceptions.InvalidTokenError = type("InvalidTokenError", (Exception,), {})
    jwt_mod.exceptions = jwt_exceptions
    sys.modules["jwt"] = jwt_mod
    sys.modules["jwt.exceptions"] = jwt_exceptions

from services import github_service
from api import projects


def run_coroutine(coro):
    """Helper chạy coroutine đồng bộ mà không cần phụ thuộc vào asyncio event loop của OS."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


class TestGitHubService(unittest.TestCase):
    """Test suite cho services/github_service.py (18 Test Cases)"""

    # --- 1. Token & Header resolution ---
    def test_tc01_resolve_token_custom(self):
        """TC01 (Đúng): Trả về token tùy biến nếu được truyền vào"""
        token = github_service._resolve_token("custom_token_123")
        self.assertEqual(token, "custom_token_123")

    def test_tc02_get_headers_missing_token_raises_value_error(self):
        """TC02 (Sai): Thiếu token hoặc token placeholder mặc định phải ném ValueError"""
        with patch.object(github_service, "GITHUB_TOKEN", None):
            with self.assertRaises(ValueError):
                github_service._get_headers(token=None)

        with patch.object(github_service, "GITHUB_TOKEN", "your_github_personal_access_token_here"):
            with self.assertRaises(ValueError):
                github_service._get_headers(token=None)

    # --- 2. create_github_repo ---
    @patch("services.github_service.requests.post")
    def test_tc03_create_github_repo_success(self, mock_post):
        """TC03 (Đúng): Tạo repo thành công khi GitHub API trả về 201"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "name": "lp-test-campaign",
            "full_name": "khanhtoan10/lp-test-campaign",
            "html_url": "https://github.com/khanhtoan10/lp-test-campaign",
            "clone_url": "https://github.com/khanhtoan10/lp-test-campaign.git",
            "default_branch": "main",
        }
        mock_post.return_value = mock_response

        res = github_service.create_github_repo("lp-test-campaign", token="dummy_token")
        self.assertEqual(res["name"], "lp-test-campaign")
        self.assertEqual(res["full_name"], "khanhtoan10/lp-test-campaign")
        self.assertEqual(res["default_branch"], "main")

    @patch("services.github_service.requests.post")
    def test_tc04_create_github_repo_api_error_raises_runtime_error(self, mock_post):
        """TC04 (Sai): GitHub API trả về lỗi 422 (repo đã tồn tại) ném RuntimeError"""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"message": "name already exists on this account"}
        mock_post.return_value = mock_response

        with self.assertRaises(RuntimeError) as ctx:
            github_service.create_github_repo("lp-existing-repo", token="dummy_token")
        self.assertIn("Tạo GitHub repo thất bại (422)", str(ctx.exception))

    # --- 3. upload_file_to_repo ---
    @patch("services.github_service.requests.put")
    @patch("services.github_service.requests.get")
    def test_tc05_upload_new_file_success(self, mock_get, mock_put):
        """TC05 (Đúng): Upload file mới chưa tồn tại (GET 404, PUT 201)"""
        mock_get.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(
            status_code=201,
            json=lambda: {"commit": {"sha": "sha_new_123"}, "content": {"html_url": "url_file"}},
        )

        res = github_service.upload_file_to_repo(
            owner="owner",
            repo_name="repo",
            file_path="index.html",
            content="<html>Hello</html>",
            token="dummy_token",
        )
        self.assertEqual(res["commit_sha"], "sha_new_123")
        self.assertEqual(res["path"], "index.html")

    @patch("services.github_service.requests.put")
    @patch("services.github_service.requests.get")
    def test_tc06_upload_existing_file_overwrites_with_sha(self, mock_get, mock_put):
        """TC06 (Đúng - Ghi đè): File đã tồn tại có SHA cũ (GET 200), PUT phải kèm sha cũ"""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"sha": "old_sha_456"})
        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {"commit": {"sha": "updated_sha_789"}, "content": {"html_url": "url_file"}},
        )

        res = github_service.upload_file_to_repo(
            owner="owner",
            repo_name="repo",
            file_path="index.html",
            content="<html>Updated</html>",
            token="dummy_token",
        )
        self.assertEqual(res["commit_sha"], "updated_sha_789")
        call_kwargs = mock_put.call_args[1]
        self.assertEqual(call_kwargs["json"]["sha"], "old_sha_456")

    @patch("services.github_service.requests.put")
    @patch("services.github_service.requests.get")
    def test_tc07_upload_binary_image_content(self, mock_get, mock_put):
        """TC07 (Biên): Upload dữ liệu dạng bytes (ảnh nhị phân) được encode Base64 chuẩn xác"""
        mock_get.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(
            status_code=201,
            json=lambda: {"commit": {"sha": "sha_img"}, "content": {"html_url": "url_img"}},
        )

        image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        github_service.upload_file_to_repo(
            owner="owner",
            repo_name="repo",
            file_path="images/banner.png",
            content=image_bytes,
            token="dummy_token",
        )
        call_kwargs = mock_put.call_args[1]
        expected_base64 = base64.b64encode(image_bytes).decode("utf-8")
        self.assertEqual(call_kwargs["json"]["content"], expected_base64)

    @patch("services.github_service.requests.put")
    @patch("services.github_service.requests.get")
    def test_tc08_upload_file_api_failure_raises_runtime_error(self, mock_get, mock_put):
        """TC08 (Sai): GitHub API từ chối PUT (403/500) ném RuntimeError"""
        mock_get.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(status_code=403, text="Forbidden", json=lambda: {"message": "Forbidden"})

        with self.assertRaises(RuntimeError) as ctx:
            github_service.upload_file_to_repo(
                owner="owner", repo_name="repo", file_path="index.html", content="test", token="dummy_token"
            )
        self.assertIn("Push file 'index.html' thất bại (403)", str(ctx.exception))

    # --- 4. push_landing_page_assets ---
    @patch("services.github_service.upload_file_to_repo")
    def test_tc09_push_landing_page_assets_with_images(self, mock_upload):
        """TC09 (Đúng): Đẩy index.html kèm danh sách ảnh phụ trợ"""
        mock_upload.side_effect = [
            {"path": "images/hero.jpg", "commit_sha": "sha_1"},
            {"path": "index.html", "commit_sha": "sha_2"},
        ]
        images = [{"path": "images/hero.jpg", "content": b"fake_data"}]
        res = github_service.push_landing_page_assets(
            owner="owner", repo_name="repo", html_content="<h1>Test</h1>", images=images, token="dummy_token"
        )
        self.assertEqual(len(res["uploaded_files"]), 2)
        self.assertEqual(res["commit_sha"], "sha_2")

    @patch("services.github_service.upload_file_to_repo")
    def test_tc10_push_landing_page_assets_no_images(self, mock_upload):
        """TC10 (Biên): Đẩy landing page khi images=None chỉ đẩy 1 file index.html"""
        mock_upload.return_value = {"path": "index.html", "commit_sha": "sha_single"}
        res = github_service.push_landing_page_assets(
            owner="owner", repo_name="repo", html_content="<h1>Only HTML</h1>", images=None, token="dummy_token"
        )
        self.assertEqual(res["uploaded_files"], ["index.html"])
        self.assertEqual(res["commit_sha"], "sha_single")

    # --- 5. enable_github_pages ---
    @patch("services.github_service.requests.post")
    def test_tc11_enable_github_pages_created_201(self, mock_post):
        """TC11 (Đúng): Bật GitHub Pages thành công (HTTP 201) trả về Pages URL"""
        mock_post.return_value = MagicMock(status_code=201)
        url = github_service.enable_github_pages("MyOwner", "my-repo", token="dummy_token")
        self.assertEqual(url, "https://myowner.github.io/my-repo")

    @patch("services.github_service.requests.post")
    def test_tc12_enable_github_pages_already_enabled_409(self, mock_post):
        """TC12 (Đúng - Đã bật): Bật GitHub Pages khi đã bật từ trước (HTTP 409 Conflict) coi là thành công"""
        mock_post.return_value = MagicMock(status_code=409)
        url = github_service.enable_github_pages("MyOwner", "my-repo", token="dummy_token")
        self.assertEqual(url, "https://myowner.github.io/my-repo")

    @patch("services.github_service.requests.post")
    def test_tc13_enable_github_pages_error_raises_runtime_error(self, mock_post):
        """TC13 (Sai): Bật GitHub Pages thất bại (HTTP 404/403) ném RuntimeError"""
        mock_post.return_value = MagicMock(
            status_code=403, json=lambda: {"message": "Upgrade to GitHub Pro to use Pages with private repos"}
        )
        with self.assertRaises(RuntimeError) as ctx:
            github_service.enable_github_pages("owner", "repo", token="dummy_token")
        self.assertIn("Bật GitHub Pages thất bại (403)", str(ctx.exception))

    # --- 6. get_github_pages_build_status ---
    @patch("services.github_service.requests.get")
    def test_tc14_get_pages_status_built(self, mock_get):
        """TC14 (Đúng): Build hoàn thành, status='built'"""
        site_res = MagicMock(status_code=200, json=lambda: {"html_url": "https://owner.github.io/repo/"})
        build_res = MagicMock(status_code=200, json=lambda: {"status": "built", "error": {}})
        mock_get.side_effect = [site_res, build_res]

        res = github_service.get_github_pages_build_status("owner", "repo", token="dummy_token")
        self.assertEqual(res["status"], "built")
        self.assertEqual(res["html_url"], "https://owner.github.io/repo/")
        self.assertIsNone(res["error"])

    @patch("services.github_service.requests.get")
    def test_tc15_get_pages_status_building_on_404(self, mock_get):
        """TC15 (Đúng - Đang build): Build chưa khởi tạo (HTTP 404), trả về building"""
        site_res = MagicMock(status_code=200, json=lambda: {"html_url": "https://owner.github.io/repo/"})
        build_res = MagicMock(status_code=404)
        mock_get.side_effect = [site_res, build_res]

        res = github_service.get_github_pages_build_status("owner", "repo", token="dummy_token")
        self.assertEqual(res["status"], "building")
        self.assertIsNone(res["error"])

    @patch("services.github_service.requests.get")
    def test_tc16_get_pages_status_errored(self, mock_get):
        """TC16 (Sai - Lỗi build): GitHub Pages build lỗi trả về errored kèm thông báo"""
        site_res = MagicMock(status_code=200, json=lambda: {"html_url": "https://owner.github.io/repo/"})
        build_res = MagicMock(
            status_code=200,
            json=lambda: {"status": "errored", "error": {"message": "Page build failed: invalid markdown"}},
        )
        mock_get.side_effect = [site_res, build_res]

        res = github_service.get_github_pages_build_status("owner", "repo", token="dummy_token")
        self.assertEqual(res["status"], "errored")
        self.assertEqual(res["error"], "Page build failed: invalid markdown")

    def test_tc17_get_pages_status_mock_mode_without_token(self):
        """TC17 (Biên - Mock Mode): Khi không có token, trả về mock built an toàn"""
        with patch.object(github_service, "GITHUB_TOKEN", None):
            res = github_service.get_github_pages_build_status("owner", "repo", token=None)
            self.assertEqual(res["status"], "built")
            self.assertEqual(res["html_url"], "https://owner.github.io/repo/")

    # --- 7. wait_for_github_pages_built ---
    @patch("services.github_service.time.sleep")
    @patch("services.github_service.get_github_pages_build_status")
    def test_tc18_wait_pages_built_success_after_polling(self, mock_status, mock_sleep):
        """TC18 (Đúng): Polling từ building sang built thành công"""
        mock_status.side_effect = [
            {"status": "building", "html_url": "url", "error": None},
            {"status": "built", "html_url": "url", "error": None},
        ]
        res = github_service.wait_for_github_pages_built("owner", "repo", token="dummy_token", timeout_seconds=10)
        self.assertEqual(res["status"], "built")
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("services.github_service.get_github_pages_build_status")
    def test_tc19_wait_pages_built_errored_aborts(self, mock_status):
        """TC19 (Sai): Build báo errored phải ném RuntimeError dừng chờ"""
        mock_status.return_value = {"status": "errored", "html_url": "url", "error": "Build failed"}
        with self.assertRaises(RuntimeError) as ctx:
            github_service.wait_for_github_pages_built("owner", "repo", token="dummy_token", timeout_seconds=10)
        self.assertIn("GitHub Pages build lỗi: Build failed", str(ctx.exception))

    @patch("services.github_service.time.sleep")
    @patch("services.github_service.get_github_pages_build_status")
    def test_tc20_wait_pages_built_timeout_raises_timeout_error(self, mock_status, mock_sleep):
        """TC20 (Biên - Hết thời gian chờ): Luôn ở trạng thái building quá timeout ném TimeoutError"""
        mock_status.return_value = {"status": "building", "html_url": "url", "error": None}
        with self.assertRaises(TimeoutError) as ctx:
            github_service.wait_for_github_pages_built(
                "owner", "repo", token="dummy_token", timeout_seconds=0.01, poll_interval=0.01
            )
        self.assertIn("Hết thời gian chờ GitHub Pages build xong", str(ctx.exception))


class TestProjectsDeployAPI(unittest.TestCase):
    """Test suite cho logic Render & Deploy trong api/projects.py (12 Test Cases)"""

    # --- 1. _render_project_html ---
    def test_tc21_render_html_from_project_version_snapshot(self):
        """TC21 (Đúng): Ưu tiên lấy html_snapshot từ project_versions nếu đã có"""
        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = ("<!DOCTYPE html><html>Version Snapshot</html>",)

        project = {"id": 1, "template_id": 1, "campaign_name": "Test"}
        html = projects._render_project_html(mock_db, project)
        self.assertEqual(html, "<!DOCTYPE html><html>Version Snapshot</html>")

    def test_tc22_render_html_fallback_standard_tailwind(self):
        """TC22 (Đúng - Fallback): Không có version và template_id=None sinh HTML chuẩn TailwindCSS"""
        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = None

        project = {
            "id": 99,
            "template_id": None,
            "campaign_name": "Chiến dịch Mùa Hè",
            "product_name": "Kem Chống Nắng",
            "product_description": "Bảo vệ da tối ưu",
            "price": 199000,
        }
        html = projects._render_project_html(mock_db, project)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Chiến dịch Mùa Hè", html)
        self.assertIn("Bảo vệ da tối ưu", html)
        self.assertIn("199000", html)
        self.assertIn("tailwindcss.com", html)

    def test_tc23_render_html_with_malformed_raw_json(self):
        """TC23 (Biên): raw_json_data bị lỗi cú pháp JSON được xử lý an toàn không crash"""
        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = None

        project = {
            "id": 100,
            "template_id": None,
            "campaign_name": "Safe Campaign",
            "product_name": "Safe Product",
            "raw_json_data": "{bad_json: 123",
        }
        html = projects._render_project_html(mock_db, project)
        self.assertIn("Safe Campaign", html)

    # --- 2. POST /{project_id}/deploy Flow ---
    def test_tc24_deploy_project_full_flow_success(self):
        """TC24 (Đúng): Luồng deploy đầy đủ từ tạo repo, push code, bật pages đến cập nhật github_pages_url"""
        with patch.object(projects, "_render_project_html", return_value="<html>Landing Page HTML</html>"), \
             patch.object(projects, "create_github_repo", return_value={"full_name": "toan/lp-1-campaign", "html_url": "https://github.com/toan/lp-1-campaign"}), \
             patch.object(projects, "push_landing_page_assets", return_value={"commit_sha": "sha_success_123"}), \
             patch.object(projects, "enable_github_pages", return_value="https://toan.github.io/lp-1-campaign"), \
             patch.object(projects, "wait_for_github_pages_built", return_value={"status": "built", "html_url": "https://toan.github.io/lp-1-campaign/"}):

            mock_db = MagicMock()
            mock_db.execute.return_value.lastrowid = 10

            project = {
                "id": 1,
                "user_id": 5,
                "campaign_name": "Campaign Pro",
                "repo_url": None,
                "status": "draft",
            }

            res = run_coroutine(projects.deploy_project(project=project, db=mock_db))

            self.assertTrue(res["success"])
            self.assertEqual(res["data"]["status"], "Success")
            self.assertEqual(res["data"]["github_pages_url"], "https://toan.github.io/lp-1-campaign/")
            self.assertEqual(res["data"]["commit_sha"], "sha_success_123")

            # Kiểm tra DB execute có cập nhật cột github_pages_url
            executed_queries = [str(call[0][0]) for call in mock_db.execute.call_args_list]
            update_projects_called = any("github_pages_url = :url" in q for q in executed_queries)
            self.assertTrue(update_projects_called, "Cột github_pages_url phải được cập nhật vào database")

    def test_tc25_deploy_project_existing_repo_no_duplicate_create(self):
        """TC25 (Đúng - Re-deploy): Dự án đã có repo_url không gọi tạo repo mới"""
        with patch.object(projects, "_render_project_html", return_value="<html>Redeploy HTML</html>"), \
             patch.object(projects, "create_github_repo") as mock_create_repo, \
             patch.object(projects, "push_landing_page_assets", return_value={"commit_sha": "sha_redeploy"}), \
             patch.object(projects, "enable_github_pages", return_value="https://toan.github.io/existing-repo"), \
             patch.object(projects, "wait_for_github_pages_built", return_value={"status": "built", "html_url": "https://toan.github.io/existing-repo/"}):

            mock_db = MagicMock()
            mock_db.execute.return_value.lastrowid = 11

            project = {
                "id": 2,
                "user_id": 5,
                "campaign_name": "Campaign Existing",
                "repo_url": "https://github.com/toan/existing-repo",
                "status": "published",
            }

            res = run_coroutine(projects.deploy_project(project=project, db=mock_db))
            mock_create_repo.assert_not_called()
            self.assertTrue(res["success"])

    def test_tc26_deploy_project_failure_updates_status_failed(self):
        """TC26 (Sai - Lỗi hệ thống): Lỗi xảy ra khi deploy phải rollback và đánh dấu status='Failed'"""
        with patch.object(projects, "_render_project_html", side_effect=RuntimeError("Disk full / template missing")):
            mock_db = MagicMock()
            mock_db.execute.return_value.lastrowid = 12

            project = {"id": 3, "campaign_name": "Error Campaign", "repo_url": None}

            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                run_coroutine(projects.deploy_project(project=project, db=mock_db))

            self.assertEqual(ctx.exception.status_code, 500)
            self.assertIn("Deploy thất bại", ctx.exception.detail)
            mock_db.rollback.assert_called_once()

    # --- 3. GET /{project_id}/deploy-status Flow ---
    def test_tc27_deploy_status_not_deployed_yet(self):
        """TC27 (Biên): Dự án chưa có repo và chưa có log deploy trả về NotDeployed"""
        mock_db = MagicMock()
        mock_db.execute.return_value.mappings.return_value.first.return_value = None

        project = {"id": 10, "repo_url": None}

        res = run_coroutine(projects.get_project_deploy_status(project=project, db=mock_db))

        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["deploy_status"], "NotDeployed")
        self.assertEqual(res["data"]["pages_build_status"], "not_configured")
        self.assertFalse(res["data"]["is_built"])
        self.assertIsNone(res["data"]["github_pages_url"])

    def test_tc28_deploy_status_building_in_progress(self):
        """TC28 (Đúng - Đang build): GitHub Pages báo status='building'"""
        with patch.object(projects, "get_github_pages_build_status", return_value={"status": "building", "html_url": "https://toan.github.io/my-lp/"}):
            mock_dep = {"id": 50, "status": "Building", "commit_sha": "sha_1", "error_message": None}
            mock_db = MagicMock()
            mock_db.execute.return_value.mappings.return_value.first.return_value = mock_dep

            project = {"id": 15, "repo_url": "https://github.com/toan/my-lp"}

            res = run_coroutine(projects.get_project_deploy_status(project=project, db=mock_db))

            self.assertTrue(res["success"])
            self.assertEqual(res["data"]["deploy_status"], "Building")
            self.assertFalse(res["data"]["is_built"])
            self.assertIsNone(res["data"]["github_pages_url"])

    def test_tc29_deploy_status_built_syncs_database(self):
        """TC29 (Đúng - Build xong): GitHub Pages báo 'built' tự động đồng bộ DB sang Success và lưu URL"""
        with patch.object(projects, "get_github_pages_build_status", return_value={"status": "built", "html_url": "https://toan.github.io/my-lp/"}):
            mock_dep = {"id": 51, "status": "Building", "commit_sha": "sha_1", "error_message": None}
            mock_db = MagicMock()
            mock_db.execute.return_value.mappings.return_value.first.return_value = mock_dep

            project = {"id": 15, "repo_url": "https://github.com/toan/my-lp"}

            res = run_coroutine(projects.get_project_deploy_status(project=project, db=mock_db))

            self.assertTrue(res["success"])
            self.assertEqual(res["data"]["deploy_status"], "Success")
            self.assertTrue(res["data"]["is_built"])
            self.assertEqual(res["data"]["github_pages_url"], "https://toan.github.io/my-lp/")
            mock_db.commit.assert_called_once()

    def test_tc30_deploy_status_errored_syncs_failed_in_db(self):
        """TC30 (Sai - Build lỗi): GitHub Pages báo 'errored' cập nhật DB sang Failed kèm error_message"""
        with patch.object(projects, "get_github_pages_build_status", return_value={"status": "errored", "html_url": "https://toan.github.io/my-lp/", "error": "Jekyll build error"}):
            mock_dep = {"id": 52, "status": "Building", "commit_sha": "sha_1", "error_message": None}
            mock_db = MagicMock()
            mock_db.execute.return_value.mappings.return_value.first.return_value = mock_dep

            project = {"id": 15, "repo_url": "https://github.com/toan/my-lp"}

            res = run_coroutine(projects.get_project_deploy_status(project=project, db=mock_db))

            self.assertTrue(res["success"])
            self.assertFalse(res["data"]["is_built"])
            self.assertEqual(res["data"]["error_message"], "Jekyll build error")
            mock_db.commit.assert_called_once()

    def test_tc31_no_duplicate_routes_in_projects_py(self):
        """TC31 (Biên - Kiểm tra tĩnh): Đảm bảo không còn endpoint deploy và deploy-status bị khai báo trùng"""
        projects_file = os.path.join(BACKEND_DIR, "api", "projects.py")
        with open(projects_file, "r", encoding="utf-8") as f:
            content = f.read()

        deploy_post_count = content.count('@router.post("/{project_id}/deploy")')
        deploy_status_get_count = content.count('@router.get("/{project_id}/deploy-status")')

        self.assertEqual(deploy_post_count, 1, "Route @router.post('/{project_id}/deploy') chỉ được khai báo đúng 1 lần")
        self.assertEqual(deploy_status_get_count, 1, "Route @router.get('/{project_id}/deploy-status') chỉ được khai báo đúng 1 lần")

    def test_tc32_no_published_url_column_in_projects_py(self):
        """TC32 (Biên - Kiểm tra tên cột DB): Không còn xuất hiện cột sai published_url trong projects.py"""
        projects_file = os.path.join(BACKEND_DIR, "api", "projects.py")
        with open(projects_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("published_url", content, "Tên cột 'published_url' đã bị loại bỏ hoàn toàn, thay bằng 'github_pages_url'")


if __name__ == "__main__":
    unittest.main()
