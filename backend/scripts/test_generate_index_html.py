"""Kiểm thử sinh index.html từ template đã chọn.

Chạy từ thư mục backend:
    python scripts/test_generate_index_html.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from markupsafe import escape

from services.html_page_service import (
    HtmlPageError,
    TemplateNotFoundError,
    generate_index_html,
)
from services.template_service import TEMPLATES_DIR

PASSED = 0


def check(name: str, condition: bool, detail: str) -> None:
    global PASSED
    if not condition:
        raise AssertionError(f"FAIL {name}: {detail}")
    PASSED += 1
    print(f"PASS {name}: {detail}")


def main() -> None:
    gemini = {
        "headline": 'Tai nghe Nova & "Pro"',
        "subheadline": "Chống ồn chủ động cho ngày dài",
        "features": ["Pin 40 giờ", "Chống ồn", "Sạc nhanh"],
        "cta_text": "Mua ngay",
        "primary_color": "#e11d48",
    }
    social = {
        "facebook": "https://facebook.com/novabrand",
        "instagram": "https://www.instagram.com/novabrand",
        "tiktok": "https://www.tiktok.com/@novabrand",
        "zalo": "https://zalo.me/0901234567",
        "youtube": "https://www.youtube.com/@novabrand",
    }
    image = "https://cdn.example.com/products/nova.jpg"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        result = generate_index_html(
            gemini,
            template_name="sales.html",
            social_links=social,
            image_url=image,
            project={"product_name": "Tai nghe Nova", "price": 1290000},
            output_path=root / "case1" / "index.html",
        )
        html = result["html"]
        output = Path(result["output_path"])
        check("1. file", output.is_file() and html.lstrip().startswith("<!DOCTYPE html>"), output.name)
        check("1. headline", "Tai nghe Nova" in html and "Chống ồn chủ động" in html, "đủ text Gemini")
        check("1. features", "Pin 40 giờ" in html and "Sạc nhanh" in html, "features đưa vào template")
        check("1. cta+color", "Mua ngay" in html and "#E11D48" in html, "cta và màu hex")
        check("1. image", 'src="https://cdn.example.com/products/nova.jpg"' in html, "src ảnh")
        check(
            "1. social",
            "https://facebook.com/novabrand" in html
            and "https://www.instagram.com/novabrand/" in html
            and "https://www.tiktok.com/@novabrand" in html
            and "https://zalo.me/0901234567" in html
            and "https://www.youtube.com/@novabrand" in html,
            "facebook, instagram, tiktok, zalo, youtube",
        )
        check("1. placeholder", "{{" not in html and "{%" not in html, "không còn thẻ Jinja")
        check("1. quote", str(escape('Tai nghe Nova & "Pro"')) in html, "escape &, quote")

        partial = generate_index_html(
            {"headline": "Chỉ có tiêu đề", "features": None, "subheadline": None},
            template_name="marketing.html",
            output_path=root / "case2" / "index.html",
        )
        partial_html = partial["html"]
        check(
            "2. thiếu trường",
            "Chỉ có tiêu đề" in partial_html
            and "undefined" not in partial_html.lower()
            and "[object Object]" not in partial_html
            and ">None<" not in partial_html,
            "thiếu field vẫn ra HTML, không in null/undefined",
        )

        hostile = '<script>alert(1)</script><img src=x onerror="alert(1)">'
        xss = generate_index_html(
            {
                "headline": hostile,
                "subheadline": "A < B & C > D 'quote'",
                "features": ["<b>đậm</b>", "an toàn"],
                "cta_text": hostile,
                "primary_color": "#112233",
            },
            template_name="sales.html",
            output_path=root / "case3" / "index.html",
        )
        xss_html = xss["html"]
        check("3. escape", str(escape(hostile)) in xss_html, "script được escape")
        check(
            "4. script không thực thi",
            "<script>alert(1)</script>" not in xss_html and "onerror=\"alert(1)\"" not in xss_html,
            "không còn thẻ script thô từ dữ liệu",
        )
        check("3. ký tự", str(escape("A < B & C > D 'quote'")) in xss_html, "đủ & < > ' \"")

        safe_social = generate_index_html(
            gemini,
            template_name="sales.html",
            social_links={"instagram": "https://instagram.com/ok"},
            output_path=root / "case5" / "index.html",
        )
        check(
            "5. url hợp lệ",
            "https://instagram.com/ok/" in safe_social["html"],
            "instagram vào href",
        )

        blocked = generate_index_html(
            gemini,
            template_name="sales.html",
            social_links={
                "instagram": "javascript:alert(1)",
                "zalo": "data:text/html,hi",
                "youtube": "javascript:alert(document.domain)",
            },
            image_url="javascript:alert(1)",
            output_path=root / "case6" / "index.html",
        )
        blocked_html = blocked["html"]
        check(
            "6. javascript url",
            "javascript:" not in blocked_html.lower() and "data:text/html" not in blocked_html.lower(),
            "scheme nguy hiểm bị loại",
        )
        check(
            "6. không tự tạo username",
            "instagram.com/javascriptalert" not in blocked_html,
            "không biến javascript: thành link",
        )

        imaged = generate_index_html(
            {"headline": "Ảnh tương đối", "primary_color": "#2563EB"},
            template_name="event.html",
            image_url="images/hero.png",
            output_path=root / "case7" / "index.html",
        )
        check("7. ảnh tương đối", 'src="images/hero.png"' in imaged["html"], "src đường dẫn nội bộ")
        check(
            "8. nhiều placeholder",
            "Ảnh tương đối" in imaged["html"] and "#2563EB" in imaged["html"] and "{{" not in imaged["html"],
            "headline, màu, không sót placeholder",
        )

        original = {"headline": "Giữ nguyên", "features": ["A"]}
        generate_index_html(
            original,
            template_name="event.html",
            output_path=root / "case-copy" / "index.html",
        )
        check("input không bị sửa", original == {"headline": "Giữ nguyên", "features": ["A"]}, "deepcopy")

        try:
            generate_index_html({"headline": "x"}, template_name="missing.html", output_path=root / "bad")
            missing_ok = False
        except TemplateNotFoundError:
            missing_ok = True
        check("thiếu template", missing_ok, "TemplateNotFoundError")

        try:
            generate_index_html("{", template_name="sales.html", output_path=root / "bad-json")
            json_ok = False
        except HtmlPageError:
            json_ok = True
        check("json hỏng", json_ok, "HtmlPageError")

        try:
            generate_index_html(
                gemini,
                template_name="sales.html",
                output_path=TEMPLATES_DIR / "index.html",
            )
            protected = False
        except HtmlPageError:
            protected = True
        check("không ghi đè template", protected and (TEMPLATES_DIR / "sales.html").is_file(), "từ chối ghi vào templates/")

    demo = generate_index_html(
        gemini,
        template_name="sales.html",
        social_links=social,
        image_url=image,
        project={"product_name": "Tai nghe Nova", "price": 1290000},
    )
    demo_path = Path(demo["output_path"])
    check(
        "9. mở được",
        demo_path.is_file() and demo_path.read_text(encoding="utf-8").lstrip().startswith("<!DOCTYPE html>"),
        str(demo_path),
    )
    print(f"\n{PASSED} checks passed")
    print(f"DEMO {demo_path}")


if __name__ == "__main__":
    main()
