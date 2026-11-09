from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CheckResult, Incident


def is_success(check : CheckResult) -> bool:
    return (
        check.error is None
        and check.status_code is not None
        and 200 <= check.status_code < 300
    )

async def process_incident(
        session: AsyncSession, monitor_id: int
) -> None:
    statement = select(CheckResult).where(CheckResult.monitor_id == monitor_id).order_by(CheckResult.checked_at.desc(),CheckResult.id.desc()).limit(2)
    result = await session.execute(statement)
    records = result.scalars().all()

    if not records:
        return

    statement2 = select(Incident).where(
        Incident.monitor_id == monitor_id,
        Incident.resolved_at.is_(None)
    )

    result = await session.execute(statement2)
    incident = result.scalar_one_or_none()

    if incident is not None and is_success(records[0]):
        incident.resolved_at = datetime.now(timezone.utc)

    if(
        len(records) == 2
        and not is_success(records[0])
        and not is_success(records[1])
        and incident is None
    ):
        incident = Incident(monitor_id=monitor_id, reason="Two consecutive failures")
        session.add(incident)