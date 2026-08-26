from collections.abc import Mapping
from typing import Any


class MCPlicaError(Exception):
    code = "MCPLICA_ERROR"
    status_code = 400

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class NotFoundError(MCPlicaError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(MCPlicaError):
    code = "CONFLICT"
    status_code = 409


class InvalidStateError(MCPlicaError):
    code = "INVALID_STATE"
    status_code = 409


class PermissionDeniedError(MCPlicaError):
    code = "PERMISSION_DENIED"
    status_code = 403


class AuthenticationError(MCPlicaError):
    code = "AUTHENTICATION_REQUIRED"
    status_code = 401


class RateLimitError(AuthenticationError):
    code = "RATE_LIMITED"
    status_code = 429


class ValidationError(MCPlicaError):
    code = "VALIDATION_ERROR"
    status_code = 422


class PayloadTooLargeError(ValidationError):
    code = "PAYLOAD_TOO_LARGE"
    status_code = 413


class SecurityPolicyError(MCPlicaError):
    code = "SECURITY_POLICY_BLOCK"
    status_code = 403


class ClientError(MCPlicaError):
    code = "CLIENT_ERROR"
    status_code = 502


class ClientConnectionError(ClientError):
    code = "CLIENT_CONNECTION_ERROR"


class ClientTimeoutError(ClientError):
    code = "CLIENT_TIMEOUT"
    status_code = 504


class ClientAuthenticationError(ClientError):
    code = "CLIENT_AUTHENTICATION_ERROR"


class ClientRateLimitError(ClientError):
    code = "CLIENT_RATE_LIMIT"
    status_code = 503


class ClientResponseError(ClientError):
    code = "CLIENT_RESPONSE_ERROR"


class ClientUnavailableError(ClientError):
    code = "CLIENT_UNAVAILABLE"
    status_code = 503


class SourceParseError(ValidationError):
    code = "SOURCE_PARSE_ERROR"


class ReferenceResolutionError(SourceParseError):
    code = "REFERENCE_RESOLUTION_ERROR"


class CanonicalizationError(ValidationError):
    code = "CANONICALIZATION_ERROR"


class IndexingError(MCPlicaError):
    code = "INDEXING_ERROR"


class AIAnalysisError(MCPlicaError):
    code = "AI_ANALYSIS_ERROR"


class CompilationError(ValidationError):
    code = "COMPILATION_ERROR"


class CoverageValidationError(ValidationError):
    code = "COVERAGE_VALIDATION_ERROR"


class ManifestValidationError(ValidationError):
    code = "MANIFEST_VALIDATION_ERROR"


class ProtocolValidationError(ValidationError):
    code = "PROTOCOL_VALIDATION_ERROR"


class PackagingError(MCPlicaError):
    code = "PACKAGING_ERROR"


class DockerOperationError(ClientError):
    code = "DOCKER_OPERATION_ERROR"


class RuntimeStartupError(DockerOperationError):
    code = "RUNTIME_STARTUP_ERROR"


class RuntimeHealthError(DockerOperationError):
    code = "RUNTIME_HEALTH_ERROR"


class HostnameConflictError(ConflictError):
    code = "HOSTNAME_CONFLICT"


class SecretMaterializationError(MCPlicaError):
    code = "SECRET_MATERIALIZATION_ERROR"
    status_code = 500
