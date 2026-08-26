import math
from typing import Any, Protocol, cast
from uuid import UUID

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.crypto import AesGcmSecretCipher
from app.core.exceptions import ClientError, ValidationError
from app.providers.ai.base import AIModelInfo, AIProvider
from app.repositories.audit import AuditRepository
from app.repositories.settings import SettingsRepository, SystemSettingRecord
from app.schemas.setting import (
    ModelCatalogItem,
    ModelSettingsRead,
    ModelSettingsUpdate,
    OpenRouterTestResult,
    SystemSettingsRead,
    SystemSettingsUpdate,
)

_OPENROUTER_SECRET_KEY = "openrouter_api_key"
_OPENROUTER_AAD = b"system-secret:openrouter_api_key"
_MODEL_SETTING_KEY = "model_policy"
_OPERATIONAL_SETTING_KEY = "operational_limits"


class OperationalSettingsView(Protocol):
    mcp_base_domain: str
    max_upload_bytes: int


class OperationalSettingsProvider(Protocol):
    async def get_operational(self) -> OperationalSettingsView: ...


class SettingsService:
    def __init__(
        self,
        database: DatabaseClient,
        repository: SettingsRepository,
        audit: AuditRepository,
        cipher: AesGcmSecretCipher,
        defaults: Settings,
    ) -> None:
        self._database = database
        self._repository = repository
        self._audit = audit
        self._cipher = cipher
        self._defaults = defaults

    async def resolve_openrouter_api_key(self) -> str | None:
        async with self._database.session_scope() as session:
            encrypted = await self._repository.get_secret(session, _OPENROUTER_SECRET_KEY)
        if encrypted is None:
            return (
                self._defaults.openrouter_api_key.get_secret_value()
                if self._defaults.openrouter_api_key is not None
                else None
            )
        payload = self._cipher.decrypt_json(
            encrypted.encrypted_payload,
            key_version=encrypted.key_version,
            associated_data=_OPENROUTER_AAD,
        )
        value = payload.get("api_key")
        return value if isinstance(value, str) and value else None

    async def get_operational(self) -> SystemSettingsRead:
        async with self._database.session_scope() as session:
            raw = await self._repository.get(session, _OPERATIONAL_SETTING_KEY)
        return self._operational_from_raw(raw)

    def _operational_from_raw(self, raw: object | None) -> SystemSettingsRead:
        stored = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
        defaults: dict[str, object] = {
            "builders_can_deploy": self._defaults.builders_can_deploy,
            "mcp_base_domain": self._defaults.mcp_domain,
            "build_concurrency": self._defaults.build_concurrency,
            "source_retention_days": self._defaults.source_retention_days,
            "build_retention_count": self._defaults.build_retention_count,
            "max_upload_bytes": self._defaults.upload_max_bytes,
            "max_operations_per_project": self._defaults.max_operations_per_project,
            "max_document_chunks_per_project": (
                self._defaults.documentation_max_chunks_per_project
            ),
            "environment": self._defaults.env,
        }
        defaults.update({str(key): value for key, value in stored.items()})
        defaults["environment"] = self._defaults.env
        return SystemSettingsRead.model_validate(defaults)

    async def update_operational(
        self,
        update: SystemSettingsUpdate,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> SystemSettingsRead:
        changes = update.model_dump(exclude_unset=True, exclude={"environment"})
        async with self._database.session_scope() as session:
            await self._repository.lock_key(session, _OPERATIONAL_SETTING_KEY)
            raw = await self._repository.get(session, _OPERATIONAL_SETTING_KEY)
            values = self._operational_from_raw(raw).model_dump(exclude={"environment"})
            values.update(changes)
            validated = SystemSettingsRead.model_validate(
                {**values, "environment": self._defaults.env}
            )
            await self._repository.set(
                session,
                key=_OPERATIONAL_SETTING_KEY,
                value=validated.model_dump(mode="json", exclude={"environment"}),
                updated_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="settings.operational_updated",
                entity_type="system_settings",
                request_id=request_id,
                metadata={"changed_fields": sorted(changes)},
            )
        return validated

    async def get_models(self) -> ModelSettingsRead:
        async with self._database.session_scope() as session:
            record = await self._repository.get_record(session, _MODEL_SETTING_KEY)
            encrypted = await self._repository.get_secret(session, _OPENROUTER_SECRET_KEY)
        return self._models_from_records(record, openrouter_secret_exists=encrypted is not None)

    def _models_from_records(
        self,
        record: SystemSettingRecord | None,
        *,
        openrouter_secret_exists: bool,
    ) -> ModelSettingsRead:
        raw = record.value if record is not None else None
        stored = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
        stored_dimensions = stored.get("embedding_dimensions")
        return ModelSettingsRead(
            openrouter_configured=(
                openrouter_secret_exists or self._defaults.openrouter_api_key is not None
            ),
            analysis_model=_optional_string(
                stored.get("analysis_model"), self._defaults.openrouter_analysis_model
            ),
            validation_model=_optional_string(
                stored.get("validation_model"), self._defaults.openrouter_validation_model
            ),
            embedding_model=_optional_string(
                stored.get("embedding_model"), self._defaults.openrouter_embedding_model
            ),
            embedding_dimensions=(
                stored_dimensions if isinstance(stored_dimensions, int) else None
            ),
            include_documentation_in_analysis=bool(
                stored.get("include_documentation_in_analysis", False)
            ),
            updated_at=record.updated_at if record is not None else None,
        )

    async def update_models(
        self,
        update: ModelSettingsUpdate,
        provider: AIProvider,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> ModelSettingsRead:
        changes = update.model_dump(
            exclude_unset=True,
            mode="json",
        )
        await self._validate_model_changes(changes, provider)
        async with self._database.session_scope() as session:
            await self._repository.lock_key(session, _MODEL_SETTING_KEY)
            record = await self._repository.get_record(session, _MODEL_SETTING_KEY)
            encrypted = await self._repository.get_secret(session, _OPENROUTER_SECRET_KEY)
            current = self._models_from_records(
                record,
                openrouter_secret_exists=encrypted is not None,
            )
            values = current.model_dump(
                exclude={"openrouter_configured", "updated_at"},
                mode="json",
            )
            values.update(changes)
            if "embedding_model" in changes:
                values["embedding_dimensions"] = None
            saved = await self._repository.set(
                session,
                key=_MODEL_SETTING_KEY,
                value=values,
                updated_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="settings.models_updated",
                entity_type="system_settings",
                request_id=request_id,
                metadata={"changed_fields": sorted(changes)},
            )
        return ModelSettingsRead(
            **values,
            openrouter_configured=current.openrouter_configured,
            updated_at=saved.updated_at,
        )

    async def _validate_model_changes(
        self,
        changes: dict[str, Any],
        provider: AIProvider,
    ) -> None:
        selected = {
            name: value
            for name, value in changes.items()
            if name in {"analysis_model", "validation_model", "embedding_model"}
            and isinstance(value, str)
            and value
        }
        if not selected:
            return
        catalog = {model.id: model for model in await provider.list_models()}
        for field, model_id in selected.items():
            model = catalog.get(model_id)
            if model is None:
                raise ValidationError(
                    f"Selected {field} is not present in the live OpenRouter catalog"
                )
            if field == "embedding_model":
                if not _supports_embeddings(model):
                    raise ValidationError(
                        "Selected embedding_model does not advertise embedding capability"
                    )
            elif not _supports_structured_outputs(model):
                raise ValidationError(
                    f"Selected {field} does not advertise structured-output capability"
                )

    async def rotate_openrouter_key(
        self,
        api_key: str,
        *,
        actor_user_id: UUID,
        request_id: str | None,
    ) -> ModelSettingsRead:
        normalized_api_key = _normalize_openrouter_api_key(api_key)
        encrypted = self._cipher.encrypt_json(
            {"api_key": normalized_api_key},
            associated_data=_OPENROUTER_AAD,
        )
        async with self._database.session_scope() as session:
            await self._repository.lock_key(session, _OPENROUTER_SECRET_KEY)
            await self._repository.set_secret(
                session,
                key=_OPENROUTER_SECRET_KEY,
                encrypted_payload=encrypted.payload,
                key_version=encrypted.key_version,
                updated_by=actor_user_id,
            )
            await self._audit.append(
                session,
                actor_user_id=actor_user_id,
                event_type="settings.openrouter_key_rotated",
                entity_type="system_secret",
                request_id=request_id,
                metadata={"configured": True},
            )
        models = await self.get_models()
        return models.model_copy(update={"openrouter_configured": True})

    async def model_catalog(self, provider: AIProvider) -> list[ModelCatalogItem]:
        result: list[ModelCatalogItem] = []
        for model in await provider.list_models():
            result.append(
                ModelCatalogItem(
                    id=model.id,
                    name=model.name,
                    context_length=_model_context_length(model.raw.get("context_length")),
                    supports_structured_outputs=_supports_structured_outputs(model),
                    supports_embeddings=_supports_embeddings(model),
                )
            )
        return sorted(result, key=lambda item: item.name.casefold())

    async def test_openrouter(self, provider: AIProvider) -> OpenRouterTestResult:
        try:
            models = await provider.list_models()
        except ClientError as exc:
            return OpenRouterTestResult(ok=False, message=str(exc))
        if not models:
            return OpenRouterTestResult(
                ok=False,
                message="OpenRouter connected but returned no usable model metadata",
            )
        return OpenRouterTestResult(
            ok=True,
            message=f"OpenRouter connected; {len(models)} models are visible",
        )


def _optional_string(value: Any, fallback: str | None) -> str | None:
    return value if isinstance(value, str) and value else fallback


def _normalize_openrouter_api_key(value: str) -> str:
    normalized = value.strip()
    if not 10 <= len(normalized) <= 500 or any(
        not 33 <= ord(character) <= 126 for character in normalized
    ):
        raise ValidationError("OpenRouter API key must be 10-500 printable ASCII characters")
    return normalized


def _model_context_length(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 < value <= 2_147_483_647 else None
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        integer = int(value)
        return integer if 0 < integer <= 2_147_483_647 else None
    return None


def _supports_structured_outputs(model: AIModelInfo) -> bool:
    return bool(
        {"response_format", "structured_outputs", "json_schema"} & model.supported_parameters
    )


def _supports_embeddings(model: AIModelInfo) -> bool:
    return bool(
        {"embedding", "embeddings"} & model.output_modalities
        or {"embedding", "embeddings"} & model.supported_parameters
    )
