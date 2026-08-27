"""Add the durable runtime lifecycle command outbox.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


_RUNNING_COMPLETE_CONSTRAINT_NAMES = (
    "ck_deployments_running_complete",
    # Installations created before the check-constraint naming convention was
    # corrected applied the table prefix twice.  Those databases are valid 0008
    # installations and must remain upgradeable without an operator-side rename.
    "ck_deployments_ck_deployments_running_complete",
)


def _drop_running_complete_constraint() -> None:
    existing_names = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("deployments")
        if constraint.get("name")
    }
    for name in _RUNNING_COMPLETE_CONSTRAINT_NAMES:
        if name in existing_names:
            op.drop_constraint(op.f(name), "deployments", type_="check")


def upgrade() -> None:
    action = postgresql.ENUM("deploy", "stop", name="runtime_command_action", create_type=False)
    status = postgresql.ENUM(
        "pending",
        "dispatched",
        "running",
        "failed",
        "effective",
        name="runtime_command_status",
        create_type=False,
    )
    action.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "deployments",
        sa.Column(
            "previous_active_deployment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_deployments_previous_active_deployment_id_deployments",
        "deployments",
        "deployments",
        ["previous_active_deployment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "deployments",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("activation_phase", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("activation_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("activation_proof_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("auth_overlay_sha256", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_deployments_auth_overlay_sha256",
        "deployments",
        "auth_overlay_sha256 IS NULL OR auth_overlay_sha256 ~ '^[a-f0-9]{64}$'",
    )
    op.execute(
        "UPDATE deployments SET activated_at = started_at, activation_phase = 'legacy_running' "
        "WHERE started_at IS NOT NULL AND status IN ('running', 'stopping', 'stopped')"
    )
    op.create_check_constraint(
        "ck_deployments_activation_phase",
        "deployments",
        "activation_phase IS NULL OR activation_phase IN ("
        "'verified', 'retiring_previous', 'running', 'legacy_running', 'failed')",
    )
    op.create_check_constraint(
        "ck_deployments_activation_proof",
        "deployments",
        "activation_phase NOT IN ('verified', 'retiring_previous', 'running') OR ("
        "activation_verified_at IS NOT NULL AND activation_proof_sha256 IS NOT NULL "
        "AND activation_proof_sha256 ~ '^[a-f0-9]{64}$')",
    )
    _drop_running_complete_constraint()
    op.create_check_constraint(
        "ck_deployments_running_complete",
        "deployments",
        "status <> 'running'::deployment_status OR ("
        "container_id IS NOT NULL AND image_digest IS NOT NULL "
        "AND started_at IS NOT NULL AND activated_at IS NOT NULL "
        "AND activation_phase IN ('running', 'legacy_running') "
        "AND health_status = 'healthy')",
    )
    op.create_table(
        "runtime_lifecycle_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sequence",
            sa.BigInteger(),
            sa.Identity(start=1),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", action, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("reason", sa.String(length=160), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retryable", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_runtime_lifecycle_commands_attempt_count",
        ),
        sa.CheckConstraint(
            "char_length(btrim(reason)) > 0 AND char_length(btrim(idempotency_key)) > 0",
            name="ck_runtime_lifecycle_commands_identity_nonempty",
        ),
        sa.CheckConstraint(
            "(subject_type IS NULL) = (subject_id IS NULL)",
            name="ck_runtime_lifecycle_commands_subject_pair",
        ),
        sa.CheckConstraint(
            "(status = 'effective'::runtime_command_status AND effective_at IS NOT NULL "
            "AND failed_at IS NULL) OR "
            "(status = 'failed'::runtime_command_status AND failed_at IS NOT NULL "
            "AND last_error_code IS NOT NULL) OR "
            "status IN ('pending'::runtime_command_status, "
            "'dispatched'::runtime_command_status, 'running'::runtime_command_status)",
            name="ck_runtime_lifecycle_commands_status_shape",
        ),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("sequence", name="uq_runtime_lifecycle_commands_sequence"),
    )
    op.create_index(
        "ix_runtime_commands_dispatch_due",
        "runtime_lifecycle_commands",
        ["next_attempt_at", "created_at"],
        postgresql_where=sa.text(
            "status IN ('pending'::runtime_command_status, "
            "'dispatched'::runtime_command_status, 'running'::runtime_command_status, "
            "'failed'::runtime_command_status)"
        ),
    )
    op.create_index(
        "ix_runtime_commands_project_created",
        "runtime_lifecycle_commands",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_runtime_commands_subject_created",
        "runtime_lifecycle_commands",
        ["subject_type", "subject_id", "sequence"],
    )
    op.create_index(
        "ix_runtime_commands_transition",
        "runtime_lifecycle_commands",
        ["transition_id"],
    )


def downgrade() -> None:
    op.drop_table("runtime_lifecycle_commands")
    _drop_running_complete_constraint()
    op.create_check_constraint(
        "ck_deployments_running_complete",
        "deployments",
        "status <> 'running'::deployment_status OR ("
        "container_id IS NOT NULL AND image_digest IS NOT NULL "
        "AND started_at IS NOT NULL AND health_status = 'healthy')",
    )
    op.drop_constraint("ck_deployments_activation_proof", "deployments", type_="check")
    op.drop_constraint("ck_deployments_activation_phase", "deployments", type_="check")
    op.drop_column("deployments", "activation_proof_sha256")
    op.drop_column("deployments", "activation_verified_at")
    op.drop_column("deployments", "activation_phase")
    op.drop_column("deployments", "activated_at")
    op.drop_constraint("ck_deployments_auth_overlay_sha256", "deployments", type_="check")
    op.drop_column("deployments", "auth_overlay_sha256")
    op.drop_constraint(
        "fk_deployments_previous_active_deployment_id_deployments",
        "deployments",
        type_="foreignkey",
    )
    op.drop_column("deployments", "previous_active_deployment_id")
    postgresql.ENUM(name="runtime_command_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="runtime_command_action").drop(op.get_bind(), checkfirst=True)
