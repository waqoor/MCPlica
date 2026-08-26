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
