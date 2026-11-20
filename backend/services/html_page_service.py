"""Sinh file index.html hoàn chỉnh từ template người dùng đã chọn.

Luồng xử lý:
1. Nhận dữ liệu JSON trả về từ Gemini, liên kết mạng xã hội và hình ảnh.
2. Kiểm tra, làm sạch và escape/sanitize dữ liệu theo từng ngữ cảnh (HTML text,
   HTML attribute, URL, đường dẫn ảnh, mã màu CSS).
3. Render template HTML người dùng đã chọn thông qua Jinja2 autoescape.
4. Xuất file index.html hoàn chỉnh, không ghi đè template gốc.
"""

from __future__ import annotations

import copy
import html as html_stdlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from services.template_service import (
    BACKEND_DIR,
    TEMPLATES_DIR,
    _safe_template_name,
    render_landing_page,
    resolve_primary_color,
)

_EMPTY_TEXT = {"null", "none", "undefined", "[object object]"}
_UNRESOLVED_PLACEHOLDER = re.compile(
    r"\{\{\s*(?:data|cta|title)\b|\{%\s*(?:if|for|include|set|endif|endfor)\b"
)
_HTTP_SCHEMES = {"http", "https"}
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_SOCIAL_FIELDS = (
    "facebook_url",
    "social_facebook",
    "instagram_url",
    "instagram_link",
    "social_instagram",
    "tiktok_url",
    "tiktok_shop_link",
    "social_tiktok",
    "zalo_link",
    "social_zalo",
    "messenger_link",
    "youtube_url",
    "social_youtube",
)

_SOCIAL_ALIASES = {
    "facebook": "facebook_url",
    "facebook_url": "facebook_url",
    "social_facebook": "facebook_url",
    "instagram": "instagram_link",
    "instagram_url": "instagram_url",
    "instagram_link": "instagram_link",
    "social_instagram": "instagram_link",
    "tiktok": "tiktok_url",
    "tiktok_url": "tiktok_url",
    "tiktok_shop": "tiktok_shop_link",
    "tiktok_shop_link": "tiktok_shop_link",
    "social_tiktok": "tiktok_url",
    "zalo": "zalo_link",
    "zalo_link": "zalo_link",
    "social_zalo": "zalo_link",
    "messenger": "messenger_link",
    "messenger_link": "messenger_link",
    "youtube": "youtube_url",
    "youtube_url": "youtube_url",
    "social_youtube": "youtube_url",
    "hotline": "hotline",
}


class HtmlPageError(Exception):
    """Lỗi khi dữ liệu đầu vào, template hoặc quá trình sinh file index.html thất bại."""


class TemplateNotFoundError(HtmlPageError):
    """Không tìm thấy template HTML người dùng đã chọn."""


class HtmlWriteError(HtmlPageError):
    """Không ghi được file index.html ra ổ đĩa."""


# ── Context-aware Escape & Sanitization Helpers ──────────────────────

def escape_html_text(value: str) -> str:
    """Escape ký tự HTML đặc biệt (&, <, >, ", ') cho ngữ cảnh nội dung HTML."""
    return html_stdlib.escape(value, quote=True)


def escape_html_attr(value: str) -> str:
    """Escape giá trị dùng trong thuộc tính HTML (href, src, alt, content)."""
    escaped = html_stdlib.escape(value, quote=True)
    return escaped.replace("`", "&#96;")


def sanitize_http_url(value: Any) -> str | None:
    """Kiểm tra và chỉ giữ URL có giao thức http: hoặc https: kèm host hợp lệ.

    Từ chối javascript:, data:, vbscript:, file:, khoảng trắng/ký tự điều khiển
    và không tự ý tạo URL nếu dữ liệu đầu vào không phải URL hợp lệ.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if any(ch in text for ch in ("\x00", "\r", "\n", "\t", " ", '"', "'", "<", ">", "`")):
        return None

    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _HTTP_SCHEMES or not parsed.netloc:
        return None
    # Chặn trường hợp netloc chỉ có userinfo hoặc rỗng sau @
    hostname = parsed.hostname or ""
    if not hostname or "." not in hostname and hostname != "localhost":
        return None
    return text


def sanitize_image_src(value: Any) -> str | None:
    """Kiểm tra URL ảnh (http/https) hoặc đường dẫn ảnh tương đối an toàn trong dự án."""
    remote = sanitize_http_url(value)
    if remote:
        return remote

    if not isinstance(value, str):
        return None
    text = value.strip().replace("\\", "/")
    if not text or text.startswith("//") or ":" in text:
        return None
    if any(ch in text for ch in ("\x00", "\r", "\n", "\t", " ", '"', "'", "<", ">", "`")):
        return None

    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    if not re.fullmatch(r"[A-Za-z0-9._~/%+\-]+", text):
        return None
    return text


def sanitize_hotline(value: Any) -> str | None:
    """Chỉ giữ số điện thoại hợp lệ (chữ số, dấu +, khoảng trắng, dấu chấm/gạch ngang)."""
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    digits = re.sub(r"[^\d]", "", cleaned)
    if len(digits) < 7 or len(digits) > 15:
        return None
    if not re.fullmatch(r"[\d\s\.\-\+\(\)]+", cleaned):
        return None
    return cleaned


def _clean_text(value: Any) -> str | None:
    """Chuẩn hóa chuỗi văn bản hiển thị; loại bỏ null, undefined, dict/list."""
    if value is None or isinstance(value, (dict, list, tuple, bool)):
        return None
    text = str(value).strip()
    if not text or text.lower() in _EMPTY_TEXT:
        return None
    return text


def _clean_features_list(raw_features: Any) -> list[Any]:
    """Làm sạch danh sách tính năng từ JSON Gemini, bỏ phần tử rỗng hoặc không hợp lệ."""
    if not isinstance(raw_features, list):
        return []
    cleaned_items: list[Any] = []
    for item in raw_features:
        if isinstance(item, str):
            text = _clean_text(item)
            if text:
                cleaned_items.append(text)
        elif isinstance(item, dict):
            title = _clean_text(item.get("title") or item.get("name") or item.get("heading"))
            desc = _clean_text(item.get("description") or item.get("desc") or item.get("content"))
            icon = _clean_text(item.get("icon"))
            if title or desc:
                entry: dict[str, str] = {}
                if title:
                    entry["title"] = title
                if desc:
                    entry["description"] = desc
                if icon and re.fullmatch(r"fa-[a-z0-9-]+", icon):
                    entry["icon"] = icon
                cleaned_items.append(entry)
    return cleaned_items


def _features_heading(features: Any) -> str | None:
    if isinstance(features, list):
        parts: list[str] = []
        for item in features:
            if isinstance(item, str):
                text = _clean_text(item)
            elif isinstance(item, dict):
                text = _clean_text(
                    item.get("title") or item.get("name") or item.get("heading")
                )
            else:
                text = None
            if text:
                parts.append(text)
        return " • ".join(parts) if parts else None
    return _clean_text(features)


def _load_gemini_json(gemini_json: Any) -> dict[str, Any]:
    if gemini_json is None or gemini_json == "":
        return {}
    if isinstance(gemini_json, str):
        try:
            parsed = json.loads(gemini_json)
        except json.JSONDecodeError as exc:
            raise HtmlPageError("JSON Gemini không hợp lệ, không thể sinh index.html") from exc
        if not isinstance(parsed, dict):
            raise HtmlPageError("JSON Gemini phải là một JSON object")
        return parsed
    if isinstance(gemini_json, dict):
        return copy.deepcopy(gemini_json)
    raise HtmlPageError("JSON Gemini phải là một JSON object")


def _parse_existing_raw(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _apply_social(target: dict[str, Any], social_links: dict[str, Any] | None) -> None:
    if not social_links:
        return
    if not isinstance(social_links, dict):
        raise HtmlPageError("Dữ liệu mạng xã hội phải là object")
    for key, raw_value in social_links.items():
        field = _SOCIAL_ALIASES.get(str(key).strip().lower())
        if field is None:
            continue
        if field == "hotline":
            target[field] = sanitize_hotline(raw_value)
            continue
        target[field] = sanitize_http_url(raw_value)


def _sanitize_project_urls(project: dict[str, Any]) -> None:
    for field in _SOCIAL_FIELDS:
        if field in project:
            project[field] = sanitize_http_url(project.get(field))

    facebook = project.get("facebook_url") or project.get("social_facebook")
    if facebook:
        project["facebook_url"] = facebook
        project["social_facebook"] = facebook

    instagram = (
        project.get("instagram_link")
        or project.get("instagram_url")
        or project.get("social_instagram")
    )
    if instagram:
        project["instagram_link"] = instagram
        project["instagram_url"] = instagram
        project["social_instagram"] = instagram

    tiktok = (
        project.get("tiktok_url")
        or project.get("tiktok_shop_link")
        or project.get("social_tiktok")
    )
    if tiktok:
        project["tiktok_url"] = tiktok
        project["social_tiktok"] = tiktok
        if project.get("tiktok_shop_link"):
            project["tiktok_shop_link"] = project["tiktok_shop_link"]

    zalo = project.get("zalo_link") or project.get("social_zalo")
    if zalo:
        project["zalo_link"] = zalo
        project["social_zalo"] = zalo

    youtube = project.get("youtube_url") or project.get("social_youtube")
    if youtube:
        project["youtube_url"] = youtube
        project["social_youtube"] = youtube

    if "image_url" in project:
        project["image_url"] = sanitize_image_src(project.get("image_url"))
    if "hotline" in project:
        project["hotline"] = sanitize_hotline(project.get("hotline"))


def _pick_image(*candidates: Any) -> str | None:
    for candidate in candidates:
        if isinstance(candidate, list):
            for item in candidate:
                src = _pick_image(item)
                if src:
                    return src
            continue
        if isinstance(candidate, dict):
            src = _pick_image(
                candidate.get("url"),
                candidate.get("src"),
                candidate.get("image_url"),
                candidate.get("path"),
            )
            if src:
                return src
            continue
        src = sanitize_image_src(candidate)
        if src:
            return src
    return None


def _resolve_output_path(output_path: str | Path | None) -> Path:
    if output_path is None:
        path = (BACKEND_DIR / "generated" / "index.html").resolve()
    else:
        raw = Path(output_path)
        path = raw.resolve() if raw.is_absolute() else (BACKEND_DIR / raw).resolve()
        if path.suffix == "" or path.is_dir():
            path = path / "index.html"
    if path.name.lower() != "index.html":
        raise HtmlWriteError("File sinh ra phải có tên index.html")

    templates_root = TEMPLATES_DIR.resolve()
    if path == templates_root or templates_root in path.parents:
        raise HtmlWriteError("Không được ghi đè thư mục template gốc")
    return path


def _resolve_selected_template(template_name: str | None, raw: dict[str, Any]) -> str:
    for candidate in (
        template_name,
        raw.get("template_file"),
        raw.get("template_path"),
        raw.get("template"),
    ):
        safe_name = _safe_template_name(candidate)
        if safe_name:
            return safe_name
    raise TemplateNotFoundError("Không tìm thấy template HTML đã chọn trong backend/templates")


def build_page_project(
    gemini_json: Any = None,
    *,
    template_name: str | None = None,
    social_links: dict[str, Any] | None = None,
    image_url: Any = None,
    project: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Gộp dữ liệu JSON Gemini, mạng xã hội và hình ảnh thành dict chuẩn hóa để render.

    Không làm thay đổi các object dữ liệu đầu vào.
    """
    content = _load_gemini_json(gemini_json)
    base = copy.deepcopy(project) if isinstance(project, dict) else {}
    raw = _parse_existing_raw(base.get("raw_json_data"))

    # 1. Xử lý các trường văn bản từ Gemini JSON
    for key in (
        "headline",
        "subheadline",
        "cta_text",
        "product_description",
        "brand_name",
        "campaign_name",
        "hero_badge",
        "features_description",
    ):
        text = _clean_text(content.get(key))
        if text is not None:
            raw[key] = text

    if "features" in content:
        cleaned_features = _clean_features_list(content.get("features"))
        if cleaned_features:
            raw["features"] = cleaned_features
            heading = _features_heading(cleaned_features)
            if heading:
                raw["features_heading"] = heading
        else:
            raw.pop("features", None)
            raw.pop("features_heading", None)

    # 2. Xử lý màu chủ đạo (chỉ chấp nhận mã màu hex hoặc theme hợp lệ)
    color = _clean_text(content.get("primary_color"))
    if color:
        resolved_color = resolve_primary_color(color)
        if _HEX_COLOR_RE.fullmatch(resolved_color):
            raw["primary_color"] = resolved_color

    # 3. Xử lý liên kết mạng xã hội (ưu tiên tham số social_links, sau đó đến JSON/project)
    for field in _SOCIAL_FIELDS:
        if field in content:
            raw[field] = content.get(field)
    if isinstance(content.get("social_links"), dict):
        _apply_social(raw, content.get("social_links"))

    _apply_social(raw, social_links)
    for field in _SOCIAL_FIELDS:
        if field in raw:
            base[field] = raw.get(field)

    if "hotline" in raw and isinstance(social_links, dict) and "hotline" in {
        str(key).strip().lower() for key in social_links
    }:
        base["hotline"] = raw.get("hotline")

    # 4. Xử lý dữ liệu hình ảnh (không tự tạo URL ảnh khi đầu vào không có)
    image = _pick_image(
        image_url,
        content.get("image_url"),
        content.get("image"),
        content.get("hero_image"),
        content.get("images"),
        base.get("image_url"),
        raw.get("image_url"),
    )
    if image:
        raw["image_url"] = image
        base["image_url"] = image
    else:
        raw.pop("image_url", None)
        base["image_url"] = None

    # 5. Sanitize toàn bộ URL trước khi đưa sang tầng render
    _sanitize_project_urls(base)
    _sanitize_project_urls(raw)

    if raw.get("primary_color") and not _clean_text(base.get("color_theme")):
        base["color_theme"] = raw["primary_color"]

    selected = _resolve_selected_template(template_name, raw)
    raw["template_file"] = selected
    base["raw_json_data"] = raw

    if not _clean_text(base.get("product_name")):
        base["product_name"] = _clean_text(raw.get("headline")) or "Landing Page"
    if not _clean_text(base.get("campaign_name")):
        base["campaign_name"] = base["product_name"]
    return base, selected


def generate_index_html(
    gemini_json: Any = None,
    *,
    template_name: str | None = None,
    social_links: dict[str, Any] | None = None,
    image_url: Any = None,
    project: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Render template đã chọn với dữ liệu đã làm sạch và xuất ra file index.html.

    Returns:
        dict gồm các khóa: ``html``, ``output_path`` và ``template_name``.
    """
    page_project, selected = build_page_project(
        gemini_json,
        template_name=template_name,
        social_links=social_links,
        image_url=image_url,
        project=project,
    )

    try:
        html = render_landing_page(page_project, template_path=selected)
    except Exception as exc:
        raise HtmlPageError("Không sinh được HTML từ template đã chọn") from exc

    if not isinstance(html, str) or "<html" not in html.lower():
        raise HtmlPageError("Template không tạo ra tài liệu HTML hoàn chỉnh")
    if _UNRESOLVED_PLACEHOLDER.search(html):
        raise HtmlPageError("Template còn placeholder chưa được xử lý")

    destination = _resolve_output_path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise HtmlWriteError(f"Không ghi được file index.html: {exc.strerror or exc}") from exc

    return {
        "html": html,
        "output_path": str(destination),
        "template_name": selected,
    }