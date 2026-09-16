from collections import Counter
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings
from agentguard_api.core.time import duration_ms, ensure_aware_utc
from agentguard_api.models import ApplicationVersion, Project, Span, Trace
from agentguard_api.schemas.trace import TraceIngest
from agentguard_api.services.errors import ConflictError, NotFoundError, ValidationError
from agentguard_api.services.redaction import redact_value, redaction_rules_for_project


def _as_error_dict(value) -> dict | None:
    return value.model_dump(mode="json") if value is not None else None


def _validate_span_graph(payload: TraceIngest, max_spans: int) -> None:
    if len(payload.spans) > max_spans:
        raise ValidationError(
            f"trace contains {len(payload.spans)} spans, exceeding configured limit {max_spans}",
            metadata={"max_spans": max_spans},
        )

    external_ids = [span.external_span_id for span in payload.spans if span.external_span_id]
    duplicates = [external_id for external_id, count in Counter(external_ids).items() if count > 1]
    if duplicates:
        raise ValidationError(
            "external_span_id values must be unique within a trace payload",
            metadata={"duplicates": duplicates},
        )

    known_ids = set(external_ids)
    missing_parents = sorted(
        {
            span.parent_external_span_id
            for span in payload.spans
            if span.parent_external_span_id and span.parent_external_span_id not in known_ids
        }
    )
    if missing_parents:
        raise ValidationError(
            "span parent_external_span_id must reference another span in the same payload",
            metadata={"missing_parent_external_span_ids": missing_parents},
        )

    parent_by_child = {
        span.external_span_id: span.parent_external_span_id
        for span in payload.spans
        if span.external_span_id and span.parent_external_span_id
    }

    for child in parent_by_child:
        seen: set[str] = set()
        current = child
        while current in parent_by_child:
            if current in seen:
                raise ValidationError("span parent relationships cannot contain cycles")
            seen.add(current)
            current = parent_by_child[current]

    for span in payload.spans:
        try:
            duration_ms(span.started_at, span.ended_at)
        except ValueError as exc:
            raise ValidationError(f"invalid span timing for {span.name}: {exc}") from exc

    try:
        duration_ms(payload.started_at, payload.ended_at)
    except ValueError as exc:
        raise ValidationError(f"invalid trace timing: {exc}") from exc


async def ingest_trace(
    session: AsyncSession,
    payload: TraceIngest,
    settings: Settings,
    *,
    workspace_id: UUID | None = None,
) -> Trace:
    _validate_span_graph(payload, settings.max_trace_spans)

    stmt = (
        select(Project, ApplicationVersion)
        .join(ApplicationVersion, ApplicationVersion.project_id == Project.id)
        .where(Project.slug == payload.project_slug)
        .where(ApplicationVersion.version == payload.version)
    )
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise NotFoundError(
            "project/version pair was not found",
        )
    project, application_version = row
    redaction_patterns, redaction_mode = await redaction_rules_for_project(session, project)

    trace_duration_ms = duration_ms(payload.started_at, payload.ended_at)
    trace = Trace(
        project_id=project.id,
        application_version_id=application_version.id,
        external_trace_id=payload.external_trace_id,
        name=payload.name,
        status=payload.status,
        input=redact_value(payload.input, redaction_patterns, redaction_mode),
        output=redact_value(payload.output, redaction_patterns, redaction_mode),
        meta=redact_value(payload.metadata, redaction_patterns, redaction_mode),
        started_at=ensure_aware_utc(payload.started_at),
        ended_at=ensure_aware_utc(payload.ended_at),
        duration_ms=trace_duration_ms,
        total_input_tokens=payload.total_input_tokens,
        total_output_tokens=payload.total_output_tokens,
        estimated_cost=payload.estimated_cost,
        error=_as_error_dict(payload.error),
    )

    try:
        session.add(trace)
        await session.flush()

        span_by_external_id: dict[str, Span] = {}
        for span_payload in payload.spans:
            parent_span_id = None
            if span_payload.parent_external_span_id:
                parent = span_by_external_id.get(span_payload.parent_external_span_id)
                if parent is None:
                    raise ValidationError(
                        "parent span must appear before child span in ingestion payload",
                        metadata={"parent_external_span_id": span_payload.parent_external_span_id},
                    )
                parent_span_id = parent.id

            span = Span(
                trace_id=trace.id,
                parent_span_id=parent_span_id,
                external_span_id=span_payload.external_span_id,
                type=span_payload.type,
                name=span_payload.name,
                status=span_payload.status,
                input=redact_value(span_payload.input, redaction_patterns, redaction_mode),
                output=redact_value(span_payload.output, redaction_patterns, redaction_mode),
                meta=redact_value(span_payload.metadata, redaction_patterns, redaction_mode),
                attributes=redact_value(
                    span_payload.attributes,
                    redaction_patterns,
                    redaction_mode,
                ),
                provider=span_payload.provider,
                model_name=span_payload.model_name,
                input_tokens=span_payload.input_tokens,
                output_tokens=span_payload.output_tokens,
                estimated_cost=span_payload.estimated_cost,
                started_at=ensure_aware_utc(span_payload.started_at),
                ended_at=ensure_aware_utc(span_payload.ended_at),
                duration_ms=duration_ms(span_payload.started_at, span_payload.ended_at),
                error=_as_error_dict(span_payload.error),
            )
            session.add(span)
            await session.flush()
            if span.external_span_id:
                span_by_external_id[span.external_span_id] = span
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "trace conflicts with an existing scoped external identifier",
            metadata={"external_trace_id": payload.external_trace_id},
        ) from exc
    except Exception:
        await session.rollback()
        raise

    return await get_trace(session, trace.id, workspace_id=workspace_id)


async def get_trace(
    session: AsyncSession,
    trace_id: UUID,
    *,
    workspace_id: UUID | None = None,
) -> Trace:
    stmt = select(Trace).options(selectinload(Trace.spans)).where(Trace.id == trace_id)
    if workspace_id is not None:
        stmt = stmt.join(Project).where(Project.workspace_id == workspace_id)
    result = await session.execute(
        stmt
    )
    trace = result.scalar_one_or_none()
    if trace is None:
        raise NotFoundError("trace was not found", metadata={"trace_id": str(trace_id)})
    trace.spans.sort(key=lambda span: (span.started_at, span.created_at))
    return trace


def trace_list_query(
    *,
    project_id: UUID | None = None,
    application_version_id: UUID | None = None,
    status: str | None = None,
    workspace_id: UUID | None = None,
) -> Select:
    stmt = select(Trace).options(selectinload(Trace.spans))
    if workspace_id is not None:
        stmt = stmt.join(Project).where(Project.workspace_id == workspace_id)
    if project_id:
        stmt = stmt.where(Trace.project_id == project_id)
    if application_version_id:
        stmt = stmt.where(Trace.application_version_id == application_version_id)
    if status:
        stmt = stmt.where(Trace.status == status)
    return stmt.order_by(Trace.created_at.desc())


async def list_traces(
    session: AsyncSession,
    *,
    project_id: UUID | None,
    application_version_id: UUID | None,
    status: str | None,
    workspace_id: UUID | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Trace], int]:
    base = trace_list_query(
        project_id=project_id,
        application_version_id=application_version_id,
        status=status,
        workspace_id=workspace_id,
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    result = await session.execute(base.limit(limit).offset(offset))
    return list(result.scalars().unique()), int(total or 0)
