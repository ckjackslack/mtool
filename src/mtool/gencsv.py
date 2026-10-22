"""Generate a synthetic employee CSV (sample data for ``mtool stats``).

Rows come from a "fake data provider" - by default a seeded ``faker.Faker``
instance (optional dependency, ``pip install 'mtool[gen]'``). Any object with
``name()``, ``phone_number()``, ``job()``, ``company()`` and
``pyint(min_value, max_value)`` works, which keeps this testable without Faker.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from typing import Any, Protocol, TextIO

COLUMNS = ("full_name", "age", "phone", "position", "company")


class FakeProvider(Protocol):
    def name(self) -> str: ...
    def pyint(self, min_value: int = ..., max_value: int = ...) -> int: ...
    def phone_number(self) -> str: ...
    def job(self) -> str: ...
    def company(self) -> str: ...


class GenError(RuntimeError):
    pass


def make_faker(locale: str = "en_US", seed: int | None = None) -> Any:
    try:
        import faker
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise GenError(
            "generating data needs Faker: pip install 'mtool[gen]'"
        ) from exc
    try:
        fake = faker.Faker(locale)
    except AttributeError as exc:
        raise GenError(f"unknown Faker locale {locale!r}") from exc
    if seed is not None:
        fake.seed_instance(seed)
    return fake


def generate_rows(
    count: int, provider: FakeProvider, min_age: int = 18, max_age: int = 65
) -> Iterator[tuple[str, int, str, str, str]]:
    if count < 0:
        raise ValueError("count must be >= 0")
    if min_age > max_age:
        raise ValueError("min_age must be <= max_age")
    for _ in range(count):
        yield (
            provider.name(),
            provider.pyint(min_value=min_age, max_value=max_age),
            provider.phone_number(),
            provider.job(),
            provider.company(),
        )


def write_csv(rows: Iterator[tuple[Any, ...]], out: TextIO) -> int:
    """Write header + rows as proper CSV (quoting handled by ``csv``). Returns row count."""
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    n = 0
    for row in rows:
        writer.writerow(row)
        n += 1
    return n
