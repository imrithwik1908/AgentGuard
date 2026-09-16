import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.models import Project, RedactionPolicy


def _apply_patterns_to_text(value: str, patterns: list[str], mode: str) -> str | None:
    redacted = value
    for pattern in patterns:
        if not pattern:
            continue
        if mode == "drop" and re.search(pattern, redacted):
            return None
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted


def redact_value(value: Any, patterns: list[str], mode: str) -> Any:
    if isinstance(value, str):
        return _apply_patterns_to_text(value, patterns, mode)
    if isinstance(value, list):
        return [redact_value(item, patterns, mode) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            next_value = redact_value(item, patterns, mode)
            if next_value is not None:
                redacted[key] = next_value
        return redacted
    return value


async def redaction_rules_for_project(
    session: AsyncSession,
    project: Project,
) -> tuple[list[str], str]:
    if project.workspace_id is None:
        return [], "mask"
    result = await session.execute(
        select(RedactionPolicy).where(
            RedactionPolicy.workspace_id == project.workspace_id,
            RedactionPolicy.is_enabled.is_(True),
        )
    )
    policies = list(result.scalars())
    patterns: list[str] = []
    mode = "mask"
    for policy in policies:
        mode = "drop" if policy.mode == "drop" else mode
        patterns.extend(line.strip() for line in policy.patterns.splitlines() if line.strip())
    return patterns, mode
