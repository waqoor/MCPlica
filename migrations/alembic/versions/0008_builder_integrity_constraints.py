"""Enforce builder integrity and optimize control-plane listing paths.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unique constraints already own indexes; retaining separate unique indexes doubles
    # write amplification without improving lookup behavior.
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_index("ix_projects_mcp_hostname", table_name="projects")

    # Replace single-column list indexes with covering order indexes used by the APIs.
    for table, name in (
        ("audit_events", "ix_audit_events_project_id"),
        ("audit_events", "ix_audit_events_event_type"),
        ("builds", "ix_builds_project_id"),
        ("builds", "ix_builds_status"),
        ("build_ai_runs", "ix_build_ai_runs_build_id"),
        ("project_sources", "ix_project_sources_project_id"),
        ("source_versions", "ix_source_versions_source_id"),
    ):
        op.drop_index(name, table_name=table)
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index(
        "ix_audit_events_project_created",
        "audit_events",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_type_created",
        "audit_events",
        ["event_type", "created_at"],
    )
    op.create_index("ix_builds_project_created", "builds", ["project_id", "created_at"])
    op.create_index("ix_builds_status_created", "builds", ["status", "created_at"])
    op.create_index(
        "ix_build_ai_runs_build_created",
        "build_ai_runs",
        ["build_id", "created_at"],
    )
    op.create_index(
        "ix_project_sources_project_created",
        "project_sources",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_source_versions_source_created",
        "source_versions",
        ["source_id", "created_at"],
    )

    op.create_check_constraint(
        "ck_source_versions_sha256",
        "source_versions",
        "content_sha256 ~ '^[a-f0-9]{64}$'",
    )
    op.create_check_constraint(
        "ck_source_versions_nonempty",
        "source_versions",
        "byte_size > 0",
    )
    op.create_check_constraint(
        "ck_project_credentials_payload_nonempty",
        "project_credentials",
        "octet_length(encrypted_payload) > 0 AND char_length(btrim(key_version)) > 0",
    )

    op.create_check_constraint(
        "ck_document_index_generation_key_sha256",
        "document_index_generations",
        "generation_key ~ '^[a-f0-9]{64}$'",
    )
    op.create_check_constraint(
        "ck_document_index_chunk_manifest_sha256",
        "document_index_generations",
        "chunk_manifest_sha256 IS NULL OR chunk_manifest_sha256 ~ '^[a-f0-9]{64}$'",
    )
    op.create_check_constraint(
        "ck_document_index_ready_complete",
        "document_index_generations",
        "status <> 'ready'::document_index_status OR ("
        "completed_at IS NOT NULL AND dimensions IS NOT NULL AND "
        "chunk_manifest_storage_key IS NOT NULL AND chunk_manifest_sha256 IS NOT NULL AND ("
        "(chunk_count = 0 AND dimensions = 0 AND collection_name IS NULL) OR "
        "(chunk_count > 0 AND dimensions > 0 AND embedding_model IS NOT NULL "
        "AND collection_name IS NOT NULL)))",
    )

    op.create_check_constraint(
        "ck_builds_config_object",
        "builds",
        "jsonb_typeof(build_config_json) = 'object'",
    )
    for column in ("enrichment_sha256", "manifest_sha256", "artifact_sha256"):
        op.create_check_constraint(
            f"ck_builds_{column}",
            "builds",
            f"{column} IS NULL OR {column} ~ '^[a-f0-9]{{64}}$'",
        )
    op.create_check_constraint(
        "ck_builds_terminal_completion",
        "builds",
        "(status IN ('READY'::build_status, 'FAILED'::build_status, "
        "'CANCELLED'::build_status)) = (completed_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_builds_ready_complete",
        "builds",
        "status <> 'READY'::build_status OR ("
        "canonical_snapshot_id IS NOT NULL AND enrichment_json IS NOT NULL "
        "AND enrichment_sha256 IS NOT NULL AND manifest_sha256 IS NOT NULL "
        "AND manifest_storage_key IS NOT NULL AND artifact_sha256 IS NOT NULL "
        "AND artifact_storage_key IS NOT NULL AND analysis_model IS NOT NULL "
        "AND validation_model IS NOT NULL AND prompt_bundle_version IS NOT NULL "
        "AND error_code IS NULL AND error_summary IS NULL)",
    )
    op.create_check_constraint(
        "ck_builds_failed_error",
        "builds",
        "status <> 'FAILED'::build_status OR error_code IS NOT NULL",
    )

    op.create_check_constraint(
        "ck_build_ai_runs_status",
        "build_ai_runs",
        "status IN ('succeeded', 'failed')",
    )
    op.create_check_constraint(
        "ck_build_ai_runs_input_hash",
        "build_ai_runs",
        "input_context_sha256 ~ '^[a-f0-9]{64}$'",
    )
    op.create_check_constraint(
        "ck_build_ai_runs_response_hash",
        "build_ai_runs",
        "response_sha256 IS NULL OR response_sha256 ~ '^[a-f0-9]{64}$'",
    )
    op.create_check_constraint(
        "ck_build_ai_runs_latency",
        "build_ai_runs",
        "latency_ms IS NULL OR latency_ms >= 0",
    )
    op.create_check_constraint(
        "ck_build_ai_runs_outcome",
        "build_ai_runs",
        "(status = 'succeeded' AND response_json IS NOT NULL "
        "AND response_sha256 IS NOT NULL AND error_code IS NULL) OR "
        "(status = 'failed' AND response_json IS NULL AND error_code IS NOT NULL)",
    )

    op.create_check_constraint(
        "ck_validation_reports_count_consistency",
        "validation_reports",
        "operation_excluded_count <= operation_source_count AND "
        "operation_expected_count = operation_source_count - operation_excluded_count",
    )
    op.create_check_constraint(
        "ck_validation_reports_pass_integrity",
        "validation_reports",
        "overall_status <> 'pass'::validation_status OR ("
        "blocking_error_count = 0 AND "
        "operation_generated_count = operation_expected_count AND coverage_percent = 100)",
    )
    op.create_check_constraint(
        "ck_operation_exclusions_reason_code_nonempty",
        "operation_exclusions",
        "char_length(btrim(reason_code)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_operation_exclusions_reason_code_nonempty",
        "operation_exclusions",
        type_="check",
    )
    op.drop_constraint(
        "ck_validation_reports_pass_integrity",
        "validation_reports",
        type_="check",
    )
    op.drop_constraint(
        "ck_validation_reports_count_consistency",
        "validation_reports",
        type_="check",
    )
    for name in (
        "ck_build_ai_runs_outcome",
        "ck_build_ai_runs_latency",
        "ck_build_ai_runs_response_hash",
        "ck_build_ai_runs_input_hash",
        "ck_build_ai_runs_status",
    ):
        op.drop_constraint(name, "build_ai_runs", type_="check")
    for name in (
        "ck_builds_failed_error",
        "ck_builds_ready_complete",
        "ck_builds_terminal_completion",
        "ck_builds_artifact_sha256",
        "ck_builds_manifest_sha256",
        "ck_builds_enrichment_sha256",
        "ck_builds_config_object",
    ):
        op.drop_constraint(name, "builds", type_="check")
    for name in (
        "ck_document_index_ready_complete",
        "ck_document_index_chunk_manifest_sha256",
        "ck_document_index_generation_key_sha256",
    ):
        op.drop_constraint(name, "document_index_generations", type_="check")
    op.drop_constraint(
        "ck_project_credentials_payload_nonempty",
        "project_credentials",
        type_="check",
    )
    op.drop_constraint("ck_source_versions_nonempty", "source_versions", type_="check")
    op.drop_constraint("ck_source_versions_sha256", "source_versions", type_="check")

    for table, name in (
        ("source_versions", "ix_source_versions_source_created"),
        ("project_sources", "ix_project_sources_project_created"),
        ("build_ai_runs", "ix_build_ai_runs_build_created"),
        ("builds", "ix_builds_status_created"),
        ("builds", "ix_builds_project_created"),
        ("audit_events", "ix_audit_events_type_created"),
        ("audit_events", "ix_audit_events_project_created"),
        ("audit_events", "ix_audit_events_created_at"),
    ):
        op.drop_index(name, table_name=table)
    op.create_index("ix_source_versions_source_id", "source_versions", ["source_id"])
    op.create_index("ix_project_sources_project_id", "project_sources", ["project_id"])
    op.create_index("ix_build_ai_runs_build_id", "build_ai_runs", ["build_id"])
    op.create_index("ix_builds_status", "builds", ["status"])
    op.create_index("ix_builds_project_id", "builds", ["project_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"])
    op.create_index("ix_projects_mcp_hostname", "projects", ["mcp_hostname"], unique=True)
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
