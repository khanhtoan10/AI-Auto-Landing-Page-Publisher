"""API Router lịch sử triển khai Landing Page.

Cung cấp dữ liệu thật từ bảng ``deployments`` cho trang Lịch sử xuất bản:

  GET /deployments          – Danh sách deployment của người dùng hiện tại.
  GET /deployments/stats    – Số liệu tổng hợp cho phần banner thống kê.
  GET /deployments/{id}     – Chi tiết một deployment (dùng khi cần polling).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user

router = APIRouter(prefix="/deployments", tags=["Deployments"])

# Subquery xác định deployment thành công mới nhất của mỗi dự án.
_LATEST_SUCCESS_JOIN = """
    LEFT JOIN (
        SELECT project_id, MAX(id) AS latest_id
        FROM deployments
        WHERE status = 'Success'
        GROUP BY project_id
    ) ls ON ls.project_id = d.project_id
"""


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _view_status(raw_status: str | None, is_latest_success: bool) -> str:
    if raw_status == "Success":
        return "active" if is_latest_success else "superseded"
    if raw_status == "Failed":
        return "failed"
    return "processing"


def _serialize(row: Any) -> dict:
    item = _json_safe(dict(row))
    is_latest = bool(item.get("is_latest_success"))
    item["is_latest_success"] = is_latest
    item["view_status"] = _view_status(item.get("status"), is_latest)
    item["project_name"] = item.get("campaign_name") or item.get("product_name") or f"Dự án #{item.get('project_id')}"
    item["page_url"] = item.get("github_pages_url") or item.get("project_pages_url")

    start = item.get("start_time")
    end = item.get("end_time")
    duration = None
    if start and end:
        try:
            duration = max(0, int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()))
        except (TypeError, ValueError):
            duration = None
    item["duration_seconds"] = duration
    return item


def _build_filters(project_id: int | None, view_status: str | None) -> tuple[str, dict]:
    where = ["p.user_id = :user_id", "p.deleted_at IS NULL"]
    params: dict = {}

    if project_id is not None:
        where.append("d.project_id = :project_id")
        params["project_id"] = project_id

    if view_status == "active":
        where.append("d.status = 'Success' AND ls.latest_id = d.id")
    elif view_status == "superseded":
        where.append("d.status = 'Success' AND (ls.latest_id IS NULL OR ls.latest_id <> d.id)")
    elif view_status == "failed":
        where.append("d.status = 'Failed'")
    elif view_status == "processing":
        where.append("d.status NOT IN ('Success', 'Failed')")

    return " AND ".join(where), params


@router.get("")
def list_deployments(
    project_id: int | None = Query(default=None, description="Chỉ lấy lịch sử của một dự án"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="active | superseded | failed | processing",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Danh sách deployment có phân trang, kèm trạng thái active/superseded."""
    params = {"user_id": current_user["id"]}
    where, extra_params = _build_filters(project_id, status_filter)
    params.update(extra_params)

    if project_id is not None:
        owned = db.execute(
            text(
                "SELECT id FROM projects "
                "WHERE id = :project_id AND user_id = :user_id AND deleted_at IS NULL"
            ),
            {"project_id": project_id, "user_id": current_user["id"]},
        ).first()
        if not owned:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dự án không tồn tại hoặc không thuộc quyền quản lý của bạn.",
            )

    count_row = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS total
            FROM deployments d
            JOIN projects p ON p.id = d.project_id
            {_LATEST_SUCCESS_JOIN}
            WHERE {where}
            """
        ),
        params,
    ).mappings().first()
    total = int(count_row["total"] or 0) if count_row else 0

    offset = (page - 1) * page_size
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    d.id,
                    d.project_id,
                    d.commit_sha,
                    d.status,
                    d.github_pages_url,
                    d.error_message,
                    d.start_time,
                    d.end_time,
                    p.campaign_name,
                    p.product_name,
                    p.status AS project_status,
                    p.github_pages_url AS project_pages_url,
                    CASE WHEN ls.latest_id = d.id THEN 1 ELSE 0 END AS is_latest_success
                FROM deployments d
                JOIN projects p ON p.id = d.project_id
                {_LATEST_SUCCESS_JOIN}
                WHERE {where}
                ORDER BY d.start_time DESC, d.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": page_size, "offset": offset},
        )
        .mappings()
        .all()
    )

    return {
        "success": True,
        "data": {
            "items": [_serialize(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/stats")
def deployment_stats(
    project_id: int | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Số liệu tổng hợp phục vụ banner trang Lịch sử xuất bản."""
    where = ["p.user_id = :user_id", "p.deleted_at IS NULL"]
    params: dict = {"user_id": current_user["id"]}
    if project_id is not None:
        where.append("d.project_id = :project_id")
        params["project_id"] = project_id

    row = (
        db.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN d.status = 'Success' THEN 1 ELSE 0 END), 0) AS successful,
                    COALESCE(SUM(CASE WHEN d.status = 'Failed' THEN 1 ELSE 0 END), 0) AS failed,
                    COALESCE(SUM(CASE WHEN d.status NOT IN ('Success', 'Failed') THEN 1 ELSE 0 END), 0) AS processing,
                    COUNT(DISTINCT CASE WHEN d.status = 'Success' THEN d.project_id END) AS live_projects
                FROM deployments d
                JOIN projects p ON p.id = d.project_id
                WHERE {' AND '.join(where)}
                """
            ),
            params,
        )
        .mappings()
        .first()
    )

    total = int(row["total"] or 0) if row else 0
    successful = int(row["successful"] or 0) if row else 0
    success_rate = round(successful * 100 / total, 1) if total else 0.0

    return {
        "success": True,
        "data": {
            "total_deployments": total,
            "successful_deployments": successful,
            "failed_deployments": int(row["failed"] or 0) if row else 0,
            "processing_deployments": int(row["processing"] or 0) if row else 0,
            "live_projects": int(row["live_projects"] or 0) if row else 0,
            "success_rate": success_rate,
        },
    }


@router.get("/{deployment_id}")
def get_deployment_detail(
    deployment_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chi tiết một deployment, chỉ chủ sở hữu dự án mới được xem."""
    row = (
        db.execute(
            text(
                f"""
                SELECT
                    d.id,
                    d.project_id,
                    d.commit_sha,
                    d.status,
                    d.github_pages_url,
                    d.error_message,
                    d.start_time,
                    d.end_time,
                    p.campaign_name,
                    p.product_name,
                    p.status AS project_status,
                    p.github_pages_url AS project_pages_url,
                    CASE WHEN ls.latest_id = d.id THEN 1 ELSE 0 END AS is_latest_success
                FROM deployments d
                JOIN projects p ON p.id = d.project_id
                {_LATEST_SUCCESS_JOIN}
                WHERE d.id = :deployment_id
                  AND p.user_id = :user_id
                  AND p.deleted_at IS NULL
                """
            ),
            {"deployment_id": deployment_id, "user_id": current_user["id"]},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bản triển khai này.",
        )
    return {"success": True, "data": _serialize(row)}
