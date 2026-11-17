"""API Router quản lý Template (Landing Page Templates).

Cung cấp hai endpoint:
  - GET /templates       : Lấy danh sách toàn bộ template
  - GET /templates/{id}  : Lấy chi tiết một template theo ID
"""

import logging
from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.template import (
    ErrorResponse,
    TemplateDetailResponse,
    TemplateListResponse,
)
from services.template_service import get_all_templates, get_template_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get(
    "",
    response_model=TemplateListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách Template",
    description="Lấy danh sách tất cả Template từ bảng `templates` trong database, bao gồm thông tin cơ bản và danh sách placeholders.",
    responses={
        200: {
            "model": TemplateListResponse,
            "description": "Lấy dữ liệu thành công",
        },
        500: {
            "model": ErrorResponse,
            "description": "Lỗi hệ thống hoặc lỗi truy vấn cơ sở dữ liệu",
        },
    },
)
async def list_templates(db: Session = Depends(get_db)):
    """Lấy danh sách toàn bộ các Template khả dụng trong hệ thống."""
    try:
        templates = get_all_templates(db)
        return TemplateListResponse(
            success=True,
            message="Lấy danh sách template thành công",
            data=templates,
        )
    except Exception as exc:
        logger.error(f"Lỗi khi truy vấn danh sách template: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Lỗi hệ thống hoặc lỗi truy vấn cơ sở dữ liệu",
                "data": None,
            },
        )


@router.get(
    "/{id}",
    response_model=TemplateDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy chi tiết Template",
    description="Nhận ID Template từ URL, truy vấn dữ liệu Template tương ứng trong bảng `templates` và trả về chi tiết.",
    responses={
        200: {
            "model": TemplateDetailResponse,
            "description": "Lấy dữ liệu thành công",
        },
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy Template theo ID",
        },
        422: {
            "description": "ID không hợp lệ",
        },
        500: {
            "model": ErrorResponse,
            "description": "Lỗi hệ thống hoặc lỗi truy vấn cơ sở dữ liệu",
        },
    },
)
async def get_template(
    id: int = Path(..., gt=0, description="ID của Template cần lấy thông tin", examples=[1]),
    db: Session = Depends(get_db),
):
    """Lấy thông tin chi tiết của một Template theo ID."""
    try:
        template = get_template_by_id(db, id)
        if template is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "message": "Không tìm thấy template",
                    "data": None,
                },
            )
        return TemplateDetailResponse(
            success=True,
            message="Lấy chi tiết template thành công",
            data=template,
        )
    except Exception as exc:
        logger.error(f"Lỗi khi lấy chi tiết template {id}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Lỗi hệ thống hoặc lỗi truy vấn cơ sở dữ liệu",
                "data": None,
            },
        )
