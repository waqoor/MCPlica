from app.parsers.identifiers import operation_key, server_key, tool_name_seed


def test_identifiers_are_stable_and_semantic() -> None:
    assert operation_key("get", "/pets/{id}", None) == operation_key("GET", "/pets/{id}", None)
    assert operation_key("GET", "/pets/{id}", "getPet") != operation_key("GET", "/pets/{id}", None)
    assert tool_name_seed("GET", "/pets/{pet_id}", "getPet") == "get_pet"
    assert tool_name_seed("DELETE", "/pets/{pet_id}", None) == "delete_pets_pet_id"
    assert server_key("https://api.example.com") == server_key("https://api.example.com")
