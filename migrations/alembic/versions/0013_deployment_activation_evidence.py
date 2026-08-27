"""Require durable activation evidence for rollback candidates.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-27
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migration 0009 conservatively inferred legacy activation from started_at. A stopped
    # pre-activation container can also have started_at, so retain that inference only when a
    # durable running event exists (or the deployment is still running) and runtime identity is
    # complete. Ambiguous legacy rows fail closed and cannot be rollback targets.
    op.execute(
        """
        UPDATE deployments AS deployment
        SET activated_at = NULL,
            activation_phase = NULL
        WHERE deployment.activated_at IS NOT NULL
          AND (
            deployment.started_at IS NULL
            OR deployment.container_id IS NULL
            OR deployment.image_digest IS NULL
            OR (
              deployment.activation_phase = 'legacy_running'
              AND deployment.status <> 'running'::deployment_status
              AND NOT EXISTS (
                SELECT 1
                FROM audit_events AS event
                WHERE event.entity_type = 'deployment'
                  AND event.entity_id = deployment.id
                  AND event.event_type = 'deployment.running'
              )
            )
          )
        """
    )
    op.create_check_constraint(
        "ck_deployments_activation_success_evidence",
        "deployments",
        "activated_at IS NULL OR (started_at IS NOT NULL AND container_id IS NOT NULL "
        "AND image_digest IS NOT NULL AND (activation_phase = 'legacy_running' OR ("
        "activation_verified_at IS NOT NULL AND activation_proof_sha256 IS NOT NULL "
        "AND activation_proof_sha256 ~ '^[a-f0-9]{64}$')))",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_deployments_activation_success_evidence",
        "deployments",
        type_="check",
    )
