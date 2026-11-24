"""Bộ kiểm thử tự động toàn diện cho tính năng SEO Meta & Open Graph Integration.

Sử dụng thư viện chuẩn của Python (html.parser) kết hợp Jinja2 của dự án.
Bao gồm 6 nhóm kiểm thử:
1. Test 1: Đầy đủ dữ liệu (Full Campaign Data)
2. Test 2: Dữ liệu thiếu hoặc rỗng (Fallback & Empty Image/URL Guard)
3. Test 3: XSS & Ký tự đặc biệt (HTML Escaping & Content Security)
4. Test 4: Kiểm tra toàn bộ 6 Template + FALLBACK_TEMPLATE (Không trùng thẻ, đúng cấu trúc)
5. Test 5: Thứ tự ưu tiên dữ liệu (SEO Title, Description, OG Image Priority)
6. Test 6: Kiểm tra hồi quy dữ liệu cũ (brand_name, cta, features list/string)
"""

import os
import re
import sys
from html.parser import HTMLParser

# Thiết lập đường dẫn backend
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.template_service import (
    FALLBACK_TEMPLATE,
    _ENV,
    _fallback_template,
    build_template_data,
    render_landing_page,
)


class MetaTagCounterParser(HTMLParser):
    """HTML Parser chuyên đếm và trích xuất thẻ SEO & Open Graph chuẩn xác."""

    def __init__(self):
        super().__init__()
        self.title_count = 0
        self.title_text = ""
        self.in_title = False
        self.meta_descriptions = []
        self.og_titles = []
        self.og_descriptions = []
        self.og_types = []
        self.og_images = []
        self.og_urls = []
        self.all_meta_tags = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self.title_count += 1
            self.in_title = True
        elif tag == "meta":
            self.all_meta_tags.append(attrs_dict)
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")

            if name == "description":
                self.meta_descriptions.append(content)
            if prop == "og:title":
                self.og_titles.append(content)
            elif prop == "og:description":
                self.og_descriptions.append(content)
            elif prop == "og:type":
                self.og_types.append(content)
            elif prop == "og:image":
                self.og_images.append(content)
            elif prop == "og:url":
                self.og_urls.append(content)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_text += data


def parse_html_seo(html: str) -> MetaTagCounterParser:
    parser = MetaTagCounterParser()
    parser.feed(html)
    return parser


def check(name: str, condition: bool, message: str = ""):
    if condition:
        print(f"  [PASSED] {name}: {message}")
    else:
        print(f"  [FAILED] {name}: {message}")
        raise AssertionError(f"Check failed: {name} - {message}")


def run_seo_tests():
    print("=" * 70)
    print("BẮT ĐẦU KIỂM THỬ TÍNH NĂNG AUTOMATIC SEO META & OPEN GRAPH")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # TEST 1: ĐẦY ĐỦ DỮ LIỆU
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Đầy đủ dữ liệu (Full Campaign Data) ---")
    long_desc = (
        "Khóa học lập trình trí tuệ nhân tạo chuyên sâu thế hệ mới 2026. "
        "Trang bị kiến thức toàn diện từ Machine Learning, Deep Learning tới LLM Agents và Generative AI. "
        "Thực chiến với 10 dự án thực tế doanh nghiệp cùng chuyên gia hàng đầu ngành công nghệ cao.\r\n\t"
        "Đăng ký ngay hôm nay để nhận trọn bộ học bổng 50%!"
    )
    full_project = {
        "campaign_name": "Khóa Học AI Chuyên Sâu 2026",
        "brand_name": "TechMaster AI",
        "product_name": "AI Engineer Bootcamp",
        "product_description": long_desc,
        "image_url": "https://cdn.example.com/images/hero-banner-2026.png",
        "github_pages_url": "https://techmaster.github.io/ai-bootcamp/",
        "raw_json_data": "{}",
    }

    data_1 = build_template_data(full_project)
    check("Test 1.1 - Title đúng định dạng", data_1["seo_title"] == "Khóa Học AI Chuyên Sâu 2026 - TechMaster AI", data_1["seo_title"])
    check("Test 1.2 - Description không vượt quá 160 ký tự", len(data_1["seo_description"]) <= 160, f"Độ dài: {len(data_1['seo_description'])}")
    check("Test 1.3 - Description làm sạch newlines/tabs", "\r" not in data_1["seo_description"] and "\n" not in data_1["seo_description"], "Không có ký tự điều khiển")
    check("Test 1.4 - Description cắt tại ranh giới từ và có '...'", data_1["seo_description"].endswith("..."), data_1["seo_description"])
    check("Test 1.5 - OG Image đúng", data_1["og_image"] == "https://cdn.example.com/images/hero-banner-2026.png", data_1["og_image"])
    check("Test 1.6 - OG URL đúng", data_1["og_url"] == "https://techmaster.github.io/ai-bootcamp/", data_1["og_url"])

    rendered_1 = render_landing_page(full_project, template_path="modern_tech.html")
    parser_1 = parse_html_seo(rendered_1)
    check("Test 1.7 - Có đúng 1 thẻ <title>", parser_1.title_count == 1, parser_1.title_text)
    check("Test 1.8 - <title> nội dung khớp seo_title", parser_1.title_text.strip() == data_1["seo_title"], parser_1.title_text.strip())
    check("Test 1.9 - Có đúng 1 thẻ meta description", len(parser_1.meta_descriptions) == 1, parser_1.meta_descriptions[0])
    check("Test 1.10 - Có đúng 1 og:title khớp seo_title", len(parser_1.og_titles) == 1 and parser_1.og_titles[0] == data_1["seo_title"], parser_1.og_titles[0])
    check("Test 1.11 - Có đúng 1 og:description", len(parser_1.og_descriptions) == 1 and parser_1.og_descriptions[0] == data_1["seo_description"], parser_1.og_descriptions[0])
    check("Test 1.12 - Có đúng 1 og:image", len(parser_1.og_images) == 1 and parser_1.og_images[0] == data_1["og_image"], parser_1.og_images[0])
    check("Test 1.13 - Có đúng 1 og:url", len(parser_1.og_urls) == 1 and parser_1.og_urls[0] == data_1["og_url"], parser_1.og_urls[0])
    check("Test 1.14 - og:type là website", len(parser_1.og_types) == 1 and parser_1.og_types[0] == "website", parser_1.og_types[0])

    # -------------------------------------------------------------------------
    # TEST 2: DỮ LIỆU THIẾU HOẶC RỖNG
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Dữ liệu thiếu hoặc rỗng (Fallback & Guards) ---")
    sparse_project = {
        "brand_name": "SoloBrand",
        "product_description": None,
        "image_url": "",
        "github_pages_url": None,
        "raw_json_data": "{}",
    }

    data_2 = build_template_data(sparse_project)
    check("Test 2.1 - Title fallback về brand_name", data_2["seo_title"] == "SoloBrand", data_2["seo_title"])
    check("Test 2.2 - Có description fallback an toàn", bool(data_2["seo_description"]) and len(data_2["seo_description"]) <= 160, data_2["seo_description"])
    check("Test 2.3 - Không chứa từ 'None' hay 'null'", "None" not in data_2["seo_title"] and "null" not in data_2["seo_title"] and "None" not in data_2["seo_description"], "Không có chuỗi rác")
    check("Test 2.4 - og_image là chuỗi rỗng khi thiếu", data_2["og_image"] == "", "og_image rỗng")
    check("Test 2.5 - og_url là chuỗi rỗng khi thiếu", data_2["og_url"] == "", "og_url rỗng")

    rendered_2 = render_landing_page(sparse_project, template_path="marketing.html")
    parser_2 = parse_html_seo(rendered_2)
    check("Test 2.6 - Không render thẻ og:image khi rỗng (không có content='')", len(parser_2.og_images) == 0, f"Số thẻ og:image: {len(parser_2.og_images)}")
    check("Test 2.7 - Không render thẻ og:url khi rỗng", len(parser_2.og_urls) == 0, f"Số thẻ og:url: {len(parser_2.og_urls)}")
    check("Test 2.8 - Không có thẻ meta nào mang content rỗng", not any(m.get("content") == "" for m in parser_2.all_meta_tags if m.get("property") in ("og:image", "og:url")), "Không có content rỗng")

    # -------------------------------------------------------------------------
    # TEST 3: XSS VÀ KÝ TỰ ĐẶC BIỆT
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: XSS và ký tự đặc biệt (Security Escaping) ---")
    xss_project = {
        "campaign_name": 'Chiến Dịch "Siêu Sale" & <script>alert("XSS")</script>',
        "brand_name": "Hacker's Hub <img src=x onerror=alert(1)>",
        "product_description": 'Mô tả có dấu ngoặc kép "VIP", dấu nháy đơn \'Pro\' & ký tự <tags> nguy hiểm.',
        "image_url": "javascript:alert('pwned')",
        "github_pages_url": "data:text/html,<script>alert(1)</script>",
        "raw_json_data": "{}",
    }

    data_3 = build_template_data(xss_project)
    check("Test 3.1 - Loại bỏ protocol nguy hiểm trong og_image", data_3["og_image"] == "", "javascript: bị loại bỏ hoàn toàn")
    check("Test 3.2 - Loại bỏ protocol nguy hiểm trong og_url", data_3["og_url"] == "", "data: bị loại bỏ hoàn toàn")

    rendered_3 = render_landing_page(xss_project, template_path="sales.html")
    check("Test 3.3 - Không có thẻ <script>alert chèn vào ngoài ý muốn", "<script>alert" not in rendered_3, "Không bị tiêm mã script")
    check("Test 3.4 - Dấu ngoặc kép và nhọn được HTML escape", "&quot;" in rendered_3 or "&#34;" in rendered_3 or "&lt;script&gt;" in rendered_3, "Dữ liệu được escape an toàn")
    parser_3 = parse_html_seo(rendered_3)
    check("Test 3.5 - Cấu trúc thẻ meta không bị phá vỡ", len(parser_3.og_titles) == 1 and len(parser_3.meta_descriptions) == 1, "Thẻ meta chuẩn cấu trúc")

    # -------------------------------------------------------------------------
    # TEST 4: KIỂM TRA TOÀN BỘ 6 TEMPLATE + FALLBACK_TEMPLATE
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Kiểm tra toàn bộ 6 Template + FALLBACK_TEMPLATE ---")
    templates_to_test = [
        "modern_tech.html",
        "elegant_beauty.html",
        "trust_consulting.html",
        "sales.html",
        "marketing.html",
        "event.html",
    ]

    test_payload = {
        "campaign_name": "Ưu Đãi Đặc Biệt 2026",
        "brand_name": "Universal Brand",
        "product_description": "Mô tả chuẩn SEO cho kiểm thử tất cả template đa thiết bị.",
        "image_url": "https://example.com/banner.jpg",
        "github_pages_url": "https://universal.github.io/campaign/",
        "raw_json_data": "{}",
    }

    for t_name in templates_to_test:
        html_out = render_landing_page(test_payload, template_path=t_name)
        p = parse_html_seo(html_out)
        check(f"Test 4 [{t_name}] - Đúng 1 <title>", p.title_count == 1, f"Count={p.title_count}")
        check(f"Test 4 [{t_name}] - Đúng 1 meta description", len(p.meta_descriptions) == 1, f"Count={len(p.meta_descriptions)}")
        check(f"Test 4 [{t_name}] - Đúng 1 og:title", len(p.og_titles) == 1, f"Count={len(p.og_titles)}")
        check(f"Test 4 [{t_name}] - Đúng 1 og:description", len(p.og_descriptions) == 1, f"Count={len(p.og_descriptions)}")
        check(f"Test 4 [{t_name}] - Đúng 1 og:type", len(p.og_types) == 1 and p.og_types[0] == "website", f"Type={p.og_types}")
        check(f"Test 4 [{t_name}] - Đúng 1 og:image", len(p.og_images) == 1, f"Image={p.og_images[0]}")
        check(f"Test 4 [{t_name}] - Đúng 1 og:url", len(p.og_urls) == 1, f"Url={p.og_urls[0]}")

    # Kiểm tra FALLBACK_TEMPLATE (truyền template_path không tồn tại để kích hoạt fallback)
    fallback_html = render_landing_page(test_payload, template_path="non_existent_template.html")
    p_fb = parse_html_seo(fallback_html)
    check("Test 4 [FALLBACK] - Đúng 1 <title>", p_fb.title_count == 1, f"Count={p_fb.title_count}")
    check("Test 4 [FALLBACK] - Đúng 1 meta description", len(p_fb.meta_descriptions) == 1, f"Count={len(p_fb.meta_descriptions)}")
    check("Test 4 [FALLBACK] - Đúng 1 og:title", len(p_fb.og_titles) == 1, f"Count={len(p_fb.og_titles)}")
    check("Test 4 [FALLBACK] - Đúng 1 og:description", len(p_fb.og_descriptions) == 1, f"Count={len(p_fb.og_descriptions)}")
    check("Test 4 [FALLBACK] - Đúng 1 og:image", len(p_fb.og_images) == 1, f"Image={p_fb.og_images[0]}")
    check("Test 4 [FALLBACK] - Đúng 1 og:url", len(p_fb.og_urls) == 1, f"Url={p_fb.og_urls[0]}")

    # -------------------------------------------------------------------------
    # TEST 5: KIỂM TRA THỨ TỰ ƯU TIÊN DỮ LIỆU
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Kiểm tra thứ tự ưu tiên dữ liệu (Data Priority) ---")

    # 5.1 Ưu tiên SEO Title:
    # 1. raw.seo_title
    d_p1 = build_template_data({
        "campaign_name": "Camp A",
        "product_name": "Prod B",
        "brand_name": "Brand C",
        "raw_json_data": '{"seo_title": "SEO Title Custom"}'
    })
    check("Test 5.1 - Title ưu tiên 1: raw.seo_title", d_p1["seo_title"] == "SEO Title Custom", d_p1["seo_title"])

    # 2. project.campaign_name (không có seo_title)
    d_p2 = build_template_data({
        "campaign_name": "Camp A",
        "product_name": "Prod B",
        "brand_name": "Brand C",
        "raw_json_data": '{}'
    })
    check("Test 5.2 - Title ưu tiên 2: campaign_name + brand", d_p2["seo_title"] == "Camp A - Brand C", d_p2["seo_title"])

    # 3. project.product_name (không có campaign_name)
    d_p3 = build_template_data({
        "product_name": "Prod B",
        "brand_name": "Brand C",
        "raw_json_data": '{}'
    })
    check("Test 5.3 - Title ưu tiên 3: product_name + brand", d_p3["seo_title"] == "Prod B - Brand C", d_p3["seo_title"])

    # 4. Khi tên đã chứa thương hiệu thì không lặp
    d_p4 = build_template_data({
        "campaign_name": "Khuyến Mãi Brand C",
        "brand_name": "Brand C",
        "raw_json_data": '{}'
    })
    check("Test 5.4 - Tránh lặp tên thương hiệu trong Title", d_p4["seo_title"] == "Khuyến Mãi Brand C", d_p4["seo_title"])

    # 5.2 Ưu tiên SEO Description:
    # 1. raw.seo_description
    d_d1 = build_template_data({
        "product_description": "Project Desc",
        "raw_json_data": '{"seo_description": "Custom SEO Description"}'
    })
    check("Test 5.5 - Desc ưu tiên 1: raw.seo_description", d_d1["seo_description"] == "Custom SEO Description", d_d1["seo_description"])

    # 2. project.product_description
    d_d2 = build_template_data({
        "product_description": "Project Desc Level 2",
        "raw_json_data": '{"product_description": "Raw Desc Level 3"}'
    })
    check("Test 5.6 - Desc ưu tiên 2: project.product_description", d_d2["seo_description"] == "Project Desc Level 2", d_d2["seo_description"])

    # 5.3 Ưu tiên Open Graph Image:
    # 1. project.image_url
    d_i1 = build_template_data({
        "image_url": "https://img.project.com/1.jpg",
        "raw_json_data": '{"image_url": "https://img.raw.com/2.jpg", "hero_image_url": "https://img.hero.com/3.jpg"}'
    })
    check("Test 5.7 - Image ưu tiên 1: project.image_url", d_i1["og_image"] == "https://img.project.com/1.jpg", d_i1["og_image"])

    # 2. raw.image_url
    d_i2 = build_template_data({
        "raw_json_data": '{"image_url": "https://img.raw.com/2.jpg", "hero_image_url": "https://img.hero.com/3.jpg"}'
    })
    check("Test 5.8 - Image ưu tiên 2: raw.image_url", d_i2["og_image"] == "https://img.raw.com/2.jpg", d_i2["og_image"])

    # -------------------------------------------------------------------------
    # TEST 6: KIỂM TRA HỒI QUY DỮ LIỆU CŨ (Regression)
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Kiểm tra hồi quy dữ liệu cũ (Regression) ---")
    reg_project = {
        "brand_name": "Nova Enterprise",
        "product_name": "Flagship Solution",
        "campaign_name": "Q4 Campaign",
        "price": 2500000,
        "color_theme": "#2563EB",
        "messenger_link": "https://m.me/nova.enterprise",
        "hotline": "1900 1234",
        "raw_json_data": """{
            "headline": "Tiêu Đề Lớn",
            "features_heading": "Lý do chọn Nova",
            "features": [
                {"title": "Tính năng 1", "description": "Mô tả tính năng 1", "icon": "fa-star"},
                {"title": "Tính năng 2", "description": "Mô tả tính năng 2", "icon": "fa-check"}
            ]
        }""",
    }

    d_reg = build_template_data(reg_project)
    check("Test 6.1 - data.brand_name bảo toàn", d_reg["brand_name"] == "Nova Enterprise", d_reg["brand_name"])
    check("Test 6.2 - data.cta bảo toàn cấu trúc", isinstance(d_reg["cta"], dict) and d_reg["cta"]["has_any_cta"] is True, "CTA object hợp lệ")
    check("Test 6.3 - data.features chuỗi tiêu đề bảo toàn", d_reg["features"] == "Lý do chọn Nova", d_reg["features"])
    check("Test 6.4 - data.feature_items danh sách bảo toàn", len(d_reg["feature_items"]) == 2, f"Số features: {len(d_reg['feature_items'])}")
    check("Test 6.5 - Hotline format & href bảo toàn", d_reg["hotline"] == "1900 1234" and d_reg["hotline_href"] == "tel:19001234", d_reg["hotline_href"])

    # Render kiểm tra giao diện body không bị ảnh hưởng
    html_reg = render_landing_page(reg_project, template_path="modern_tech.html")
    check("Test 6.6 - Render template thành công và chứa CTA dynamic section", "cta-dynamic-section" in html_reg, "CTA section tồn tại")
    check("Test 6.7 - Chứa nội dung headline và brand trong body", "Tiêu Đề Lớn" in html_reg and "Nova Enterprise" in html_reg, "Body nguyên vẹn")

    print("\n" + "=" * 70)
    print("TẤT CẢ 6 NHÓM KIỂM THỬ SEO META & OPEN GRAPH ĐỀU PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    run_seo_tests()
