"""A toy JSON API to exercise ``mtool web`` against (needs ``mtool[server]``).

Endpoints:
    GET  /                 -> {"message": "Hello, world!"}
    GET  /hello/<name>     -> "Hello, Name!"
    GET  /people           -> {"people": [...]}
    POST /people           -> create {"name": "..."}; 400 on bad input, 409 on duplicate
    GET  /people/<id>      -> one person or 404

The data lives in an in-memory ``PeopleStore`` (plain Python, no Flask) which
``create_app`` wires into a fresh Flask app, so every app/test gets its own data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import count
from typing import Any

DEFAULT_PEOPLE = ("John", "Tom", "Bob")
MAX_NAME_LENGTH = 100


class ValidationError(ValueError):
    pass


class ConflictError(ValueError):
    pass


@dataclass(frozen=True)
class Person:
    id: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_payload(payload: Any) -> str:
    """Return the cleaned name from a POST body or raise ``ValidationError``."""
    if not isinstance(payload, dict):
        raise ValidationError("body must be a JSON object")
    extra = set(payload) - {"name"}
    if extra:
        raise ValidationError(f"unexpected keys: {', '.join(sorted(extra))}")
    if "name" not in payload:
        raise ValidationError("name not passed")
    name = payload["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name must be a non-empty string")
    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"name longer than {MAX_NAME_LENGTH} characters")
    return name


class PeopleStore:
    def __init__(self, names: tuple[str, ...] | list[str] = DEFAULT_PEOPLE) -> None:
        self._ids = count(start=1)
        self._people: list[Person] = []
        for name in names:
            self.add(name)

    def all(self) -> list[Person]:
        return list(self._people)

    def get(self, person_id: int) -> Person | None:
        return next((p for p in self._people if p.id == person_id), None)

    def add(self, name: str) -> Person:
        if any(p.name.lower() == name.lower() for p in self._people):
            raise ConflictError("Given name already exists.")
        person = Person(id=next(self._ids), name=name)
        self._people.append(person)
        return person


def create_app(store: PeopleStore | None = None):
    try:
        from flask import Flask, jsonify, request
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("the server needs Flask: pip install 'mtool[server]'") from exc

    app = Flask(__name__)
    app.config["store"] = store if store is not None else PeopleStore()

    def error(message: str, status: int):
        return jsonify({"error": message}), status

    @app.get("/")
    def index():
        return jsonify({"message": "Hello, world!"})

    @app.get("/hello/<name>")
    def greet(name: str):
        return f"Hello, {name.capitalize()}!"

    @app.get("/people")
    def list_people():
        return jsonify({"people": [p.to_dict() for p in app.config["store"].all()]})

    @app.post("/people")
    def add_person():
        payload = request.get_json(silent=True)
        try:
            person = app.config["store"].add(validate_payload(payload))
        except ValidationError as exc:
            return error(f"Validation error: {exc}", 400)
        except ConflictError as exc:
            return error(str(exc), 409)
        return jsonify(person.to_dict()), 201

    @app.get("/people/<int:person_id>")
    def get_person(person_id: int):
        person = app.config["store"].get(person_id)
        if person is None:
            return error("Not found.", 404)
        return jsonify(person.to_dict())

    @app.errorhandler(404)
    def not_found(_exc):
        return error("Not found.", 404)

    @app.errorhandler(405)
    def method_not_allowed(_exc):
        return error("Method not allowed.", 405)

    return app
