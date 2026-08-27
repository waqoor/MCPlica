from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.deployments import (
    RuntimeCommandStatus,
    RuntimeEffectState,
)
from app.repositories.runtime_commands import RuntimeCommandRepository


async def runtime_effect_update(
    session: AsyncSession,
    commands: RuntimeCommandRepository,
    *,
    project_id: UUID,
    subject_type: str,
    subject_id: UUID,
) -> dict[str, object]:
    latest = await commands.latest_for_subject(
        session,
        project_id=project_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    if latest is None:
        return {
            "runtime_effect_state": RuntimeEffectState.EFFECTIVE,
            "runtime_command_id": None,
            "runtime_error_code": None,
        }
    transition = await commands.list_transition(session, latest.transition_id)
    failed = next(
        (command for command in transition if command.status == RuntimeCommandStatus.FAILED),
        None,
    )
    pending = next(
        (command for command in transition if command.status != RuntimeCommandStatus.EFFECTIVE),
        None,
    )
    selected = failed or pending or latest
    if failed is not None:
        state = RuntimeEffectState.FAILED
    elif pending is not None:
        state = RuntimeEffectState.PENDING
    else:
        state = RuntimeEffectState.EFFECTIVE
    return {
        "runtime_effect_state": state,
        "runtime_command_id": selected.id,
        "runtime_error_code": selected.last_error_code,
    }
