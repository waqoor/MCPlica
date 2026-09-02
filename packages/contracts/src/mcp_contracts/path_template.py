"""Shared parsing for OpenAPI simple path parameter expressions."""


def path_parameter_names(path: str) -> tuple[str, ...]:
    """Return placeholders in source order and reject malformed brace syntax.

    Expressions may be embedded in a segment and a segment may contain more
    than one expression. MCPlica supports exactly one parameter name per
    expression.
    """

    names: list[str] = []
    index = 0
    while index < len(path):
        character = path[index]
        if character == "}":
            raise ValueError("path template contains an unmatched closing brace")
        if character != "{":
            index += 1
            continue
        closing = path.find("}", index + 1)
        if closing < 0:
            raise ValueError("path template contains an unmatched opening brace")
        name = path[index + 1 : closing]
        if not name or "{" in name or "/" in name:
            raise ValueError("path template contains an invalid parameter expression")
        names.append(name)
        index = closing + 1
    return tuple(names)
