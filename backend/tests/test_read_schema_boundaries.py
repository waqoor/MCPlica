from datetime import UTC, datetime
from uuid import uuid4

from app.domain.auth import UserAccount, UserRole
from app.domain.builds import BuildRecord, BuildStatus, BuildTrigger
from app.domain.credentials import CredentialRecord, CredentialScheme
from app.domain.indexing import IndexGenerationStatus
from app.domain.sources import (
    OperationSecurityRequirementRecord,
    OperationServerRoutingRecord,
    ProjectSourceRecord,
    SecuritySchemeDiscoveryRecord,
    ServerCandidateRecord,
    SourceConfigurationDiscoveryRecord,
    SourceIssueRecord,
    SourceKind,
    SourceOrigin,
    SourceVersionMetadataRecord,
    SourceVersionRecord,
)
from app.schemas.auth import UserRead
from app.schemas.build import BuildRead
from app.schemas.credential import CredentialRead
from app.schemas.source import (
    SourceConfigurationDiscoveryRead,
    SourceRead,
    SourceVersionMetadataRead,
    SourceVersionRead,
)


def test_read_schemas_accept_domain_records_without_exposing_internal_fields() -> None:
    now = datetime.now(UTC)
    user_id = uuid4()
    project_id = uuid4()
    source_id = uuid4()
    source = ProjectSourceRecord(
        id=source_id,
        project_id=project_id,
        kind=SourceKind.OPENAPI,
        name="Primary API",
        origin_type=SourceOrigin.UPLOAD,
        source_url=None,
        is_primary=True,
        created_at=now,
    )
    version = SourceVersionRecord(
        id=uuid4(),
        source_id=source_id,
        content_sha256="a" * 64,
        media_type="application/json",
        storage_key="internal/source.json",
        byte_size=42,
        detected_format="openapi-json",
        source_etag=None,
        source_last_modified=None,
        created_by=user_id,
        created_at=now,
    )
    credential = CredentialRecord(
        id=uuid4(),
        project_id=project_id,
        name="Bearer",
        scheme_type=CredentialScheme.BEARER,
        key_version="internal-key-version",
        metadata={"security_scheme": "bearerAuth"},
        created_by=user_id,
        created_at=now,
        rotated_at=None,
        revoked_at=None,
    )
    user = UserAccount(
        id=user_id,
        email="admin@admin.com",
        display_name="Admin",
        password_hash="internal-password-hash",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    build = BuildRecord(
        id=uuid4(),
        project_id=project_id,
        sequence=1,
        status=BuildStatus.QUEUED,
        trigger=BuildTrigger.INITIAL,
        canonical_snapshot_id=None,
        previous_build_id=None,
        compiler_version="1.0.0",
        manifest_schema_version="1.0.0",
        runtime_compatibility="1.0.0",
        analysis_model="analysis-model",
        validation_model="validation-model",
        embedding_model="embedding-model",
        embedding_dimensions=8,
        prompt_bundle_version="1.0.0",
        enrichment_sha256=None,
        manifest_sha256=None,
        artifact_sha256=None,
        manifest_storage_key=None,
        artifact_storage_key=None,
        error_code=None,
        error_summary=None,
        requested_by=user_id,
        created_at=now,
        started_at=None,
        completed_at=None,
    )

    assert SourceRead.model_validate(source).id == source_id
    assert SourceVersionRead.model_validate(version).id == version.id
    assert "storage_key" not in SourceVersionRead.model_validate(version).model_dump()
    metadata_record = SourceVersionMetadataRecord(
        version=version,
        parse_status="valid",
        spec_version="openapi-3.1",
        operation_count=2,
        servers=["https://api.example.test/"],
        auth_schemes=["bearerAuth"],
        errors=[
            SourceIssueRecord(
                source_version_id=version.id,
                stage="parsing",
                code="SOURCE_WARNING",
                severity="warning",
                message="Example warning",
                pointer="#/paths",
            )
        ],
        index_status=IndexGenerationStatus.READY,
        metadata_build_id=build.id,
    )
    metadata = SourceVersionMetadataRead(
        **SourceVersionRead.model_validate(version).model_dump(),
        **metadata_record.model_dump(exclude={"version"}),
    )
    assert metadata.operation_count == 2
    assert metadata.index_status is IndexGenerationStatus.READY
    assert "storage_key" not in metadata.model_dump()
    assert CredentialRead.model_validate(credential).id == credential.id
    assert "key_version" not in CredentialRead.model_validate(credential).model_dump()
    assert UserRead.model_validate(user).id == user_id
    assert "password_hash" not in UserRead.model_validate(user).model_dump()
    build_read = BuildRead.model_validate(build)
    assert build_read.id == build.id
    assert build_read.canonical_snapshot_id is None
    assert "requested_by" not in build_read.model_dump()
    assert "manifest_storage_key" not in build_read.model_dump()


def test_source_configuration_read_accepts_nested_domain_records() -> None:
    source_version_id = uuid4()
    discovery = SourceConfigurationDiscoveryRecord(
        source_version_ids=[source_version_id],
        configuration_sha256="a" * 64,
        servers=[
            ServerCandidateRecord(
                ref="server:primary",
                url="https://api.example.test",
                description="Primary API",
                scope="root",
                source_pointer="#/servers/0",
                applicable_operation_keys=["get_items"],
            )
        ],
        operations=[
            OperationServerRoutingRecord(
                operation_key="get_items",
                method="GET",
                path="/items",
                candidate_refs=["server:primary"],
                selected_server_ref="server:primary",
                configured_server_ref=None,
                selection_required=False,
                selection_error=None,
            )
        ],
        security_schemes=[
            SecuritySchemeDiscoveryRecord(
                name="bearerAuth",
                type="http_bearer",
                location=None,
                parameter_name=None,
                token_url=None,
                advertised_scopes=[],
                applicable_operation_keys=["get_items"],
                optional_for_all_operations=False,
                source_pointer="#/components/securitySchemes/bearerAuth",
            )
        ],
        security_requirements=[
            OperationSecurityRequirementRecord(
                operation_key="get_items",
                alternatives=[{"bearerAuth": []}],
                anonymous_allowed=False,
            )
        ],
        routing_complete=True,
    )

    response = SourceConfigurationDiscoveryRead.model_validate(discovery)

    assert response.source_version_ids == [source_version_id]
    assert response.servers[0].ref == "server:primary"
    assert response.operations[0].selected_server_ref == "server:primary"
    assert response.security_schemes[0].name == "bearerAuth"
    assert response.security_requirements[0].alternatives == [{"bearerAuth": []}]
