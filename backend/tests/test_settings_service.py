from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.crypto import AesGcmSecretCipher
from app.core.exceptions import ValidationError
from app.providers.ai.base import AIModelInfo, AIProvider
from app.repositories.audit import AuditRepository
from app.repositories.settings import EncryptedSystemSecret, SettingsRepository, SystemSettingRecord
from app.schemas.setting import SystemSettingsUpdate
from app.services.settings import SettingsService


class _Database:
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[object]:
        yield object()


class _SettingsRepository:
    encrypted_payload: bytes | None = None
    key_version: str | None = None

    async def lock_key(self, _session: object, _key: str) -> None:
        return None

    async def set_secret(
        self,
        _session: object,
        *,
        key: str,
        encrypted_payload: bytes,
        key_version: str,
        updated_by: object,
    ) -> None:
        del key, updated_by
        self.encrypted_payload = encrypted_payload
        self.key_version = key_version

    async def get_record(self, _session: object, _key: str) -> None:
        return None

    async def get_secret(
        self,
        _session: object,
        key: str,
    ) -> EncryptedSystemSecret | None:
        if self.encrypted_payload is None or self.key_version is None:
            return None
        return EncryptedSystemSecret(
            key=key,
            encrypted_payload=self.encrypted_payload,
            key_version=self.key_version,
            rotated_at=datetime.now(UTC),
        )


class _Audit:
    async def append(self, _session: object, **_values: object) -> None:
        return None


class _CatalogProvider:
    async def list_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                id="valid",
                name="Valid",
                supported_parameters=frozenset({"json_schema"}),
                input_modalities=frozenset({"text"}),
                output_modalities=frozenset({"text"}),
                raw={"context_length": 128_000.0},
            ),
            AIModelInfo(
                id="boolean",
                name="Boolean",
                supported_parameters=frozenset(),
                input_modalities=frozenset(),
                output_modalities=frozenset(),
                raw={"context_length": True},
            ),
            AIModelInfo(
                id="invalid",
                name="Invalid",
                supported_parameters=frozenset(),
                input_modalities=frozenset(),
                output_modalities=frozenset(),
                raw={"context_length": float("nan")},
            ),
        ]


def _service(
    repository: _SettingsRepository | None = None,
    defaults: Settings | None = None,
) -> tuple[SettingsService, AesGcmSecretCipher, _SettingsRepository]:
    active_repository = repository or _SettingsRepository()
    cipher = AesGcmSecretCipher({"v1": b"k" * 32}, "v1")
    return (
        SettingsService(
            cast(DatabaseClient, _Database()),
            cast(SettingsRepository, active_repository),
            cast(AuditRepository, _Audit()),
            cipher,
            defaults or Settings(env="test"),
        ),
        cipher,
        active_repository,
    )


async def test_openrouter_key_is_normalized_before_encrypted_persistence() -> None:
    service, cipher, repository = _service()
    result = await service.rotate_openrouter_key(
        "  sk-or-v1-test-key  ",
        actor_user_id=uuid4(),
        request_id="request-1",
    )

    assert result.openrouter_configured is True
    assert repository.encrypted_payload is not None
    assert repository.key_version is not None
    assert cipher.decrypt_json(
        repository.encrypted_payload,
        key_version=repository.key_version,
        associated_data=b"system-secret:openrouter_api_key",
    ) == {"api_key": "sk-or-v1-test-key"}


@pytest.mark.parametrize(
    "invalid",
    ["short", "          ", "sk-or-v1-line\nbreak", "sk-or-v1-\u2603-key"],
)
async def test_openrouter_key_rejects_unsafe_text_at_the_service_boundary(invalid: str) -> None:
    service, _cipher, _repository = _service()
    with pytest.raises(ValidationError, match="printable ASCII"):
        await service.rotate_openrouter_key(
            invalid,
            actor_user_id=uuid4(),
            request_id=None,
        )


async def test_model_catalog_ignores_boolean_and_non_finite_context_lengths() -> None:
    service, _cipher, _repository = _service()
    catalog = await service.model_catalog(cast(AIProvider, _CatalogProvider()))

    by_id = {item.id: item for item in catalog}
    assert by_id["valid"].context_length == 128_000
    assert by_id["boolean"].context_length is None
    assert by_id["invalid"].context_length is None


@pytest.mark.parametrize(
    "field",
    [
        "builders_can_deploy",
        "mcp_base_domain",
        "build_concurrency",
        "max_upload_bytes",
        "max_operations_per_project",
        "max_document_chunks_per_project",
        "environment",
    ],
)
def test_required_operational_patch_fields_reject_explicit_null(field: str) -> None:
    with pytest.raises(PydanticValidationError):
        SystemSettingsUpdate.model_validate({field: None})
    assert SystemSettingsUpdate.model_validate({}).model_dump(exclude_unset=True) == {}


def test_explicitly_cleared_models_do_not_reappear_from_environment_defaults() -> None:
    defaults = Settings(
        env="test",
        openrouter_analysis_model="environment-analysis",
        openrouter_validation_model="environment-validation",
        openrouter_embedding_model="environment-embedding",
    )
    service, _cipher, _repository = _service(defaults=defaults)

    inherited = service._models_from_records(  # pyright: ignore[reportPrivateUsage]
        None,
        openrouter_secret_exists=False,
    )
    assert inherited.analysis_model == "environment-analysis"
    assert inherited.validation_model == "environment-validation"
    assert inherited.embedding_model == "environment-embedding"

    cleared = service._models_from_records(  # pyright: ignore[reportPrivateUsage]
        SystemSettingRecord(
            key="model_policy",
            value={
                "analysis_model": None,
                "validation_model": "",
                "embedding_model": None,
                "include_documentation_in_analysis": False,
            },
            updated_at=datetime.now(UTC),
        ),
        openrouter_secret_exists=False,
    )
    assert cleared.analysis_model is None
    assert cleared.validation_model is None
    assert cleared.embedding_model is None
