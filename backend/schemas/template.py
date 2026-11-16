import json
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class TemplateItem(BaseModel):
    """Schema thông tin của một Template trả về cho client."""

    id: int = Field(..., description="ID của Template", examples=[1])
    name: str = Field(..., description="Tên Template", examples=["Modern Business"])
    description: Optional[str] = Field(
        None,
        description="Mô tả Template",
        examples=["Template landing page dành cho doanh nghiệp hiện đại"],
    )
    thumbnail: str = Field(
        ...,
        description="Đường dẫn ảnh đại diện",
        examples=["/uploads/templates/modern-business.png"],
    )
    thumbnail_url: Optional[str] = Field(
        None,
        description="Đường dẫn ảnh đại diện (alias tương thích)",
        examples=["/static/thumbnails/modern_tech.jpg"],
    )
    file_path: Optional[str] = Field(
        None,
        description="Đường dẫn file template gốc",
        examples=["templates/modern_tech.html"],
    )
    placeholders: List[str] = Field(
        default_factory=list,
        description="Danh sách các placeholder mà Template hỗ trợ",
        examples=[
            [
                "headline",
                "subheadline",
                "features",
                "cta",
                "primary_color",
                "image",
            ]
        ],
    )

    @field_validator("placeholders", mode="before")
    @classmethod
    def parse_placeholders(cls, v: Any) -> List[str]:
        """Đảm bảo placeholders luôn là một JSON Array (list of string)."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
                return []
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(v, (list, tuple)):
            return [str(item) for item in v]
        return []

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """Schema response danh sách Template thành công."""

    success: bool = Field(True, description="Trạng thái thực hiện yêu cầu")
    message: str = Field("Lấy danh sách template thành công", description="Thông điệp phản hồi")
    data: List[TemplateItem] = Field(..., description="Danh sách các template từ database")


class TemplateDetailResponse(BaseModel):
    """Schema response chi tiết Template thành công."""

    success: bool = Field(True, description="Trạng thái thực hiện yêu cầu")
    message: str = Field("Lấy chi tiết template thành công", description="Thông điệp phản hồi")
    data: Optional[TemplateItem] = Field(..., description="Dữ liệu chi tiết template")


class ErrorResponse(BaseModel):
    """Schema chuẩn khi xảy ra lỗi."""

    success: bool = Field(False, description="Trạng thái thất bại")
    message: str = Field(..., description="Thông điệp mô tả lỗi")
    data: Optional[Any] = Field(None, description="Dữ liệu trả về (null khi có lỗi)")
