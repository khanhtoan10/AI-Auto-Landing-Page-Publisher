"""Service render mã nguồn HTML hoàn chỉnh cho Landing Page.

Luồng sử dụng (xem ``backend/api/projects.py``):
    rendered_html = render_landing_page(project_dict)

Chiến lược render:
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
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

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


def build_template_data(project: dict) -> dict[str, Any]:
    """Chuẩn hoá dữ liệu project thành bộ biến cho template."""
    raw = _parse_raw_json(project.get("raw_json_data"))

    brand_name = _first(
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
        "image_url": _first(project.get("image_url"), raw.get("image_url"), raw.get("hero_image_url")),
        "features": _first(raw.get("features_heading"), "Vì sao nên chọn chúng tôi?"),
        "features_description": _first(
            raw.get("features_description"),
            "Những giá trị khác biệt chỉ có tại sản phẩm lần này.",
        ),
        "feature_items": features,
        "social_facebook": _first(project.get("facebook_url"), raw.get("social_facebook")),
        "social_tiktok": _first(project.get("tiktok_url"), raw.get("social_tiktok")),
        "social_instagram": _first(project.get("instagram_url"), raw.get("social_instagram")),
        "social_zalo": _first(raw.get("social_zalo")),
        "repo_url": _first(project.get("repo_url")),
        "github_pages_url": _first(project.get("github_pages_url")),
        "has_social": any(
            _first(
                project.get("facebook_url"),
                project.get("tiktok_url"),
                project.get("instagram_url"),
                raw.get("social_facebook"),
                raw.get("social_tiktok"),
                raw.get("social_instagram"),
            )
        ),
        "year": 2025,
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
  <title>{{ data.headline }} - {{ data.brand_name }}</title>
  <meta name="description" content="{{ data.subheadline }}"/>
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
            return template.render(data=data, title=data["brand_name"])
        except Exception:  # pragma: no cover - template do người dùng cung cấp
            logger.exception("Khong the render template '%s', dung template mac dinh", template_name)

    return _fallback_template().render(data=data)
