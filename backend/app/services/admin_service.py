"""Moderation: admins review reports, and can suspend the account a report is about.

Nothing here happens automatically. A report is only a claim; a person reads it and decides,
and the decision is recorded on the report (who, when, what, and a note).
"""

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import (
    JoinRequest,
    RefreshToken,
    Report,
    ReportResolution,
    ReportStatus,
    RequestStatus,
    Trip,
    User,
)
from app.realtime import broker
from app.schemas.admin import AdminPersonOut, AdminSummary, ReportOut, ReportResolve, ReportTripOut
from app.schemas.common import utc_now
from app.schemas.pagination import DEFAULT_LIMIT, Page, decode_cursor, make_page
from app.services import request_service, trip_service
from app.services.errors import ConflictError, DomainError, NotFoundError

# Everything a report card shows, fetched in the same query (no N+1).
WITH_PEOPLE = (
    joinedload(Report.reporter),
    joinedload(Report.reported),
    joinedload(Report.reviewer),
    joinedload(Report.trip),
)


async def _reports_received(db: AsyncSession, user_ids: set[int]) -> dict[int, int]:
    """How many reports name each of these people: one grouped query for the whole page."""
    if not user_ids:
        return {}
    rows = await db.execute(
        select(Report.reported_id, func.count())
        .where(Report.reported_id.in_(user_ids))
        .group_by(Report.reported_id)
    )
    return {user_id: count for user_id, count in rows}


def _person(user: User, counts: dict[int, int]) -> AdminPersonOut:
    person = AdminPersonOut.model_validate(user)
    person.reports_received = counts.get(user.id, 0)
    return person


def _report_out(report: Report, counts: dict[int, int]) -> ReportOut:
    trip = report.trip
    return ReportOut(
        id=report.id,
        reason=report.reason,
        details=report.details,
        status=report.status,
        created_at=report.created_at,
        reporter=_person(report.reporter, counts),
        reported=_person(report.reported, counts),
        trip=ReportTripOut(
            id=trip.id,
            start_label=trip.from_label,
            end_label=trip.to_label,
            depart_at=trip.depart_at,
            status=trip.status,
        )
        if trip
        else None,
        resolution=report.resolution,
        admin_note=report.admin_note,
        reviewed_at=report.reviewed_at,
        reviewed_by_name=report.reviewer.display_name if report.reviewer else None,
    )


async def list_reports(
    db: AsyncSession, status: ReportStatus, cursor: str | None = None, limit: int = DEFAULT_LIMIT
) -> Page[ReportOut]:
    stmt = (
        select(Report)
        .options(*WITH_PEOPLE)
        .where(Report.status == status)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(tuple_(Report.created_at, Report.id) < tuple_(*decode_cursor(cursor)))
    reports = list(await db.scalars(stmt))
    people = {r.reported_id for r in reports} | {r.reporter_id for r in reports}
    counts = await _reports_received(db, people)
    return make_page(reports, limit, lambda r: (r.created_at, r.id), lambda r: _report_out(r, counts))


async def get_report(db: AsyncSession, report_id: int) -> ReportOut:
    report = await db.scalar(
        select(Report)
        .options(*WITH_PEOPLE)
        .where(Report.id == report_id)
        .execution_options(populate_existing=True)
    )
    if report is None:
        raise NotFoundError("Report not found")
    counts = await _reports_received(db, {report.reported_id, report.reporter_id})
    return _report_out(report, counts)


async def summary(db: AsyncSession) -> AdminSummary:
    open_reports = await db.scalar(
        select(func.count()).select_from(Report).where(Report.status == ReportStatus.OPEN)
    )
    suspended = await db.scalar(
        select(func.count()).select_from(User).where(User.suspended_at.is_not(None))
    )
    return AdminSummary(open_reports=open_reports or 0, suspended_users=suspended or 0)


async def resolve_report(
    db: AsyncSession, admin: User, report_id: int, data: ReportResolve
) -> ReportOut:
    # FOR UPDATE: two admins deciding the same report are handled one after the other, and
    # the second one is told it was already reviewed.
    report = await db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if report is None:
        raise NotFoundError("Report not found")
    if report.status != ReportStatus.OPEN:
        raise ConflictError("This report was already reviewed")

    now = utc_now()
    target: User | None = None
    if data.action == "suspend":
        target = await db.get(User, report.reported_id)
        if target is None:
            raise NotFoundError("That account no longer exists")
        if target.id == admin.id:
            raise DomainError("You can't suspend your own account")
        if target.is_admin:
            raise DomainError("Admins can't be suspended here. Remove their admin rights first.")
        if not target.is_suspended:
            target.suspended_at = now
        # Log them out everywhere: none of their refresh tokens works any more.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == target.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason="suspended")
        )
        # One decision answers every other open report about the same person.
        await db.execute(
            update(Report)
            .where(
                Report.reported_id == target.id,
                Report.status == ReportStatus.OPEN,
                Report.id != report.id,
            )
            .values(
                status=ReportStatus.REVIEWED,
                resolution=ReportResolution.SUSPENDED,
                reviewed_by=admin.id,
                reviewed_at=now,
                admin_note=f"Closed together with report #{report.id}",
            )
        )

    report.status = ReportStatus.REVIEWED
    report.resolution = ReportResolution.SUSPENDED if target else ReportResolution.DISMISSED
    report.admin_note = (data.note or "").strip() or None
    report.reviewed_by = admin.id
    report.reviewed_at = now
    await db.commit()  # the decision and the suspension succeed or fail together

    if target is not None:
        await _leave_all_rides(db, target)
    return await get_report(db, report_id)


async def _leave_all_rides(db: AsyncSession, user: User) -> None:
    """Take a suspended person out of every upcoming ride.

    Reuses the normal "cancel" rules, so seats are given back under the same locks and the
    other people get the same live alerts ("X cancelled the ride", "X withdrew"). Nobody is
    told about the suspension itself.
    """
    trip_ids = list(
        await db.scalars(
            select(Trip.id).where(Trip.host_id == user.id, Trip.status.in_(trip_service.ACTIVE))
        )
    )
    for trip_id in trip_ids:
        try:
            await trip_service.cancel_trip(db, user, trip_id)
        except DomainError:
            await db.rollback()  # it changed in the meantime (already cancelled): nothing left to do

    request_ids = list(
        await db.scalars(
            select(JoinRequest.id)
            .join(Trip, Trip.id == JoinRequest.trip_id)
            .where(
                JoinRequest.requester_id == user.id,
                JoinRequest.status.in_((RequestStatus.PENDING, RequestStatus.ACCEPTED)),
                Trip.status.in_(trip_service.ACTIVE),
            )
        )
    )
    for request_id in request_ids:
        try:
            await request_service.cancel_request(db, user, request_id)
        except DomainError:
            await db.rollback()

    # Their open tabs reload, get a 401, and land on the login screen.
    await broker.publish(
        [user.id], {"type": "account.suspended", "message": "Your account has been suspended."}
    )


async def list_suspended(db: AsyncSession) -> list[AdminPersonOut]:
    users = list(
        await db.scalars(
            select(User)
            .where(User.suspended_at.is_not(None))
            .order_by(User.suspended_at.desc())
            .limit(100)
        )
    )
    counts = await _reports_received(db, {u.id for u in users})
    return [_person(u, counts) for u in users]


async def unsuspend_user(db: AsyncSession, user_id: int) -> AdminPersonOut:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if not user.is_suspended:
        raise ConflictError("This account isn't suspended")
    user.suspended_at = None  # their old rides stay cancelled; they simply can log in again
    await db.commit()
    return _person(user, await _reports_received(db, {user.id}))


async def set_admin(db: AsyncSession, email: str, is_admin: bool) -> User:
    """Used by the command line (app/cli.py). There is deliberately no API endpoint for it."""
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise NotFoundError(f"No account with the email {email}")
    user.is_admin = is_admin
    await db.commit()
    return user
