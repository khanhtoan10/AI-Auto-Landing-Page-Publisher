"""Service xử lý nghiệp vụ liên quan đến Template.

Đọc dữ liệu trực tiếp từ bảng templates trong cơ sở dữ liệu qua SQLAlchemy Session.
Không dùng mock data hay hardcode dữ liệu.
"""

from typing import List, Optional
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
