from typing import Any

import pytest
from mcp_contracts import ApiInventory
from pydantic import ValidationError


def test_api_inventory_contract_enforces_path_parameters() -> None:
    document: dict[str, Any] = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "operations": [
            {
                "method": "GET",
                "path": "/products/{product_id}",
                "parameters": [
                    {
                        "name": "product_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "OK"}},
            }
        ],
    }
    parsed = ApiInventory.model_validate(document)
    assert parsed.operations[0].parameters[0].name == "product_id"

    document["operations"][0]["parameters"] = []
    with pytest.raises(ValidationError, match="path parameter mismatch"):
        ApiInventory.model_validate(document)


@pytest.mark.parametrize(
    ("path", "names"),
    [
        ("/files/{id}.json", ["id"]),
        ("/coordinates/{lat},{lon}", ["lat", "lon"]),
        ("/owners/{owner}/files/{id}.{extension}", ["owner", "id", "extension"]),
    ],
)
def test_api_inventory_accepts_embedded_and_multiple_path_parameters(
    path: str,
    names: list[str],
) -> None:
    document: dict[str, Any] = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "operations": [
            {
                "method": "GET",
                "path": path,
                "parameters": [
                    {
                        "name": name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                    for name in names
                ],
                "responses": {"200": {"description": "OK"}},
            }
        ],
    }
    parsed = ApiInventory.model_validate(document)
    assert [item.name for item in parsed.operations[0].parameters] == names


@pytest.mark.parametrize("path", ["/files/{id", "/files/id}", "/files/{}", "/files/{{id}}"])
def test_api_inventory_rejects_malformed_path_parameter_braces(path: str) -> None:
    document: dict[str, Any] = {
        "schema": "api-inventory/v1",
        "name": "Inventory",
        "servers": [{"id": "primary", "url": "https://inventory.example.com"}],
        "operations": [
            {
                "method": "GET",
                "path": path,
                "parameters": [],
                "responses": {"200": {"description": "OK"}},
            }
        ],
    }
    with pytest.raises(ValidationError, match="path template"):
        ApiInventory.model_validate(document)
