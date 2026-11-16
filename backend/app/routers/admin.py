from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import AdminUser, get_admin_user
from app.dependencies.db import DbSession
from app.models import ReportStatus
from app.schemas.admin import AdminPersonOut, AdminSummary, ReportOut, ReportResolve
from app.schemas.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.services import admin_service

# The dependency is on the whole router: an endpoint added here later is admin-only by
# default, rather than open until someone remembers to protect it.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin_user)])

Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


@router.get("/summary", response_model=AdminSummary)
async def summary(db: DbSession) -> AdminSummary:
    return await admin_service.summary(db)


@router.get("/reports", response_model=Page[ReportOut])
async def list_reports(
    db: DbSession,
    status: ReportStatus = ReportStatus.OPEN,
    cursor: str | None = None,
    limit: Limit = DEFAULT_LIMIT,
) -> Page[ReportOut]:
    return await admin_service.list_reports(db, status, cursor, limit)


@router.post("/reports/{report_id}/resolve", response_model=ReportOut)
async def resolve_report(
    report_id: int, body: ReportResolve, db: DbSession, admin: AdminUser
) -> ReportOut:
    """Decide a report: dismiss it, or suspend the account it is about."""
    return await admin_service.resolve_report(db, admin, report_id, body)


@router.get("/suspended", response_model=list[AdminPersonOut])
async def list_suspended(db: DbSession) -> list[AdminPersonOut]:
    return await admin_service.list_suspended(db)


@router.post("/users/{user_id}/unsuspend", response_model=AdminPersonOut)
async def unsuspend_user(user_id: int, db: DbSession) -> AdminPersonOut:
    return await admin_service.unsuspend_user(db, user_id)
