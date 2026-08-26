from mcp_contracts import CanonicalApi, CanonicalOperation

from app.core.canonical_json import canonical_sha256
from app.domain.analysis import EnrichmentSnapshot, OperationEnrichment
from app.domain.builds import BuildConfiguration, BuildRecord, BuildStatus, BuildTrigger
from app.domain.indexing import DocumentIndexGenerationRecord, IndexGenerationStatus


def select_reusable_enrichment(
    *,
    current_build: BuildRecord,
    previous_build: BuildRecord,
    current_canonical: CanonicalApi,
    previous_canonical: CanonicalApi,
    current_generation: DocumentIndexGenerationRecord,
    previous_generation: DocumentIndexGenerationRecord,
    current_config: BuildConfiguration,
    previous_config: BuildConfiguration,
    previous_enrichment: EnrichmentSnapshot,
    prompt_template_id: str,
    prompt_template_version: str,
) -> dict[str, OperationEnrichment]:
    """Select conservative reuse candidates; uncertainty always falls back to AI."""
    if (
        current_build.trigger is not BuildTrigger.SOURCE_CHANGE
        or previous_build.status is not BuildStatus.READY
        or current_build.previous_build_id != previous_build.id
        or current_build.analysis_model is None
        or current_build.analysis_model != previous_build.analysis_model
        or current_build.prompt_bundle_version != previous_build.prompt_bundle_version
        or current_build.compiler_version != previous_build.compiler_version
        or current_generation.status is not IndexGenerationStatus.READY
        or previous_generation.status is not IndexGenerationStatus.READY
        or not _analysis_policy_matches(current_config, previous_config)
    ):
        return {}
    if current_config.include_documentation_in_analysis and not _documentation_context_matches(
        current_build,
        previous_build,
        current_generation,
        previous_generation,
        current_config,
        previous_config,
    ):
        return {}

    previous_operations = {operation.key: operation for operation in previous_canonical.operations}
    reusable: dict[str, OperationEnrichment] = {}
    for operation in current_canonical.operations:
        prior_operation = previous_operations.get(operation.key)
        prior_enrichment = previous_enrichment.operations.get(operation.key)
        if prior_operation is None or prior_enrichment is None:
            continue
        provenance = prior_enrichment.provenance
        if (
            provenance.model != current_build.analysis_model
            or provenance.prompt_template_id != prompt_template_id
            or provenance.prompt_template_version != prompt_template_version
            or _operation_fingerprint(current_canonical, operation)
            != _operation_fingerprint(previous_canonical, prior_operation)
        ):
            continue
        reusable[operation.key] = prior_enrichment
    return reusable


def _analysis_policy_matches(
    current: BuildConfiguration,
    previous: BuildConfiguration,
) -> bool:
    return (
        current.include_documentation_in_analysis == previous.include_documentation_in_analysis
        and current.max_context_chars == previous.max_context_chars
        and current.retrieval_top_k == previous.retrieval_top_k
    )


def _documentation_context_matches(
    current_build: BuildRecord,
    previous_build: BuildRecord,
    current: DocumentIndexGenerationRecord,
    previous: DocumentIndexGenerationRecord,
    current_config: BuildConfiguration,
    previous_config: BuildConfiguration,
) -> bool:
    return (
        current.source_fingerprint == previous.source_fingerprint
        and current.embedding_model == previous.embedding_model
        and current.dimensions == previous.dimensions
        and current_build.embedding_model == previous_build.embedding_model
        and current_config.document_max_text_chars == previous_config.document_max_text_chars
        and current_config.pdf_max_pages == previous_config.pdf_max_pages
        and current_config.documentation_chunk_chars == previous_config.documentation_chunk_chars
        and current_config.documentation_chunk_overlap_chars
        == previous_config.documentation_chunk_overlap_chars
        and current_config.max_document_chunks == previous_config.max_document_chunks
    )


def _operation_fingerprint(api: CanonicalApi, operation: CanonicalOperation) -> str:
    server = next((item for item in api.servers if item.key == operation.server_ref), None)
    scheme_names = {
        name for requirement in operation.security for name in requirement.scheme_scopes
    }
    security = {name: api.security_schemes.get(name) for name in sorted(scheme_names)}
    return canonical_sha256(
        {
            "operation": operation.model_dump(
                mode="json",
                by_alias=True,
                exclude={"semantic", "provenance"},
            ),
            "server": (
                server.model_dump(mode="json", by_alias=True, exclude={"source_ref"})
                if server is not None
                else None
            ),
            "security_schemes": {
                name: (
                    value.model_dump(mode="json", by_alias=True, exclude={"source_ref"})
                    if value is not None
                    else None
                )
                for name, value in security.items()
            },
        }
    )
