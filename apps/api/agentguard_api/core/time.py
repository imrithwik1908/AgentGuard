from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def duration_ms(started_at: datetime, ended_at: datetime) -> int:
    started = ensure_aware_utc(started_at)
    ended = ensure_aware_utc(ended_at)
    if ended < started:
        raise ValueError("ended_at must be greater than or equal to started_at")
    return int((ended - started).total_seconds() * 1000)

