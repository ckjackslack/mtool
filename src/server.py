from itertools import count
from typing import NamedTuple

import flask
from flask import abort, jsonify, request


ID_GEN = count(start=1)
database = []

class Person(NamedTuple):
    id: int
    name: str

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, obj):
        assert isinstance(obj, dict), "data is invalid"
        assert len(obj) == 1, "too much keys"
        assert "name" in obj, "name not passed"
        obj.update({"id": next(ID_GEN)})
        return cls(**obj)


app = flask.Flask(__name__)

for name in ["John", "Tom", "Bob"]:
    database.append(Person(id=next(ID_GEN), name=name))


@app.route("/")
def main():
    return jsonify({"message": "Hello, world!"})


@app.route("/hello/<name>")
def greet(name):
    if request.method == "GET":
        return f"Hello, {name.capitalize()}!"
    else:
        abort(405)


@app.route("/people", methods=["GET", "POST"])
def people():
    if request.method == "GET":
        return jsonify({
            "people": [entry.to_dict() for entry in database],
        })
    elif request.method == "POST":
        try:
            data = request.get_json()
            new_person = Person.from_dict(data)
            if new_person.name in {e.name for e in database}:
                return jsonify({"error": "Given name already exists."}), 409
            else:
                database.append(new_person)
                return jsonify(new_person.to_dict())
        except AssertionError as e:
            return jsonify({"error": f"Validation error: {str(e)}"}), 400


if __name__ == '__main__':
    app.run(debug=False, port=8000)