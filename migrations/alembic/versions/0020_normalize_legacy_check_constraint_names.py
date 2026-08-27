"""Normalize check-constraint names created by the legacy naming convention.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


_LEGACY_CHECK_CONSTRAINT_RENAMES = (
    (
        "build_ai_runs",
        "ck_build_ai_runs_ck_build_ai_runs_input_hash",
        "ck_build_ai_runs_input_hash",
    ),
    (
        "build_ai_runs",
        "ck_build_ai_runs_ck_build_ai_runs_latency",
        "ck_build_ai_runs_latency",
    ),
    (
        "build_ai_runs",
        "ck_build_ai_runs_ck_build_ai_runs_outcome",
        "ck_build_ai_runs_outcome",
    ),
    (
        "build_ai_runs",
        "ck_build_ai_runs_ck_build_ai_runs_response_hash",
        "ck_build_ai_runs_response_hash",
    ),
    (
        "build_ai_runs",
        "ck_build_ai_runs_ck_build_ai_runs_status",
        "ck_build_ai_runs_status",
    ),
    ("builds", "ck_builds_ck_builds_artifact_sha256", "ck_builds_artifact_sha256"),
    ("builds", "ck_builds_ck_builds_config_object", "ck_builds_config_object"),
    (
        "builds",
        "ck_builds_ck_builds_embedding_dimensions",
        "ck_builds_embedding_dimensions",
    ),
    (
        "builds",
        "ck_builds_ck_builds_enrichment_sha256",
        "ck_builds_enrichment_sha256",
    ),
    ("builds", "ck_builds_ck_builds_failed_error", "ck_builds_failed_error"),
    ("builds", "ck_builds_ck_builds_manifest_sha256", "ck_builds_manifest_sha256"),
    ("builds", "ck_builds_ck_builds_ready_complete", "ck_builds_ready_complete"),
    (
        "builds",
        "ck_builds_ck_builds_sequence_positive",
        "ck_builds_sequence_positive",
    ),
    (
        "builds",
        "ck_builds_ck_builds_terminal_completion",
        "ck_builds_terminal_completion",
    ),
    (
        "canonical_snapshots",
        "ck_canonical_snapshots_ck_canonical_snapshots_sha256",
        "ck_canonical_snapshots_sha256",
    ),
    (
        "canonical_snapshots",
        "ck_canonical_snapshots_ck_canonical_snapshots_source_versions",
        "ck_canonical_snapshots_source_versions",
    ),
    (
        "deployments",
        "ck_deployments_ck_deployments_failure_complete",
        "ck_deployments_failure_complete",
    ),
    (
        "deployments",
        "ck_deployments_ck_deployments_manifest_sha256",
        "ck_deployments_manifest_sha256",
    ),
    (
        "deployments",
        "ck_deployments_ck_deployments_route_priority_range",
        "ck_deployments_route_priority_range",
    ),
    (
        "deployments",
        "ck_deployments_ck_deployments_running_complete",
        "ck_deployments_running_complete",
    ),
    (
        "deployments",
        "ck_deployments_ck_deployments_runtime_identity_nonempty",
        "ck_deployments_runtime_identity_nonempty",
    ),
    (
        "deployments",
        "ck_deployments_ck_deployments_stopped_complete",
        "ck_deployments_stopped_complete",
    ),
    (
        "document_index_generations",
        "ck_document_index_generations_ck_document_index_chunk_m_5953",
        "ck_document_index_chunk_manifest_sha256",
    ),
    (
        "document_index_generations",
        "ck_document_index_generations_ck_document_index_generat_84cb",
        "ck_document_index_generations_dimensions",
    ),
    (
        "document_index_generations",
        "ck_document_index_generations_ck_document_index_generat_9d27",
        "ck_document_index_generation_key_sha256",
    ),
    (
        "document_index_generations",
        "ck_document_index_generations_ck_document_index_generat_e5b3",
        "ck_document_index_generations_chunk_count",
    ),
    (
        "document_index_generations",
        "ck_document_index_generations_ck_document_index_generat_f44e",
        "ck_document_index_generations_source_fingerprint",
    ),
    (
        "document_index_generations",
        "ck_document_index_generations_ck_document_index_ready_complete",
        "ck_document_index_ready_complete",
    ),
    (
        "mcp_access_tokens",
        "ck_mcp_access_tokens_ck_mcp_access_tokens_identity",
        "ck_mcp_access_tokens_identity",
    ),
    (
        "mcp_access_tokens",
        "ck_mcp_access_tokens_ck_mcp_access_tokens_revocation_expiry",
        "ck_mcp_access_tokens_revocation_expiry",
    ),
    (
        "mcp_access_tokens",
        "ck_mcp_access_tokens_ck_mcp_access_tokens_sha256",
        "ck_mcp_access_tokens_sha256",
    ),
    (
        "mcp_auth_configs",
        "ck_mcp_auth_configs_ck_mcp_auth_config_json_shapes",
        "ck_mcp_auth_config_json_shapes",
    ),
    (
        "mcp_auth_configs",
        "ck_mcp_auth_configs_ck_mcp_auth_config_mode_shape",
        "ck_mcp_auth_config_mode_shape",
    ),
    (
        "operation_exclusions",
        "ck_operation_exclusions_ck_operation_exclusions_reason__6cbd",
        "ck_operation_exclusions_reason_code_nonempty",
    ),
    (
        "operation_exclusions",
        "ck_operation_exclusions_ck_operation_exclusions_reason_nonempty",
        "ck_operation_exclusions_reason_nonempty",
    ),
    (
        "project_credentials",
        "ck_project_credentials_ck_project_credentials_payload_nonempty",
        "ck_project_credentials_payload_nonempty",
    ),
    (
        "project_sources",
        "ck_project_sources_ck_project_sources_origin_url",
        "ck_project_sources_origin_url",
    ),
    (
        "source_versions",
        "ck_source_versions_ck_source_versions_byte_size",
        "ck_source_versions_byte_size",
    ),
    (
        "source_versions",
        "ck_source_versions_ck_source_versions_nonempty",
        "ck_source_versions_nonempty",
    ),
    (
        "source_versions",
        "ck_source_versions_ck_source_versions_sha256",
        "ck_source_versions_sha256",
    ),
    (
        "validation_reports",
        "ck_validation_reports_ck_validation_reports_count_consistency",
        "ck_validation_reports_count_consistency",
    ),
    (
        "validation_reports",
        "ck_validation_reports_ck_validation_reports_counts_nonnegative",
        "ck_validation_reports_counts_nonnegative",
    ),
    (
        "validation_reports",
        "ck_validation_reports_ck_validation_reports_coverage_range",
        "ck_validation_reports_coverage_range",
    ),
    (
        "validation_reports",
        "ck_validation_reports_ck_validation_reports_findings_no_7333",
        "ck_validation_reports_findings_nonnegative",
    ),
    (
        "validation_reports",
        "ck_validation_reports_ck_validation_reports_pass_integrity",
        "ck_validation_reports_pass_integrity",
    ),
)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    preparer = connection.dialect.identifier_preparer
    table_names = {table_name for table_name, _, _ in _LEGACY_CHECK_CONSTRAINT_RENAMES}
    existing_by_table = {
        table_name: {
            constraint["name"]
            for constraint in inspector.get_check_constraints(table_name)
            if constraint.get("name")
        }
        for table_name in table_names
    }

    for table_name, legacy_name, canonical_name in _LEGACY_CHECK_CONSTRAINT_RENAMES:
        existing_names = existing_by_table[table_name]
        if legacy_name not in existing_names:
            continue
        if canonical_name in existing_names:
            raise RuntimeError(
                f"Both legacy and canonical check constraints exist on {table_name}: "
                f"{legacy_name}, {canonical_name}"
            )
        quoted_table = preparer.quote_identifier(table_name)
        quoted_legacy = preparer.quote_identifier(legacy_name)
        quoted_canonical = preparer.quote_identifier(canonical_name)
        op.execute(
            sa.text(
                f"ALTER TABLE {quoted_table} RENAME CONSTRAINT "
                f"{quoted_legacy} TO {quoted_canonical}"
            )
        )
        existing_names.remove(legacy_name)
        existing_names.add(canonical_name)


def downgrade() -> None:
    # Canonical names are valid at revision 0019. Reintroducing the legacy naming
    # drift would make a downgraded database disagree with the 0019 ORM metadata.
    pass
