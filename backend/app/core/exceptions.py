class MCPlicaError(Exception):
    code = "MCP_LICA_ERROR"


class NotFoundError(MCPlicaError):
    code = "NOT_FOUND"


class ConflictError(MCPlicaError):
    code = "CONFLICT"


class ValidationError(MCPlicaError):
    code = "VALIDATION_ERROR"


class ClientError(MCPlicaError):
    code = "CLIENT_ERROR"
