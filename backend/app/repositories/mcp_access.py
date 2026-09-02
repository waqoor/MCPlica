from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.deployments import (
    MCPAccessTokenRecord,
    MCPAuthConfigRecord,
    MCPAuthMode,
)
from app.models.mcp_access import MCPAccessToken, MCPAuthConfig


@dataclass(frozen=True, slots=True)
class MCPTokenVerifierRecord:
    id: UUID
    token_hash: str
    expires_at: datetime | None


def _config_to_domain(model: MCPAuthConfig) -> MCPAuthConfigRecord:
    return MCPAuthConfigRecord(
        project_id=model.project_id,
        mode=model.mode,
        issuer_url=model.issuer_url,
        audiences=model.audiences,
        required_scopes=model.required_scopes,
        metadata=model.metadata_json,
        updated_by=model.updated_by,
        updated_at=model.updated_at,
    )


def _token_to_domain(model: MCPAccessToken) -> MCPAccessTokenRecord:
    return MCPAccessTokenRecord(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        token_prefix=model.token_prefix,
        created_by=model.created_by,
        created_at=model.created_at,
        expires_at=model.expires_at,
        last_used_at=model.last_used_at,
        revoked_at=model.revoked_at,
    )


class MCPAccessRepository:
    async def get_config(
        self, session: AsyncSession, project_id: UUID
    ) -> MCPAuthConfigRecord | None:
        model = await session.get(MCPAuthConfig, project_id)
        return _config_to_domain(model) if model else None

    async def upsert_config(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        mode: MCPAuthMode,
        issuer_url: str | None,
        audiences: list[str],
        required_scopes: list[str],
        metadata: dict[str, object],
        updated_by: UUID,
        updated_at: datetime,
    ) -> MCPAuthConfigRecord:
        model = await session.get(MCPAuthConfig, project_id)
        if model is None:
            model = MCPAuthConfig(project_id=project_id)
            session.add(model)
        model.mode = mode
        model.issuer_url = issuer_url
        model.audiences = audiences
        model.required_scopes = required_scopes
        model.metadata_json = metadata
        model.updated_by = updated_by
        model.updated_at = updated_at
        await session.flush()
        await session.refresh(model)
        return _config_to_domain(model)

    async def list_tokens(
        self, session: AsyncSession, project_id: UUID
    ) -> list[MCPAccessTokenRecord]:
        result = await session.scalars(
            select(MCPAccessToken)
            .where(MCPAccessToken.project_id == project_id)
            .order_by(MCPAccessToken.created_at.desc(), MCPAccessToken.id.desc())
        )
        return [_token_to_domain(model) for model in result]

    async def list_tokens_page(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[MCPAccessTokenRecord], int]:
        predicate = MCPAccessToken.project_id == project_id
        total = int(
            await session.scalar(select(func.count()).select_from(MCPAccessToken).where(predicate))
            or 0
        )
        result = await session.scalars(
            select(MCPAccessToken)
            .where(predicate)
            .order_by(MCPAccessToken.created_at.desc(), MCPAccessToken.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_token_to_domain(model) for model in result], total

    async def get_token(self, session: AsyncSession, token_id: UUID) -> MCPAccessTokenRecord | None:
        model = await session.get(MCPAccessToken, token_id)
        return _token_to_domain(model) if model else None

    async def create_token(
        self,
        session: AsyncSession,
        *,
        token_id: UUID,
        project_id: UUID,
        name: str,
        token_prefix: str,
        token_hash: str,
        created_by: UUID,
        expires_at: datetime | None,
    ) -> MCPAccessTokenRecord:
        model = MCPAccessToken(
            id=token_id,
            project_id=project_id,
            name=name,
            token_prefix=token_prefix,
            token_hash=token_hash,
            created_by=created_by,
            expires_at=expires_at,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _token_to_domain(model)

    async def expire_for_rotation(
        self,
        session: AsyncSession,
        token_id: UUID,
        *,
        expires_at: datetime,
        revoke_immediately: bool,
    ) -> MCPAccessTokenRecord | None:
        await session.execute(
            update(MCPAccessToken)
            .where(MCPAccessToken.id == token_id, MCPAccessToken.revoked_at.is_(None))
            .values(
                expires_at=expires_at,
                revoked_at=expires_at if revoke_immediately else None,
            )
        )
        return await self.get_token(session, token_id)

    async def revoke(
        self, session: AsyncSession, token_id: UUID, revoked_at: datetime
    ) -> MCPAccessTokenRecord | None:
        await session.execute(
            update(MCPAccessToken)
            .where(MCPAccessToken.id == token_id, MCPAccessToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at, expires_at=revoked_at)
        )
        return await self.get_token(session, token_id)

    async def restore_rotation(
        self,
        session: AsyncSession,
        token_id: UUID,
        *,
        expires_at: datetime | None,
    ) -> MCPAccessTokenRecord | None:
        await session.execute(
            update(MCPAccessToken)
            .where(MCPAccessToken.id == token_id)
            .values(expires_at=expires_at, revoked_at=None)
        )
        return await self.get_token(session, token_id)

    async def active_verifiers(
        self, session: AsyncSession, project_id: UUID
    ) -> list[MCPTokenVerifierRecord]:
        now = await session.scalar(select(func.clock_timestamp()))
        assert now is not None
        result = await session.scalars(
            select(MCPAccessToken).where(
                MCPAccessToken.project_id == project_id,
                MCPAccessToken.revoked_at.is_(None),
                or_(MCPAccessToken.expires_at.is_(None), MCPAccessToken.expires_at > now),
            )
        )
        return [
            MCPTokenVerifierRecord(model.id, model.token_hash, model.expires_at) for model in result
        ]
