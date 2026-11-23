"""Service kết nối Gemini API và trả về dữ liệu JSON hợp lệ cho landing page."""

import json
import logging
import re
import socket
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from dotenv import load_dotenv

# Đảm bảo nạp đúng file backend/.env bất kể chạy từ thư mục gốc hay thư mục backend/
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

from core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2  # Tối đa 2 lần thử lại (tổng cộng tối đa 3 lần gọi)
RETRY_BACKOFF_SECONDS = 1.0

REQUIRED_FIELDS: dict[str, type] = {
    "headline": str,
    "subheadline": str,
    "features": list,
    "cta_text": str,
    "primary_color": str,
}

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")

QUOTA_KEYWORDS = (
    "quota",
    "rate limit",
    "rate_limit",
    "resource_exhausted",
    "resource has been exhausted",
    "too many requests",
    "exceeded your current quota",
)


class GeminiServiceError(Exception):
    """Lỗi chung khi gọi hoặc xử lý dữ liệu từ Gemini API."""

    user_message = "Không thể tạo nội dung lúc này. Vui lòng thử lại sau."
    error_code = "GEMINI_ERROR"
    retryable = False


class GeminiConfigError(GeminiServiceError):
    """Lỗi thiếu hoặc sai cấu hình GEMINI_API_KEY."""

    user_message = "Dịch vụ AI chưa được cấu hình hợp lệ. Vui lòng liên hệ quản trị viên."
    error_code = "GEMINI_CONFIG_ERROR"
    retryable = False


class GeminiQuotaError(GeminiServiceError):
    """Lỗi hết quota hoặc vượt giới hạn request từ Gemini API."""

    user_message = "AI service hiện đã vượt giới hạn sử dụng. Vui lòng thử lại sau."
    error_code = "GEMINI_QUOTA_EXCEEDED"
    retryable = False


class GeminiTimeoutError(GeminiServiceError):
    """Lỗi request tới Gemini API bị quá thời gian chờ (timeout)."""

    user_message = "AI đang xử lý quá lâu. Vui lòng thử lại sau."
    error_code = "GEMINI_TIMEOUT"
    retryable = True


class GeminiConnectionError(GeminiServiceError):
    """Lỗi kết nối mạng hoặc HTTP error từ Gemini API."""

    user_message = "Không thể tạo nội dung lúc này. Vui lòng thử lại sau."
    error_code = "GEMINI_CONNECTION_ERROR"

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class GeminiResponseError(GeminiServiceError):
    """Lỗi phản hồi rỗng hoặc JSON không đúng cấu trúc yêu cầu."""

    user_message = "AI trả về dữ liệu không hợp lệ. Vui lòng thử lại."
    error_code = "GEMINI_INVALID_RESPONSE"
    retryable = True


def _get_api_key() -> str:
    """Lấy GEMINI_API_KEY từ cấu hình dự án và kiểm tra tính hợp lệ."""
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key or api_key in ("your_gemini_api_key_here", "AIzaSyYourRealApiKeyHere"):
        raise GeminiConfigError(
            "GEMINI_API_KEY chưa được cấu hình hợp lệ trong file backend/.env"
        )
    return api_key


def _is_quota_error(status_code: int, error_status: str, error_detail: str) -> bool:
    """Nhận diện lỗi hết quota / vượt giới hạn request từ phản hồi Gemini API."""
    if status_code == 429:
        return True
    combined = f"{error_status} {error_detail}".lower()
    if status_code in (403, 429) and any(kw in combined for kw in QUOTA_KEYWORDS):
        return True
    return any(kw in combined for kw in QUOTA_KEYWORDS)


def _is_timeout_exception(exc: BaseException) -> bool:
    """Kiểm tra ngoại lệ có phải do timeout mạng / socket / urllib hay không."""
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(exc).lower() or "timeout" in str(exc).lower()


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


def _call_gemini_once(
    api_key: str,
    encoded_body: bytes,
    timeout: int,
) -> dict[str, Any]:
    """Thực hiện 1 lần gọi HTTP tới Gemini API và kiểm tra JSON trả về."""
    req = request.Request(
        url=GEMINI_API_URL,
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
    except error.HTTPError as exc:
        # Không log hoặc đưa API Key vào thông báo lỗi
        error_detail = ""
        error_status = ""
        try:
            err_json = json.loads(exc.read().decode("utf-8"))
            err_obj = err_json.get("error", {}) if isinstance(err_json, dict) else {}
            error_detail = str(err_obj.get("message", ""))
            error_status = str(err_obj.get("status", ""))
        except Exception:
            error_detail = exc.reason or "HTTP Error"

        logger.error("Gemini API trả về lỗi HTTP %s: %s", exc.code, error_detail)

        if _is_quota_error(exc.code, error_status, error_detail):
            raise GeminiQuotaError(
                f"Gemini API vượt giới hạn quota (HTTP {exc.code}): {error_detail}"
            ) from exc

        if exc.code in (408, 504):
            raise GeminiTimeoutError(
                f"Gemini API phản hồi quá thời gian chờ (HTTP {exc.code})"
            ) from exc

        # Các lỗi 5xx tạm thời phía server có thể retry; lỗi 4xx (key sai, model sai, bad request) không retry
        is_transient_5xx = 500 <= exc.code < 600
        raise GeminiConnectionError(
            f"Lỗi kết nối Gemini API (HTTP {exc.code}): {error_detail}",
            retryable=is_transient_5xx,
        ) from exc
    except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        if _is_timeout_exception(exc):
            logger.error("Kết nối tới Gemini API bị timeout sau %ss", timeout)
            raise GeminiTimeoutError(
                f"Kết nối tới Gemini API bị quá thời gian chờ ({timeout}s)"
            ) from exc

        logger.error("Không thể kết nối tới Gemini API: %s", type(exc).__name__)
        raise GeminiConnectionError(
            f"Không thể kết nối tới Gemini API: {exc}",
            retryable=True,
        ) from exc

    if not raw_http_body.strip():
        raise GeminiResponseError("Gemini API trả về phản hồi HTTP rỗng")

    try:
        api_response_json = json.loads(raw_http_body)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError("Không thể đọc dữ liệu phản hồi từ Gemini API") from exc

    generated_text = _extract_text_from_gemini_response(api_response_json)
    return validate_landing_page_json(generated_text)


def generate_landing_page_json(
    user_prompt: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """
    Gửi prompt tới Gemini API với cơ chế retry có giới hạn cho các lỗi tạm thời
    (timeout, JSON sai cấu trúc, lỗi mạng/5xx) và trả về dict JSON đã kiểm tra hợp lệ.
    """
    if timeout is None or timeout <= 0:
        raise ValueError("Thời gian chờ timeout phải lớn hơn 0 giây")
    if max_retries is None or max_retries < 0:
        raise ValueError("Số lần thử lại max_retries không được âm")

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

    total_attempts = max_retries + 1
    last_error: GeminiServiceError | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            return _call_gemini_once(
                api_key=api_key,
                encoded_body=encoded_body,
                timeout=timeout,
            )
        except GeminiServiceError as exc:
            last_error = exc
            if not exc.retryable or attempt >= total_attempts:
                if exc.retryable and attempt >= total_attempts and max_retries > 0:
                    logger.warning(
                        "Gemini API thất bại sau %s/%s lần thử (lỗi cuối: %s)",
                        attempt,
                        total_attempts,
                        exc.error_code,
                    )
                raise

            logger.warning(
                "Gemini API gặp lỗi tạm thời (%s) ở lần thử %s/%s, đang thử lại...",
                exc.error_code,
                attempt,
                total_attempts,
            )
            if RETRY_BACKOFF_SECONDS > 0:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    assert last_error is not None
    raise last_error
