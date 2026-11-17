from sqlalchemy import Column, Integer, Table
from sqlalchemy.orm import configure_mappers

from core.database import Base

# Đăng ký metadata tham chiếu cho các bảng khóa ngoại của Project (users, templates)
Table("users", Base.metadata, Column("id", Integer, primary_key=True), extend_existing=True)
Table("templates", Base.metadata, Column("id", Integer, primary_key=True), extend_existing=True)

from models.generation import (  # noqa: E402
    GENERATION_STATUSES,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUCCESS,
    Generation,
)
from models.project import Project  # noqa: E402

configure_mappers()

__all__ = [
    "GENERATION_STATUSES",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SUCCESS",
    "Generation",
    "Project",
]