class RuntimeExecutionError(Exception):
    __slots__ = ("code", "safe_message")

    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)

    def __str__(self) -> str:
        return self.safe_message


class ArgumentValidationError(RuntimeExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_arguments", message)


class DestinationPolicyError(RuntimeExecutionError):
    def __init__(self, message: str = "Upstream destination is blocked by runtime policy") -> None:
        super().__init__("destination_blocked", message)


class UpstreamTimeoutError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__("upstream_timeout", "The upstream API timed out")


class UpstreamConnectionError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__("upstream_unavailable", "The upstream API is unavailable")


class UpstreamResponseTooLargeError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__(
            "response_too_large", "The upstream response exceeded its configured limit"
        )


class UpstreamRequestTooLargeError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__("request_too_large", "The upstream request exceeded its configured limit")


class UpstreamContentTypeError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported_content_type", "The upstream response content type is unsupported"
        )


class UpstreamResponseContractError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__(
            "upstream_response_contract_mismatch",
            "The upstream API response did not match its compiled contract",
        )


class UpstreamAuthenticationError(RuntimeExecutionError):
    def __init__(self) -> None:
        super().__init__("upstream_authentication_failed", "Upstream authentication failed")


class RuntimeConfigurationError(RuntimeExecutionError):
    def __init__(self, message: str = "Runtime authentication is not configured correctly") -> None:
        super().__init__("runtime_configuration_error", message)
