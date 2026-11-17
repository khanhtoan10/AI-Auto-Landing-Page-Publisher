import re
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from services.cta_service import (
    clean_string,
    normalize_hotline,
    normalize_instagram,
    normalize_messenger,
    normalize_tiktok_shop,
    normalize_zalo,
)
SOCIAL_DOMAINS = {
    "facebook_url": ("facebook.com", "fb.com"),
    "tiktok_url": ("tiktok.com",),
    "instagram_url": ("instagram.com",),
}

def _validate_url(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None or value == "":
        return value or None
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Link phai bat dau bang http:// hoac https://")
    domains = SOCIAL_DOMAINS.get(field_name)
    if domains and not any(
        parsed.hostname == d or parsed.hostname.endswith("." + d) for d in domains
    ):
        raise ValueError("Link khong dung ten mien " + domains[0])
    return value


def _validate_color(value: Optional[str]) -> Optional[str]:
    if value is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Tong mau phai dang hex, vi du #1A2B3C")
    return value


class ProjectCreate(BaseModel):
    template_id: int
    campaign_name: str = Field(min_length=1, max_length=255)
    product_name: str = Field(min_length=1, max_length=255)
    product_description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[Decimal] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_theme: Optional[str] = None

    # 5 trường CTA động chính thức
    messenger_link: Optional[str] = Field(default=None, max_length=500)
    tiktok_shop_link: Optional[str] = Field(default=None, max_length=500)
    zalo_link: Optional[str] = Field(default=None, max_length=500)
    instagram_link: Optional[str] = Field(default=None, max_length=500)
    hotline: Optional[str] = Field(default=None, max_length=50)

    # Các trường cũ giữ lại để tương thích ngược
    facebook_url: Optional[str] = Field(default=None, max_length=500)
    tiktok_url: Optional[str] = Field(default=None, max_length=500)
    instagram_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("campaign_name", "product_name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip() if v else ""
        if not v:
            raise ValueError("Không được để trống")
        return v

    @field_validator("color_theme")
    @classmethod
    def valid_color(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise ValueError("Tông màu phải có dạng mã hex, ví dụ #1A2B3C")
        return v
        return _validate_color(v)

    @field_validator("image_url")
    @classmethod
    def valid_image_url(cls, v):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Đường dẫn ảnh phải bắt đầu bằng http:// hoặc https://")
        return v
    def valid_url(cls, v, info):
        return _validate_url(v, info.field_name)

    @field_validator("messenger_link")
    @classmethod
    def validate_messenger(cls, v):
        return clean_string(v)

    @field_validator("tiktok_shop_link")
    @classmethod
    def validate_tiktok_shop(cls, v):
        return clean_string(v)

    @field_validator("zalo_link")
    @classmethod
    def validate_zalo(cls, v):
        return clean_string(v)

    @field_validator("instagram_link")
    @classmethod
    def validate_instagram(cls, v):
        return clean_string(v)

    @field_validator("hotline")
    @classmethod
    def validate_hotline(cls, v):
        return clean_string(v)


class ProjectUpdate(BaseModel):
    template_id: Optional[int] = None
    campaign_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[Decimal] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_theme: Optional[str] = None

    # 5 trường CTA động chính thức
    messenger_link: Optional[str] = Field(default=None, max_length=500)
    tiktok_shop_link: Optional[str] = Field(default=None, max_length=500)
    zalo_link: Optional[str] = Field(default=None, max_length=500)
    instagram_link: Optional[str] = Field(default=None, max_length=500)
    hotline: Optional[str] = Field(default=None, max_length=50)

    # Các trường cũ
    facebook_url: Optional[str] = Field(default=None, max_length=500)
    tiktok_url: Optional[str] = Field(default=None, max_length=500)
    instagram_url: Optional[str] = Field(default=None, max_length=500)
    repo_url: Optional[str] = Field(default=None, max_length=500)
    github_pages_url: Optional[str] = Field(default=None, max_length=500)
    raw_json_data: Optional[Any] = None
    change_summary: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Ghi chú thay đổi, lưu vào project_versions.change_summary",
    )
    commit_message: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Commit message khi push lên GitHub (tùy chọn)",
    )

    @field_validator("campaign_name", "product_name")
    @classmethod
    def not_blank(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Không được để trống")
        return v

    @field_validator("color_theme")
    @classmethod
    def valid_color(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise ValueError("Tông màu phải có dạng mã hex, ví dụ #1A2B3C")
        return v

    @field_validator("image_url")
    @classmethod
    def valid_image_url(cls, v):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Đường dẫn ảnh phải bắt đầu bằng http:// hoặc https://")
        return v

    @field_validator("messenger_link")
    @classmethod
    def validate_messenger(cls, v):
        return clean_string(v)

    @field_validator("tiktok_shop_link")
    @classmethod
    def validate_tiktok_shop(cls, v):
        return clean_string(v)

    @field_validator("zalo_link")
    @classmethod
    def validate_zalo(cls, v):
        return clean_string(v)

    @field_validator("instagram_link")
    @classmethod
    def validate_instagram(cls, v):
        return clean_string(v)

    @field_validator("hotline")
    @classmethod
    def validate_hotline(cls, v):
        return clean_string(v)
        return _validate_color(v)

    @field_validator(
        "image_url",
        "facebook_url",
        "tiktok_url",
        "instagram_url",
        "repo_url",
        "github_pages_url",
    )
    @classmethod
    def valid_url(cls, v, info):
        return _validate_url(v, info.field_name)


class ProjectPreviewResponse(BaseModel):
    """Kết quả render xem trước, không lưu vào DB."""

    success: bool = True
    rendered_html: str
    product_name: str
    price: Optional[float] = None


class ProjectUpdateResponse(BaseModel):
    """Kết quả cập nhật landing page: DB -> render -> push GitHub -> lưu version."""

    success: bool = True
    message: str
    data: dict[str, Any]
    project: dict[str, Any]
    commit_sha: Optional[str] = None
    version_id: Optional[int] = None
    version_number: Optional[int] = None
    rendered_html: str
    github_pages_url: Optional[str] = None
    repo_url: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
