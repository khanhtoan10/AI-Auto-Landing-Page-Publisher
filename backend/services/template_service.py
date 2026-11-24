"""Service xử lý nghiệp vụ liên quan đến Template.

File này gồm 2 nhóm chức năng:

1. Đọc dữ liệu Template từ database (bảng ``templates``) qua SQLAlchemy Session
   - ``get_all_templates``    : danh sách toàn bộ template
   - ``get_template_by_id``   : lấy 1 template theo ID
   - ``serialize_template``   : chuyển ORM Model -> Pydantic Schema

2. Render mã nguồn HTML hoàn chỉnh cho Landing Page
   - ``render_landing_page``  : dùng bởi ``backend/api/projects.py`` (PUT /projects/{id}
     và POST /projects/{id}/preview) để render lại toàn bộ HTML sau khi người dùng
     chỉnh sửa text, giá, link social, màu chủ đạo, link ảnh.

Chiến lược render (nhóm 2):
1. Nếu dự án chỉ định một template Jinja2 hợp lệ trong ``backend/templates/``
   (qua ``raw_json_data.template_file`` hoặc tham số ``template_path``),
   render template đó với bộ dữ liệu chuẩn hoá.
2. Nếu không, dùng template Tailwind CSS mặc định tối ưu tỉ lệ chuyển đổi
   (responsive, có hero, bảng giá, tính năng, cam kết chất lượng và social).
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.template import Template
from schemas.template import TemplateItem


def serialize_template(template: Template) -> TemplateItem:
    """Chuyển đổi ORM Model Template thành Pydantic Schema TemplateItem.
    
    Ánh xạ cột thumbnail_url từ database sang trường thumbnail theo đúng API contract.
    Loại bỏ các trường nội bộ không cần thiết như file_path và created_at.
    """
    return TemplateItem(
        id=template.id,
        name=template.name,
        description=template.description,
        thumbnail=template.thumbnail_url,
        placeholders=template.placeholders,
    )


def get_all_templates(db: Session) -> List[TemplateItem]:
    """Lấy danh sách tất cả các Template từ database.
    
    Trả về danh sách đối tượng TemplateItem đã được serialize và parse placeholders.
    """
    stmt = select(Template).order_by(Template.id.asc())
    templates = db.scalars(stmt).all()
    return [serialize_template(t) for t in templates]


def get_template_by_id(db: Session, template_id: int) -> Optional[TemplateItem]:
    """Truy vấn một Template theo ID.
    
    Trả về TemplateItem nếu tìm thấy, hoặc None nếu không tồn tại trong database.
    """
    template = db.get(Template, template_id)
    if template is None:
        return None
    return serialize_template(template)


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BACKEND_DIR / "templates"

DEFAULT_PRIMARY_COLOR = "#4F46E5"

# Bảng ánh xạ tên bộ màu (dùng ở form tạo dự án) sang mã hex hợp lệ.
THEME_COLORS = {
    "indigo": "#4F46E5",
    "emerald": "#059669",
    "amber": "#D97706",
    "dark": "#0F172A",
    "blue": "#2563EB",
    "violet": "#7C3AED",
    "rose": "#E11D48",
    "teal": "#0D9488",
    "slate": "#334155",
}

DEFAULT_FEATURES = [
    (
        "Chất lượng vượt trội",
        "Quy trình kiểm soát nghiêm ngặt, sản phẩm hoàn thiện chỉn chu tới từng chi tiết.",
        "fa-award",
    ),
    (
        "Giao hàng siêu tốc",
        "Đóng gói cẩn thận và giao tận nơi trên toàn quốc chỉ trong 2 giờ nội thành.",
        "fa-truck-fast",
    ),
    (
        "Cam kết đổi trả",
        "Hỗ trợ đổi trả trong 30 ngày nếu sản phẩm không đúng mô tả hoặc có lỗi từ nhà sản xuất.",
        "fa-shield-halved",
    ),
    (
        "Hỗ trợ tận tâm",
        "Đội ngũ tư vấn phản hồi nhanh qua mọi kênh, đồng hành cùng bạn trước và sau khi mua.",
        "fa-headset",
    ),
]

_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ── Helpers ──────────────────────────────────────────────────────────
def _first(*values: Any) -> str:
    """Trả về giá trị chuỗi đầu tiên không rỗng."""
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_raw_json(raw: Any) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.,-]", "", value)
        if not cleaned:
            return None
        # Hỗ trợ cả 1.250.000 và 1,250,000.00
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", "")
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def format_vnd(value: Any) -> str:
    """Định dạng giá tiền Việt Nam, ví dụ ``1.250.000 ₫``."""
    amount = _to_decimal(value)
    if amount is None:
        return "Liên hệ"
    if amount < 0:
        return "Liên hệ"
    integral = amount.to_integral_value()
    if amount == integral:
        formatted = f"{int(integral):,}".replace(",", ".")
    else:
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} ₫"


def resolve_primary_color(value: Any) -> str:
    """Chuẩn hoá ``color_theme`` (hex hoặc tên bộ màu) về mã hex 6 ký tự."""
    text = _first(value)
    if not text:
        return DEFAULT_PRIMARY_COLOR
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", text):
        return ("#" + "".join(ch * 2 for ch in text[1:])).upper()
    return THEME_COLORS.get(text.lower(), DEFAULT_PRIMARY_COLOR)


def _shade(hex_color: str, factor: float) -> str:
    """Làm sáng (factor > 0) hoặc làm tối (factor < 0) một mã màu hex."""
    raw = hex_color.lstrip("#")
    channels = [int(raw[i : i + 2], 16) for i in (0, 2, 4)]
    if factor >= 0:
        channels = [round(c + (255 - c) * factor) for c in channels]
    else:
        channels = [round(c * (1 + factor)) for c in channels]
    return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in channels)


def _normalize_features(raw_features: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    icons = [item[2] for item in DEFAULT_FEATURES]

    if isinstance(raw_features, list):
        for index, feature in enumerate(raw_features[:6]):
            if isinstance(feature, dict):
                title = _first(feature.get("title"), feature.get("name"), feature.get("heading"))
                description = _first(
                    feature.get("description"), feature.get("desc"), feature.get("content")
                )
                icon = _first(feature.get("icon"))
            else:
                title = _first(feature)
                description = ""
                icon = ""
            if not title and not description:
                continue
            items.append(
                {
                    "title": title or DEFAULT_FEATURES[0][0],
                    "description": description or "Thông tin chi tiết sẽ được cập nhật sớm.",
                    "icon": icon if re.fullmatch(r"fa-[a-z0-9-]+", icon or "") else icons[index % len(icons)],
                }
            )

    if not items:
        items = [
            {"title": title, "description": description, "icon": icon}
            for title, description, icon in DEFAULT_FEATURES
        ]
    return items

def _safe_http_url(value: Any) -> str:
    """Chỉ giữ URL http:// hoặc https:// hợp lệ, loại bỏ javascript:/data:."""
    text = _first(value)
    if not text or any(ch in text for ch in ("\x00", "\r", "\n", "\t", " ", '"', "'", "<", ">")):
        return ""
    lower = text.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        return ""
    return text


def _safe_image_url(value: Any) -> str:
    """Giữ URL ảnh http/https hoặc đường dẫn ảnh nội bộ an toàn."""
    http_url = _safe_http_url(value)
    if http_url:
        return http_url
    text = _first(value).replace("\\", "/")
    if not text or text.startswith("//") or ":" in text or ".." in text.split("/"):
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._~/%+\-]+", text):
        return ""
    return text


def _safe_hotline(value: Any) -> str:
    text = _first(value)
    if not text or not re.fullmatch(r"[\d\s\.\-\+\(\)]+", text):
        return ""
    digits = re.sub(r"\D", "", text)
    return text if 7 <= len(digits) <= 15 else ""


def _clean_str(value: Any) -> str:
    """Loại bỏ ký tự xuống dòng, tab, khoảng trắng thừa."""
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _clean_description(text: Any, max_len: int = 160) -> str:
    """Làm sạch description và cắt tại ranh giới từ tối đa max_len ký tự."""
    cleaned = _clean_str(text)
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned

    cutoff = max_len - 3
    truncated = cleaned[:cutoff]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "..."


def build_template_data(project: dict) -> dict[str, Any]:
    """Chuẩn hoá dữ liệu project thành bộ biến cho template."""
    raw = _parse_raw_json(project.get("raw_json_data"))

    brand_name = _first(
        project.get("brand_name"),
        project.get("product_name"),
        raw.get("brand_name"),
        raw.get("product_name"),
        project.get("campaign_name"),
        "Thương hiệu của bạn",
    )
    campaign_name = _first(project.get("campaign_name"), raw.get("campaign_name"), brand_name)
    description = _first(
        project.get("product_description"),
        raw.get("product_description"),
        raw.get("description"),
        raw.get("subheadline"),
        f"{brand_name} mang tới giải pháp chất lượng cao, được hàng ngàn khách hàng tin chọn.",
    )
    headline = _first(raw.get("headline"), brand_name)
    subheadline = _first(raw.get("subheadline"), description)
    cta_text = _first(raw.get("cta_text"), raw.get("cta"), "Đặt Hàng Ngay")
    hero_badge = _first(raw.get("hero_badge"), f"Chiến dịch {campaign_name}")

    price_value = project.get("price")
    if price_value is None:
        price_value = raw.get("price", raw.get("sale_price"))
    price_display = format_vnd(price_value)

    primary_color = resolve_primary_color(
        project.get("color_theme") or raw.get("primary_color") or raw.get("color_theme")
    )

    features = _normalize_features(raw.get("features"))

    # --- 1. SEO Title ---
    # Thứ tự ưu tiên: raw.seo_title -> campaign_name -> product_name -> kết hợp brand_name -> brand_name -> "Landing Page"
    raw_seo_title = _clean_str(raw.get("seo_title"))
    if raw_seo_title:
        seo_title = raw_seo_title
    else:
        cand_name = _clean_str(
            _first(project.get("campaign_name"), raw.get("campaign_name"))
        ) or _clean_str(
            _first(project.get("product_name"), raw.get("product_name"))
        )
        b_name = _clean_str(brand_name)
        if cand_name:
            if b_name and b_name.lower() not in cand_name.lower():
                seo_title = f"{cand_name} - {b_name}"
            else:
                seo_title = cand_name
        elif b_name:
            seo_title = b_name
        else:
            seo_title = "Landing Page"

    # --- 2. SEO Description ---
    # Thứ tự ưu tiên: raw.seo_description -> project.product_description -> raw.product_description -> raw.description -> fallback
    raw_seo_desc = _first(
        raw.get("seo_description"),
        project.get("product_description"),
        raw.get("product_description"),
        raw.get("description"),
    )
    if not _clean_str(raw_seo_desc):
        target_name = _clean_str(
            _first(
                project.get("product_name"),
                raw.get("product_name"),
                project.get("campaign_name"),
                raw.get("campaign_name"),
            )
        )
        b_name = _clean_str(brand_name)
        if target_name and b_name and b_name.lower() not in target_name.lower():
            raw_seo_desc = f"{target_name} - {b_name}. Khám phá sản phẩm chất lượng cao cùng ưu đãi hấp dẫn ngay hôm nay."
        elif target_name:
            raw_seo_desc = f"{target_name} - Khám phá sản phẩm chất lượng cao cùng ưu đãi hấp dẫn ngay hôm nay."
        elif b_name:
            raw_seo_desc = f"{b_name} - Khám phá sản phẩm chất lượng cao cùng ưu đãi hấp dẫn ngay hôm nay."
        else:
            raw_seo_desc = "Khám phá các sản phẩm và dịch vụ chất lượng cao cùng nhiều ưu đãi hấp dẫn ngay hôm nay."

    seo_description = _clean_description(raw_seo_desc, 160)

    # --- 3. Open Graph Image ---
    # Thứ tự: project.image_url -> raw.image_url -> raw.hero_image_url
    og_image = _safe_image_url(
        _first(project.get("image_url"), raw.get("image_url"), raw.get("hero_image_url"))
    )

    # --- 4. Open Graph URL ---
    # URL HTTP/HTTPS tuyệt đối hợp lệ từ github_pages_url
    og_url = _safe_http_url(
        _first(project.get("github_pages_url"), raw.get("github_pages_url"))
    )

    safe_fb = _safe_http_url(_first(project.get("facebook_url"), raw.get("facebook_url"), raw.get("social_facebook")))
    safe_tt = _safe_http_url(_first(project.get("tiktok_url"), raw.get("tiktok_url"), raw.get("social_tiktok")))
    safe_tt_shop = _safe_http_url(_first(project.get("tiktok_shop_link"), raw.get("tiktok_shop_link")))
    safe_ig = _safe_http_url(_first(project.get("instagram_link"), project.get("instagram_url"), raw.get("instagram_link"), raw.get("instagram_url"), raw.get("social_instagram")))
    safe_zalo = _safe_http_url(_first(project.get("zalo_link"), raw.get("zalo_link"), raw.get("social_zalo")))
    safe_yt = _safe_http_url(_first(project.get("youtube_url"), raw.get("youtube_url"), raw.get("social_youtube")))
    safe_msg = _safe_http_url(_first(project.get("messenger_link"), raw.get("messenger_link")))
    safe_hotline = _safe_hotline(_first(project.get("hotline"), raw.get("hotline")))
    safe_hotline_href = f"tel:{re.sub(r'[^\d\+]', '', safe_hotline)}" if safe_hotline else ""

    return {
        "id": project.get("id"),
        "brand_name": brand_name,
        "campaign_name": campaign_name,
        "headline": headline,
        "subheadline": subheadline,
        "product_description": description,
        "hero_badge": hero_badge,
        "cta_text": cta_text,
        "price": price_display,
        "price_display": price_display,
        "sale_price": _first(raw.get("sale_price"), price_display),
        "original_price": _first(raw.get("original_price"), price_display),
        "discount_percent": _first(raw.get("discount_percent"), "Ưu đãi hôm nay"),
        "sold_count": _first(raw.get("sold_count"), "1.200+"),
        "primary_color": primary_color,
        "brand_dark": _shade(primary_color, -0.35),
        "brand_soft": _shade(primary_color, 0.88),
        "image_url": _safe_image_url(_first(project.get("image_url"), raw.get("image_url"), raw.get("hero_image_url"))),
        "features": _first(raw.get("features_heading"), "Vì sao nên chọn chúng tôi?"),
        "features_description": _first(
            raw.get("features_description"),
            "Những giá trị khác biệt chỉ có tại sản phẩm lần này.",
        ),
        "feature_items": features,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "og_image": og_image,
        "og_url": og_url,
        "social_facebook": safe_fb,
        "facebook_url": safe_fb,
        "social_tiktok": safe_tt or safe_tt_shop,
        "tiktok_url": safe_tt or safe_tt_shop,
        "social_instagram": safe_ig,
        "instagram_url": safe_ig,
        "social_zalo": safe_zalo,
        "social_youtube": safe_yt,
        "youtube_url": safe_yt,
        "repo_url": _safe_http_url(project.get("repo_url")),
        "github_pages_url": _safe_http_url(project.get("github_pages_url")),
        "has_social": any((safe_fb, safe_tt, safe_tt_shop, safe_ig, safe_zalo, safe_yt, safe_msg)),
        "messenger_link": safe_msg,
        "tiktok_shop_link": safe_tt_shop or safe_tt,
        "zalo_link": safe_zalo,
        "instagram_link": safe_ig,
        "hotline": safe_hotline,
        "hotline_href": safe_hotline_href,
        "cta": build_cta_context({
            "facebook_url": safe_fb,
            "messenger_link": safe_msg,
            "tiktok_shop_link": safe_tt_shop or safe_tt,
            "zalo_link": safe_zalo,
            "instagram_link": safe_ig,
            "youtube_url": safe_yt,
            "hotline": safe_hotline,
        }),
        "year": 2026,
    }


def _safe_template_name(value: Any) -> Optional[str]:
    """Kiểm tra template nằm trong ``backend/templates`` và có đuôi .html."""
    name = _first(value).replace("\\", "/")
    if name.startswith("templates/"):
        name = name[len("templates/") :]
    if not name or not re.fullmatch(r"[A-Za-z0-9_\-/]+\.html", name):
        return None
    resolved = (TEMPLATES_DIR / name).resolve()
    try:
        resolved.relative_to(TEMPLATES_DIR.resolve())
    except ValueError:
        return None
    return name if resolved.is_file() else None


def _resolve_template_name(project: dict, template_path: Optional[str]) -> Optional[str]:
    raw = _parse_raw_json(project.get("raw_json_data"))
    for candidate in (
        template_path,
        raw.get("template_file"),
        raw.get("template_path"),
        raw.get("template"),
    ):
        name = _safe_template_name(candidate)
        if name:
            return name
    return None


# ── Template mặc định tối ưu chuyển đổi ─────────────────────────────
FALLBACK_TEMPLATE = """<!DOCTYPE html>
<html lang="vi" class="scroll-smooth">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  {% include "partials/seo_meta.html" %}
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: { sans: ['Plus Jakarta Sans', 'sans-serif'] },
          colors: {
            brand: '{{ data.primary_color }}',
            brandDark: '{{ data.brand_dark }}',
            brandSoft: '{{ data.brand_soft }}'
          }
        }
      }
    };
  </script>
  <style>
    html { scroll-behavior: smooth; }
    .hero-gradient { background: radial-gradient(circle at 20% 20%, {{ data.brand_soft }} 0%, #ffffff 55%); }
    .text-balance { text-wrap: balance; }
  </style>
</head>
<body class="font-sans bg-white text-slate-800 antialiased">

  <!-- 1. Thanh điều hướng -->
  <header class="sticky top-0 z-50 bg-white/90 backdrop-blur border-b border-slate-100">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
      <a href="#" class="flex items-center gap-2.5 min-w-0">
        <span class="w-9 h-9 rounded-xl bg-brand text-white flex items-center justify-center font-extrabold shadow-lg shadow-brand/25 shrink-0">
          {{ data.brand_name[0] | upper }}
        </span>
        <span class="font-extrabold text-slate-900 truncate">{{ data.brand_name }}</span>
      </a>
      <div class="flex items-center gap-3">
        <a href="#features" class="hidden sm:inline text-sm font-semibold text-slate-600 hover:text-brand transition">Tính năng</a>
        <a href="#lien-he" class="hidden sm:inline text-sm font-semibold text-slate-600 hover:text-brand transition">Liên hệ</a>
        <a href="#dat-hang" class="inline-flex items-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl bg-brand hover:bg-brandDark text-white text-sm font-bold shadow-lg shadow-brand/25 transition">
          <i class="fa-solid fa-bag-shopping"></i>
          <span class="hidden xs:inline">{{ data.cta_text }}</span>
          <span class="xs:hidden">Mua</span>
        </a>
      </div>
    </div>
  </header>

  <!-- 2. Hero -->
  <section class="hero-gradient border-b border-slate-100">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-14 sm:py-20 grid lg:grid-cols-2 gap-10 lg:gap-14 items-center">
      <div class="space-y-6">
        <span class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brandSoft text-brandDark text-xs font-bold border border-brand/20">
          <i class="fa-solid fa-bolt text-brand"></i>
          {{ data.hero_badge }}
        </span>
        <h1 class="text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 leading-tight text-balance">
          {{ data.headline }}
        </h1>
        <p class="text-base sm:text-lg text-slate-600 leading-relaxed max-w-xl">
          {{ data.subheadline }}
        </p>
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span class="text-sm font-semibold text-slate-500">Giá niêm yết</span>
          <span class="text-3xl sm:text-4xl font-extrabold text-brand">{{ data.price }}</span>
        </div>
        <div class="flex flex-col sm:flex-row gap-3 pt-1">
          <a href="#dat-hang" class="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl bg-brand hover:bg-brandDark text-white font-bold shadow-xl shadow-brand/25 hover:scale-[1.02] active:scale-[0.98] transition">
            <span>{{ data.cta_text }}</span>
            <i class="fa-solid fa-arrow-right text-sm"></i>
          </a>
          <a href="#features" class="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 font-bold border border-slate-200 transition">
            <i class="fa-solid fa-circle-play text-brand"></i>
            <span>Tìm hiểu thêm</span>
          </a>
        </div>
        <div class="grid grid-cols-3 gap-3 pt-4 border-t border-slate-200/70 max-w-xl text-xs sm:text-sm text-slate-600 font-medium">
          <div class="flex items-center gap-2"><i class="fa-solid fa-circle-check text-brand"></i><span>Chính hãng 100%</span></div>
          <div class="flex items-center gap-2"><i class="fa-solid fa-truck-fast text-brand"></i><span>Giao nhanh 2h</span></div>
          <div class="flex items-center gap-2"><i class="fa-solid fa-rotate-left text-brand"></i><span>Đổi trả 30 ngày</span></div>
        </div>
      </div>

      <div class="relative">
        <div class="absolute -inset-3 bg-brand/10 rounded-3xl blur-2xl"></div>
        <div class="relative bg-white rounded-3xl border border-slate-200 shadow-2xl overflow-hidden">
          {% if data.image_url %}
          <img src="{{ data.image_url }}" alt="{{ data.brand_name }}" class="w-full aspect-square object-cover"/>
          {% else %}
          <div class="w-full aspect-square bg-gradient-to-br from-brandSoft to-white flex flex-col items-center justify-center gap-4">
            <span class="w-24 h-24 rounded-3xl bg-brand text-white text-4xl font-extrabold flex items-center justify-center shadow-2xl shadow-brand/30">
              {{ data.brand_name[0] | upper }}
            </span>
            <span class="text-sm font-semibold text-slate-500">{{ data.brand_name }}</span>
          </div>
          {% endif %}
          <div class="p-4 flex items-center justify-between gap-3 border-t border-slate-100">
            <div class="flex items-center gap-3 min-w-0">
              <span class="w-10 h-10 rounded-xl bg-brandSoft text-brand flex items-center justify-center shrink-0"><i class="fa-solid fa-award"></i></span>
              <div class="min-w-0">
                <p class="text-sm font-bold text-slate-800 truncate">{{ data.campaign_name }}</p>
                <p class="text-xs text-slate-500">Được tin chọn bởi {{ data.sold_count }} khách hàng</p>
              </div>
            </div>
            <span class="text-amber-500 text-sm whitespace-nowrap"><i class="fa-solid fa-star"></i> 4.9/5</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 3. Tính năng nổi bật -->
  <section id="features" class="py-16 sm:py-20 bg-slate-50">
    <div class="max-w-6xl mx-auto px-4 sm:px-6">
      <div class="max-w-2xl mx-auto text-center space-y-3 mb-10">
        <span class="text-xs font-bold uppercase tracking-widest text-brand">Điểm khác biệt</span>
        <h2 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">{{ data.features }}</h2>
        <p class="text-slate-600 leading-relaxed">{{ data.features_description }}</p>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {% for feature in data.feature_items %}
        <article class="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition">
          <span class="w-11 h-11 rounded-xl bg-brandSoft text-brand flex items-center justify-center text-lg mb-4">
            <i class="fa-solid {{ feature.icon }}"></i>
          </span>
          <h3 class="text-sm font-bold text-slate-900 mb-1.5">{{ feature.title }}</h3>
          <p class="text-sm text-slate-600 leading-relaxed">{{ feature.description }}</p>
        </article>
        {% endfor %}
      </div>
    </div>
  </section>

  <!-- 4. Giới thiệu & cam kết -->
  <section class="py-16 sm:py-20 bg-white">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 grid lg:grid-cols-2 gap-10 items-center">
      <div class="space-y-5">
        <span class="text-xs font-bold uppercase tracking-widest text-brand">Về sản phẩm</span>
        <h2 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
          {{ data.brand_name }} - lựa chọn đáng tin cậy
        </h2>
        <p class="text-slate-600 leading-relaxed whitespace-pre-line">{{ data.product_description }}</p>
        <ul class="space-y-3 text-sm text-slate-700">
          <li class="flex items-start gap-3"><i class="fa-solid fa-circle-check text-brand mt-0.5"></i><span>Thông tin sản phẩm minh bạch, đúng như mô tả.</span></li>
          <li class="flex items-start gap-3"><i class="fa-solid fa-circle-check text-brand mt-0.5"></i><span>Đội ngũ tư vấn hỗ trợ trước và sau khi mua hàng.</span></li>
          <li class="flex items-start gap-3"><i class="fa-solid fa-circle-check text-brand mt-0.5"></i><span>Cam kết bảo mật thông tin khách hàng tuyệt đối.</span></li>
        </ul>
      </div>
      <div class="bg-slate-50 rounded-2xl border border-slate-200 p-6 sm:p-8 space-y-4">
        <div class="flex items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <span class="text-sm font-semibold text-slate-600">Giá bán</span>
          <span class="text-2xl font-extrabold text-brand">{{ data.price }}</span>
        </div>
        <div class="flex items-center justify-between gap-3 text-sm text-slate-600">
          <span>Phí vận chuyển</span>
          <span class="font-semibold text-emerald-600">Miễn phí toàn quốc</span>
        </div>
        <div class="flex items-center justify-between gap-3 text-sm text-slate-600">
          <span>Bảo hành</span>
          <span class="font-semibold text-slate-800">12 tháng chính hãng</span>
        </div>
        <a id="dat-hang" href="#lien-he" class="mt-2 inline-flex w-full items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-brand hover:bg-brandDark text-white font-bold shadow-lg shadow-brand/25 transition">
          <i class="fa-solid fa-bag-shopping"></i>
          <span>{{ data.cta_text }} - {{ data.price }}</span>
        </a>
        <p class="text-xs text-slate-500 text-center">Nhân viên sẽ liên hệ xác nhận đơn hàng trong vòng 10 phút.</p>
      </div>
    </div>
  </section>

  {% if data.has_social %}
  <!-- 5. Kết nối mạng xã hội -->
  <section id="lien-he" class="py-14 sm:py-16 bg-slate-50 border-t border-slate-100">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 text-center space-y-6">
      <h2 class="text-xl sm:text-2xl font-extrabold text-slate-900">Kết nối cùng {{ data.brand_name }}</h2>
      <p class="text-sm text-slate-600">Cập nhật ưu đãi mới nhất và chia sẻ trải nghiệm cùng cộng đồng của chúng tôi.</p>
      <div class="flex flex-wrap justify-center gap-3">
        {% if data.social_facebook %}
        <a href="{{ data.social_facebook }}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white border border-slate-200 hover:border-brand hover:text-brand text-sm font-semibold text-slate-700 transition">
          <i class="fa-brands fa-facebook text-[#1877F2]"></i><span>Facebook</span>
        </a>
        {% endif %}
        {% if data.social_tiktok %}
        <a href="{{ data.social_tiktok }}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white border border-slate-200 hover:border-brand hover:text-brand text-sm font-semibold text-slate-700 transition">
          <i class="fa-brands fa-tiktok text-slate-900"></i><span>TikTok</span>
        </a>
        {% endif %}
        {% if data.social_instagram %}
        <a href="{{ data.social_instagram }}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white border border-slate-200 hover:border-brand hover:text-brand text-sm font-semibold text-slate-700 transition">
          <i class="fa-brands fa-instagram text-[#E1306C]"></i><span>Instagram</span>
        </a>
        {% endif %}
        {% if data.social_zalo %}
        <a href="{{ data.social_zalo }}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white border border-slate-200 hover:border-brand hover:text-brand text-sm font-semibold text-slate-700 transition">
          <i class="fa-solid fa-comment-dots text-[#0068FF]"></i><span>Zalo</span>
        </a>
        {% endif %}
      </div>
    </div>
  </section>
  {% endif %}

  <!-- 6. Footer -->
  {% include "partials/cta_buttons.html" %}
  <footer class="bg-slate-900 text-slate-300">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
      <div>
        <p class="font-bold text-white">{{ data.brand_name }}</p>
        <p class="text-xs text-slate-400 mt-1">© {{ data.year }} {{ data.brand_name }}. Bảo lưu mọi quyền.</p>
      </div>
      <div class="flex items-center gap-3">
        {% if data.social_facebook %}<a href="{{ data.social_facebook }}" target="_blank" rel="noopener noreferrer" class="w-9 h-9 rounded-lg bg-white/10 hover:bg-brand flex items-center justify-center transition"><i class="fa-brands fa-facebook-f text-sm"></i></a>{% endif %}
        {% if data.social_tiktok %}<a href="{{ data.social_tiktok }}" target="_blank" rel="noopener noreferrer" class="w-9 h-9 rounded-lg bg-white/10 hover:bg-brand flex items-center justify-center transition"><i class="fa-brands fa-tiktok text-sm"></i></a>{% endif %}
        {% if data.social_instagram %}<a href="{{ data.social_instagram }}" target="_blank" rel="noopener noreferrer" class="w-9 h-9 rounded-lg bg-white/10 hover:bg-brand flex items-center justify-center transition"><i class="fa-brands fa-instagram text-sm"></i></a>{% endif %}
      </div>
    </div>
  </footer>
</body>
</html>
"""


@lru_cache(maxsize=1)
def _fallback_template():
    return _ENV.from_string(FALLBACK_TEMPLATE)


def render_landing_page(project: dict, template_path: Optional[str] = None) -> str:
    """Render toàn bộ HTML của landing page từ dữ liệu project.

    Args:
        project: dict dữ liệu dòng bảng ``projects`` (có thể lẫn Decimal/datetime).
        template_path: đường dẫn template Jinja2 tuỳ chọn trong ``backend/templates``.

    Returns:
        Chuỗi HTML hoàn chỉnh, sẵn sàng ghi ra ``index.html`` và push GitHub.
    """
    if not isinstance(project, dict):
        project = dict(project)

    data = build_template_data(project)
    template_name = _resolve_template_name(project, template_path)

    if template_name:
        try:
            template = _ENV.get_template(template_name)
            return template.render(data=data, cta=data.get("cta"), title=data.get("seo_title", data["brand_name"]))
        except Exception:  # pragma: no cover - template do người dùng cung cấp
            logger.exception("Khong the render template '%s', dung template mac dinh", template_name)

    return _fallback_template().render(data=data, cta=data.get("cta"), title=data.get("seo_title", data["brand_name"]))

from services.cta_service import build_cta_context


def render_template_preview(db: Session, template_id: int) -> Optional[str]:
    template_item = db.get(Template, template_id)
    if template_item is None:
        return None
    sample_project = {
        "campaign_name": f"Chiến Dịch Mẫu - {template_item.name}",
        "brand_name": "NovaBrand Vietnam",
        "product_name": "Sản Phẩm Tiêu Biểu 2026",
        "headline": f"Giải Pháp Đột Phá - {template_item.name}",
        "subheadline": template_item.description or "Nâng tầm trải nghiệm khách hàng và bứt phá doanh số chuyển đổi tự động.",
        "product_description": template_item.description or "Giải pháp tối ưu nâng tầm trải nghiệm khách hàng hiện đại.",
        "hero_badge": "Phiên Bản Giới Hạn 2026",
        "sold_count": "2,480+",
        "price": 1290000,
        "original_price": "1.890.000đ",
        "sale_price": "1.290.000đ",
        "discount_percent": "32%",
        "features": "Công Nghệ Tiên Tiến & Hiệu Năng Vượt Trội",
        "features_description": "Thiết kế tinh tế, tốc độ xử lý vượt bậc cùng chính sách bảo hành chính hãng 24 tháng toàn quốc.",
        "cta_text": "Đăng Ký Ngay",
        "cta_url": "#cta-contact",
        "primary_color": "#2563EB",
        "color_theme": "#2563EB",
        "messenger_link": "https://m.me/novabrand.vn",
        "tiktok_shop_link": "https://www.tiktok.com/@novabrand.vn",
        "zalo_link": "https://zalo.me/0901234567",
        "instagram_link": "https://www.instagram.com/novabrand.vn",
        "hotline": "0901 234 567",
    }
    raw_path = (template_item.file_path or "").replace("\\", "/").lstrip("/")
    for prefix in ("backend/templates/", "templates/"):
        if raw_path.startswith(prefix):
            raw_path = raw_path[len(prefix):]
    return render_landing_page(sample_project, template_path=raw_path or None)