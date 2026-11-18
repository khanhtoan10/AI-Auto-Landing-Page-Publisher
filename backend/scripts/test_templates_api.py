"""Script kiểm thử toàn diện cho Template API.

Kiểm thử 6 kịch bản theo đúng đặc tả yêu cầu:
  Test 1: Gọi GET /templates và xác nhận danh sách Template từ database.
  Test 2: Gọi GET /templates/1 và xác nhận trả về đúng Template ID = 1.
  Test 3: Gọi GET /templates/99999 và xác nhận trả về HTTP 404.
  Test 4: Kiểm tra trường placeholders có đúng kiểu dữ liệu JSON Array.
  Test 5: Kiểm tra trường hợp database chưa có Template (danh sách rỗng).
  Test 6: Kiểm tra trường hợp database xảy ra lỗi truy vấn (HTTP 500).
  Test 7: Kiểm tra trường hợp ID không hợp lệ (HTTP 422).
"""

import json
import os
import sys
from unittest.mock import MagicMock

# Thêm thư mục backend vào sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from core.database import get_db
from main import app

client = TestClient(app)


def print_section(title: str):
    print(f"\n{'='*70}\n[TEST RUNNER] {title}\n{'='*70}")


def check(name: str, condition: bool, detail: str):
    if not condition:
        raise AssertionError(f"FAILED [{name}]: {detail}")
    print(f"PASSED [{name}]: {detail}")


def run_all_tests():
    print_section("BẮT ĐẦU KIỂM THỬ TEMPLATE API")

    # =========================================================================
    # TEST 1: GET /templates - Lấy danh sách Template từ database
    # =========================================================================
    print_section("Test 1: GET /templates (Database thực tế)")
    res1 = client.get("/templates")
    check("Test 1 - Status Code", res1.status_code == 200, f"HTTP status code: {res1.status_code}")
    data1 = res1.json()
    check("Test 1 - Success Flag", data1.get("success") is True, "success == True")
    check("Test 1 - Message", data1.get("message") == "Lấy danh sách template thành công", f"message: {data1.get('message')}")
    check("Test 1 - Data Type", isinstance(data1.get("data"), list), "data là một danh sách (list)")
    check("Test 1 - Data Not Empty", len(data1.get("data")) > 0, f"Tìm thấy {len(data1.get('data'))} templates")

    first_item = data1["data"][0]
    expected_required_keys = {"id", "name", "description", "thumbnail", "placeholders"}
    check(
        "Test 1 - Schema Keys",
        expected_required_keys.issubset(set(first_item.keys())),
        f"Keys trả về chính xác: {list(first_item.keys())}",
    )
    print(f"Ví dụ response Test 1:\n{json.dumps(data1, ensure_ascii=False, indent=2)}")

    # =========================================================================
    # TEST 2: GET /templates/1 - Lấy chi tiết Template có ID = 1
    # =========================================================================
    print_section("Test 2: GET /templates/1 (Chi tiết template ID=1)")
    res2 = client.get("/templates/1")
    check("Test 2 - Status Code", res2.status_code == 200, f"HTTP status code: {res2.status_code}")
    data2 = res2.json()
    check("Test 2 - Success Flag", data2.get("success") is True, "success == True")
    check("Test 2 - Message", data2.get("message") == "Lấy chi tiết template thành công", f"message: {data2.get('message')}")
    item2 = data2.get("data")
    check("Test 2 - ID Match", item2.get("id") == 1, f"ID trả về: {item2.get('id')}")
    check("Test 2 - Name Match", item2.get("name") == "Modern Tech Gadget", f"Name: {item2.get('name')}")
    check(
        "Test 2 - Thumbnail Key",
        "thumbnail" in item2 and bool(item2["thumbnail"]),
        f"Thumbnail: {item2.get('thumbnail')}",
    )
    print(f"Ví dụ response Test 2:\n{json.dumps(data2, ensure_ascii=False, indent=2)}")

    # =========================================================================
    # TEST PREVIEW: GET /templates/1/preview - Render HTML thực tế
    # =========================================================================
    print_section("Test Preview: GET /templates/1/preview (Render HTML template)")
    res_prev = client.get("/templates/1/preview")
    check("Test Preview - Status Code", res_prev.status_code == 200, f"HTTP status code: {res_prev.status_code}")
    check("Test Preview - HTML Content", "<html" in res_prev.text, "Nội dung HTML thực tế được render")
    check("Test Preview - Content Length", len(res_prev.text) > 1000, f"Độ dài HTML: {len(res_prev.text)} ký tự")

    # =========================================================================
    # TEST 3: GET /templates/99999 - Không tìm thấy Template
    # =========================================================================
    print_section("Test 3: GET /templates/99999 (ID không tồn tại)")
    res3 = client.get("/templates/99999")
    check("Test 3 - Status Code", res3.status_code == 404, f"HTTP status code: {res3.status_code}")
    data3 = res3.json()
    check("Test 3 - Success Flag", data3.get("success") is False, "success == False")
    check("Test 3 - Message", data3.get("message") == "Không tìm thấy template", f"message: {data3.get('message')}")
    check("Test 3 - Data Null", data3.get("data") is None, "data == None")
    print(f"Ví dụ response Test 3:\n{json.dumps(data3, ensure_ascii=False, indent=2)}")

    # =========================================================================
    # TEST 4: Kiểm tra trường placeholders là JSON Array
    # =========================================================================
    print_section("Test 4: Kiểm tra kiểu dữ liệu của placeholders")
    placeholders_list = item2.get("placeholders")
    check("Test 4 - Is List", isinstance(placeholders_list, list), f"Kiểu dữ liệu: {type(placeholders_list)}")
    check("Test 4 - Not Empty", len(placeholders_list) > 0, f"Số lượng placeholders: {len(placeholders_list)}")
    check(
        "Test 4 - Items are strings",
        all(isinstance(x, str) for x in placeholders_list),
        f"Tất cả phần tử đều là chuỗi: {placeholders_list[:5]}...",
    )

    # =========================================================================
    # TEST 5: Trường hợp database chưa có Template nào (Empty Table)
    # =========================================================================
    print_section("Test 5: Trường hợp database chưa có Template")
    mock_empty_db = MagicMock()
    # Mock scalars(stmt).all() trả về rỗng []
    mock_empty_db.scalars.return_value.all.return_value = []
    # Mock db.get(...) trả về None
    mock_empty_db.get.return_value = None

    def override_empty_db():
        yield mock_empty_db

    app.dependency_overrides[get_db] = override_empty_db
    try:
        res5 = client.get("/templates")
        check("Test 5 - Status Code", res5.status_code == 200, f"HTTP status code: {res5.status_code}")
        data5 = res5.json()
        check("Test 5 - Success Flag", data5.get("success") is True, "success == True")
        check("Test 5 - Message", data5.get("message") == "Lấy danh sách template thành công", f"message: {data5.get('message')}")
        check("Test 5 - Empty List", data5.get("data") == [], "data là mảng rỗng []")
        print(f"Ví dụ response Test 5:\n{json.dumps(data5, ensure_ascii=False, indent=2)}")
    finally:
        app.dependency_overrides.clear()

    # =========================================================================
    # TEST 6: Trường hợp database xảy ra lỗi truy vấn (HTTP 500)
    # =========================================================================
    print_section("Test 6: Trường hợp database xảy ra lỗi truy vấn (HTTP 500)")
    mock_error_db = MagicMock()
    mock_error_db.scalars.side_effect = OperationalError("Can't connect to MySQL", {}, None)
    mock_error_db.get.side_effect = OperationalError("Table crashed", {}, None)

    def override_error_db():
        yield mock_error_db

    app.dependency_overrides[get_db] = override_error_db
    try:
        res6_list = client.get("/templates")
        check("Test 6 (List) - Status Code", res6_list.status_code == 500, f"HTTP status code: {res6_list.status_code}")
        data6_list = res6_list.json()
        check("Test 6 (List) - Success False", data6_list.get("success") is False, "success == False")
        check(
            "Test 6 (List) - Message",
            data6_list.get("message") == "Lỗi hệ thống hoặc lỗi truy vấn cơ sở dữ liệu",
            f"message: {data6_list.get('message')}",
        )
        check("Test 6 (List) - Data Null", data6_list.get("data") is None, "data == None")

        res6_detail = client.get("/templates/1")
        check("Test 6 (Detail) - Status Code", res6_detail.status_code == 500, f"HTTP status code: {res6_detail.status_code}")
        data6_detail = res6_detail.json()
        check("Test 6 (Detail) - Success False", data6_detail.get("success") is False, "success == False")
        check(
            "Test 6 (Detail) - Message",
            data6_detail.get("message") == "Lỗi hệ thống hoặc lỗi truy vấn cơ sở dữ liệu",
            f"message: {data6_detail.get('message')}",
        )
        check("Test 6 (Detail) - Data Null", data6_detail.get("data") is None, "data == None")
        print(f"Ví dụ response Test 6:\n{json.dumps(data6_list, ensure_ascii=False, indent=2)}")
    finally:
        app.dependency_overrides.clear()

    # =========================================================================
    # TEST 7: Kiểm tra trường hợp ID không hợp lệ (HTTP 422)
    # =========================================================================
    print_section("Test 7: Kiểm tra ID không hợp lệ (HTTP 422)")
    res7_str = client.get("/templates/not-a-number")
    check("Test 7 (String ID) - Status Code", res7_str.status_code == 422, f"HTTP status code for string ID: {res7_str.status_code}")

    res7_neg = client.get("/templates/-10")
    check("Test 7 (Negative ID) - Status Code", res7_neg.status_code == 422, f"HTTP status code for negative ID: {res7_neg.status_code}")

    res7_zero = client.get("/templates/0")
    check("Test 7 (Zero ID) - Status Code", res7_zero.status_code == 422, f"HTTP status code for ID=0: {res7_zero.status_code}")

    print_section("TẤT CẢ CÁC BÀI KIỂM THỬ ĐÃ ĐƯỢC VƯỢT QUA XUẤT SẮC!")


if __name__ == "__main__":
    run_all_tests()
