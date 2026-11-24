"""Service kết nối Gemini API và trả về dữ liệu JSON hợp lệ cho landing page."""

import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib import error, request

from dotenv import load_dotenv

# Đảm bảo nạp đúng file backend/.env bất kể chạy từ thư mục gốc hay thư mục backend/
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

from core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

REQUIRED_FIELDS: dict[str, type] = {
    "headline": str,
    "subheadline": str,
    "features": list,
    "cta_text": str,
    "primary_color": str,
}

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class GeminiServiceError(Exception):
    """Lỗi chung khi gọi hoặc xử lý dữ liệu từ Gemini API."""


class GeminiConfigError(GeminiServiceError):
    """Lỗi thiếu hoặc sai cấu hình GEMINI_API_KEY."""


class GeminiConnectionError(GeminiServiceError):
    """Lỗi kết nối mạng hoặc HTTP error từ Gemini API."""


class GeminiResponseError(GeminiServiceError):
    """Lỗi phản hồi rỗng hoặc JSON không đúng cấu trúc yêu cầu."""


def _get_api_key() -> str:
    """Lấy GEMINI_API_KEY từ cấu hình dự án và kiểm tra tính hợp lệ."""
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise GeminiConfigError(
            "GEMINI_API_KEY chưa được cấu hình hợp lệ trong file backend/.env"
        )
    return api_key


def build_landing_page_prompt(user_prompt: str) -> str:
    """Xây dựng prompt yêu cầu Gemini sinh nội dung landing page dưới dạng JSON thuần."""
    cleaned_prompt = (user_prompt or "").strip()
    if not cleaned_prompt:
        raise ValueError("Prompt đầu vào không được để trống")

    return (
        "Bạn là chuyên gia copywriting và thiết kế landing page.\n"
        "Dựa trên mô tả sản phẩm/chiến dịch dưới đây, hãy tạo nội dung cho trang landing page "
        "và trả về DUY NHẤT một chuỗi JSON hợp lệ theo đúng cấu trúc sau:\n"
        "{\n"
        '  "headline": "Tiêu đề chính ngắn gọn, thu hút (string)",\n'
        '  "subheadline": "Tiêu đề phụ giải thích rõ giá trị sản phẩm (string)",\n'
        '  "features": [\n'
        '    "Tính năng nổi bật 1 (string)",\n'
        '    "Tính năng nổi bật 2 (string)",\n'
        '    "Tính năng nổi bật 3 (string)"\n'
        "  ],\n"
        '  "cta_text": "Nội dung nút kêu gọi hành động ngắn gọn (string)",\n'
        '  "primary_color": "Mã màu chủ đạo định dạng hex 6 ký tự, ví dụ #2563EB (string)"\n'
        "}\n\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "- Chỉ trả về JSON hợp lệ.\n"
        "- Không trả về Markdown.\n"
        "- Không sử dụng code block ```json hoặc ```.\n"
        "- Không thêm bất kỳ lời giải thích nào bên ngoài JSON.\n"
        "- Đảm bảo đầy đủ 5 trường: headline, subheadline, features, cta_text, primary_color.\n"
        "- Đúng kiểu dữ liệu: headline (string), subheadline (string), "
        "features (mảng các chuỗi string không rỗng), cta_text (string), "
        "primary_color (string mã màu hex #RRGGBB).\n\n"
        f"Mô tả yêu cầu landing page:\n{cleaned_prompt}"
    )


def validate_landing_page_json(raw_text: str) -> dict[str, Any]:
    """Parse chuỗi phản hồi từ Gemini thành JSON và kiểm tra cấu trúc, kiểu dữ liệu."""
    if raw_text is None or not str(raw_text).strip():
        raise GeminiResponseError("Gemini trả về nội dung rỗng")

    cleaned_text = str(raw_text).strip()

    # Từ chối nếu phản hồi chứa markdown code block theo đúng ràng buộc prompt
    if cleaned_text.startswith("```") or "```json" in cleaned_text.lower():
        raise GeminiResponseError(
            "Phản hồi từ Gemini chứa định dạng Markdown/code block không hợp lệ"
        )

    try:
        parsed_data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError(f"Gemini trả về JSON không hợp lệ: {exc.msg}") from exc

    if not isinstance(parsed_data, dict):
        raise GeminiResponseError("Dữ liệu JSON từ Gemini phải là một JSON object")

    # Kiểm tra thiếu trường bắt buộc
    missing_fields = [field for field in REQUIRED_FIELDS if field not in parsed_data]
    if missing_fields:
        raise GeminiResponseError(
            f"JSON từ Gemini thiếu các trường bắt buộc: {', '.join(missing_fields)}"
        )

    # Kiểm tra kiểu dữ liệu từng trường
    for field, expected_type in REQUIRED_FIELDS.items():
        value = parsed_data[field]
        if not isinstance(value, expected_type):
            raise GeminiResponseError(
                f"Trường '{field}' sai kiểu dữ liệu: mong đợi {expected_type.__name__}, "
                f"nhận được {type(value).__name__}"
            )

    # Kiểm tra giá trị rỗng cho các trường chuỗi
    for str_field in ("headline", "subheadline", "cta_text", "primary_color"):
        if not parsed_data[str_field].strip():
            raise GeminiResponseError(f"Trường '{str_field}' không được để chuỗi rỗng")

    # Kiểm tra mảng features không rỗng và mọi phần tử đều là string không rỗng
    features = parsed_data["features"]
    if not features:
        raise GeminiResponseError("Trường 'features' không được là danh sách rỗng")

    for index, item in enumerate(features):
        if not isinstance(item, str) or not item.strip():
            raise GeminiResponseError(
                f"Phần tử thứ {index} trong 'features' phải là chuỗi không rỗng"
            )

    # Kiểm tra định dạng mã màu hex cho primary_color (đồng bộ chuẩn #RRGGBB của project schema)
    primary_color = parsed_data["primary_color"].strip()
    if not HEX_COLOR_PATTERN.fullmatch(primary_color):
        raise GeminiResponseError(
            "Trường 'primary_color' phải là mã màu hex hợp lệ (ví dụ: #1A2B3C)"
        )

    return {
        "headline": parsed_data["headline"].strip(),
        "subheadline": parsed_data["subheadline"].strip(),
        "features": [item.strip() for item in features],
        "cta_text": parsed_data["cta_text"].strip(),
        "primary_color": primary_color,
    }


def _extract_text_from_gemini_response(response_payload: dict[str, Any]) -> str:
    """Trích xuất chuỗi văn bản phản hồi từ cấu trúc JSON của Gemini API."""
    candidates = response_payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise GeminiResponseError("Gemini trả về nội dung rỗng (không có candidates)")

    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise GeminiResponseError("Gemini trả về nội dung rỗng (thiếu content)")

    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise GeminiResponseError("Gemini trả về nội dung rỗng (thiếu parts)")

    text_chunks = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    combined_text = "".join(text_chunks).strip()
    if not combined_text:
        raise GeminiResponseError("Gemini trả về nội dung văn bản rỗng")

    return combined_text


def generate_landing_page_json(user_prompt: str, timeout: int = 60) -> dict[str, Any]:
    """
    Gửi prompt tới Gemini API (tự động fallback qua các model dự phòng khi gặp 503/429/404),
    nhận kết quả và trả về dict JSON đã được kiểm tra hợp lệ.

    Args:
        user_prompt: Mô tả sản phẩm hoặc yêu cầu nội dung landing page.
        timeout: Thời gian chờ tối đa (giây) khi gọi Gemini API.

    Returns:
        dict chứa 5 trường đã validate: headline, subheadline, features, cta_text, primary_color.
    """
    api_key = _get_api_key()
    prompt_text = build_landing_page_prompt(user_prompt)

    request_body = {
        "contents": [
            {
                "parts": [{"text": prompt_text}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        },
    }

    encoded_body = json.dumps(request_body).encode("utf-8")

    raw_models = (
        list(GEMINI_MODEL)
        if isinstance(GEMINI_MODEL, (list, tuple))
        else [GEMINI_MODEL]
    ) + GEMINI_FALLBACK_MODELS

    models_to_try: list[str] = []
    for m in raw_models:
        if isinstance(m, str) and m.strip() and m.strip() not in models_to_try:
            models_to_try.append(m.strip())

    last_error: GeminiConnectionError | None = None
    raw_http_body = ""

    for model_name in models_to_try:
        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent"
        )
        req = request.Request(
            url=api_url,
            data=encoded_body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw_http_body = resp.read().decode("utf-8")
                last_error = None
                break
        except error.HTTPError as exc:
            error_detail = ""
            try:
                err_json = json.loads(exc.read().decode("utf-8"))
                error_detail = err_json.get("error", {}).get("message", "")
            except Exception:
                error_detail = exc.reason or "HTTP Error"

            logger.warning(
                "Gemini model '%s' trả về HTTP %s: %s",
                model_name,
                exc.code,
                error_detail,
            )
            last_error = GeminiConnectionError(
                f"Lỗi kết nối Gemini API (HTTP {exc.code}): {error_detail}"
            )
            # Nếu quá tải (503), hết quota (429) hoặc model ngừng hỗ trợ (404) -> thử model tiếp theo
            if exc.code in (404, 429, 503):
                continue
            raise last_error from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            logger.error("Không thể kết nối tới Gemini API: %s", type(exc).__name__)
            raise GeminiConnectionError(
                f"Không thể kết nối tới Gemini API: {exc}"
            ) from exc

    if last_error is not None:
        raise last_error

    if not raw_http_body.strip():
        raise GeminiResponseError("Gemini API trả về phản hồi HTTP rỗng")

    try:
        api_response_json = json.loads(raw_http_body)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError("Không thể đọc dữ liệu phản hồi từ Gemini API") from exc

    generated_text = _extract_text_from_gemini_response(api_response_json)
    return validate_landing_page_json(generated_text)