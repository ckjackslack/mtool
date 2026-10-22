import pytest

from mtool.server import (
    ConflictError,
    PeopleStore,
    ValidationError,
    create_app,
    validate_payload,
)


def test_store_defaults_and_ids():
    store = PeopleStore()
    assert [(p.id, p.name) for p in store.all()] == [(1, "John"), (2, "Tom"), (3, "Bob")]
    assert store.add("Ann").id == 4
    assert store.get(4).name == "Ann"
    assert store.get(99) is None


def test_store_conflict_case_insensitive():
    store = PeopleStore(["Ann"])
    with pytest.raises(ConflictError):
        store.add("ann")


def test_stores_are_independent():
    a, b = PeopleStore([]), PeopleStore([])
    a.add("X")
    assert b.all() == []
    assert b.add("Y").id == 1


@pytest.mark.parametrize(
    "payload,msg",
    [
        (None, "JSON object"),
        ([1], "JSON object"),
        ({}, "name not passed"),
        ({"name": "a", "age": 3}, "unexpected keys: age"),
        ({"name": ""}, "non-empty"),
        ({"name": 5}, "non-empty"),
        ({"name": "x" * 101}, "longer than"),
    ],
)
def test_validate_payload_errors(payload, msg):
    with pytest.raises(ValidationError, match=msg):
        validate_payload(payload)


def test_validate_payload_strips():
    assert validate_payload({"name": "  Ann "}) == "Ann"


# --- Flask app via the test client (no sockets) ---


@pytest.fixture
def client():
    pytest.importorskip("flask")
    return create_app(PeopleStore(["John"])).test_client()


def test_index(client):
    assert client.get("/").get_json() == {"message": "Hello, world!"}


def test_hello(client):
    r = client.get("/hello/world")
    assert r.status_code == 200 and r.get_data(as_text=True) == "Hello, World!"


def test_people_crud(client):
    r = client.post("/people", json={"name": "Ann"})
    assert r.status_code == 201 and r.get_json() == {"id": 2, "name": "Ann"}
    assert client.get("/people").get_json()["people"][-1]["name"] == "Ann"
    assert client.get("/people/2").get_json()["name"] == "Ann"


def test_people_errors(client):
    assert client.post("/people", json={"name": "john"}).status_code == 409
    r = client.post("/people", data="not json", content_type="application/json")
    assert r.status_code == 400
    assert "Validation error" in r.get_json()["error"]
    assert client.get("/people/42").status_code == 404
    assert client.get("/nope").get_json() == {"error": "Not found."}
    assert client.delete("/people").status_code == 405
