import json
from typing import cast

import mcp.types as types

from app.clients.api_client import UpstreamResult
from app.executor.errors import RuntimeExecutionError


def map_upstream_result(result: UpstreamResult) -> types.CallToolResult:
    if result.is_error:
        payload = result.data
        structured: dict[str, object] | None = None
    else:
        payload = {
            "status": result.status_code,
            "contentType": result.content_type,
            "body": result.data,
        }
        structured = cast(dict[str, object], payload)
    if isinstance(payload, str):
        text = payload
    elif payload is None:
        text = ""
    else:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
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
