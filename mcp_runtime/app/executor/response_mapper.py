import json
from typing import cast

import mcp.types as types

from app.clients.api_client import UpstreamResult
from app.executor.errors import RuntimeExecutionError


def map_upstream_result(result: UpstreamResult) -> types.CallToolResult:
    if isinstance(result.data, str):
        text = result.data
    elif result.data is None:
        text = ""
    else:
        text = json.dumps(result.data, ensure_ascii=False, separators=(",", ":"))
    structured: object | None = None
    data = result.data
    if isinstance(data, dict):
        structured = cast(dict[str, object], data)
    elif isinstance(data, list):
        structured = cast(list[object], data)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structured_content=structured,
        is_error=result.is_error,
        _meta={"httpStatus": result.status_code, "contentType": result.content_type},
    )


def map_runtime_error(error: RuntimeExecutionError) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": error.code, "message": error.safe_message},
                    separators=(",", ":"),
                ),
            )
        ],
        is_error=True,
        _meta={"errorCode": error.code},
    )
