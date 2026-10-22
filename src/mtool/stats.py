"""CSV statistics: load a table and summarise its columns.

``load_table`` does the parsing from any text stream; the summary functions
are pure and operate on lists of strings.
"""

from __future__ import annotations

import csv
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TextIO


class StatsError(ValueError):
    """Raised for user-facing problems (bad CSV, unknown column...)."""


@dataclass
class Table:
    columns: list[str]
    rows: list[dict[str, str]]

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rows), len(self.columns)

    def column(self, name: str) -> list[str]:
        if name not in self.columns:
            raise StatsError(
                f"unknown column {name!r}; available: {', '.join(self.columns)}"
            )
        return [row.get(name) or "" for row in self.rows]


def load_table(stream: TextIO, delimiter: str = ",") -> Table:
    """Parse CSV with a header row. Raises ``StatsError`` on malformed input."""
    reader = csv.DictReader(stream, delimiter=delimiter, restkey="__extra__")
    if not reader.fieldnames:
        raise StatsError("CSV file is empty (no header row)")
    columns = [c.strip() for c in reader.fieldnames]
    if len(set(columns)) != len(columns):
        raise StatsError("CSV header contains duplicate column names")
    rows: list[dict[str, str]] = []
    try:
        for lineno, raw in enumerate(reader, start=2):
            if "__extra__" in raw:
                raise StatsError(
                    f"line {lineno}: expected {len(columns)} fields, got more "
                    "(unquoted delimiter inside a value?)"
                )
            rows.append({c.strip(): (v or "") for c, v in raw.items()})
    except csv.Error as exc:
        raise StatsError(f"malformed CSV: {exc}") from exc
    return Table(columns=columns, rows=rows)


def parse_number(value: str) -> float | None:
    """Parse a numeric cell; returns None for anything that isn't a number."""
    text = value.strip().replace("_", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number


@dataclass
class ColumnSummary:
    name: str
    count: int
    missing: int
    unique: int
    kind: str  # "numeric" or "text"
    mean: float | None = None
    median: float | None = None
    stdev: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    top: list[tuple[str, int]] = field(default_factory=list)


def summarize_column(name: str, values: Sequence[str], top_n: int = 3) -> ColumnSummary:
    """Summarise one column.

    A column counts as numeric when every non-empty value parses as a number.
    """
    present = [v for v in values if v.strip()]
    missing = len(values) - len(present)
    unique = len(set(present))
    numbers = [parse_number(v) for v in present]
    if present and all(n is not None for n in numbers):
        nums = [n for n in numbers if n is not None]
        return ColumnSummary(
            name=name,
            count=len(nums),
            missing=missing,
            unique=unique,
            kind="numeric",
            mean=statistics.fmean(nums),
            median=statistics.median(nums),
            stdev=statistics.stdev(nums) if len(nums) > 1 else 0.0,
            minimum=min(nums),
            maximum=max(nums),
        )
    counter = Counter(present)
    top = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    return ColumnSummary(
        name=name, count=len(present), missing=missing, unique=unique, kind="text", top=top
    )


def summarize(table: Table, columns: Sequence[str] | None = None) -> list[ColumnSummary]:
    names = list(columns) if columns else table.columns
    return [summarize_column(n, table.column(n)) for n in names]


def _num(x: float | None) -> str:
    if x is None:
        return "-"
    if float(x).is_integer():
        return str(int(x))
    return f"{x:.4g}" if abs(x) >= 1e6 else f"{x:.2f}"


def format_summary(table: Table, summaries: Sequence[ColumnSummary]) -> str:
    rows, cols = table.shape
    lines = [f"Shape: {rows} rows x {cols} columns", ""]
    for s in summaries:
        lines.append(f"{s.name} ({s.kind})")
        lines.append(f"  count: {s.count}  missing: {s.missing}  unique: {s.unique}")
        if s.kind == "numeric":
            lines.append(
                f"  mean: {_num(s.mean)}  median: {_num(s.median)}  stdev: {_num(s.stdev)}"
            )
            lines.append(f"  min: {_num(s.minimum)}  max: {_num(s.maximum)}")
        elif s.top and s.unique < s.count:  # skip "top" when every value is distinct
            top = ", ".join(f"{v!r} x{c}" for v, c in s.top)
            lines.append(f"  top: {top}")
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def summary_as_dict(table: Table, summaries: Sequence[ColumnSummary]) -> dict:
    from dataclasses import asdict

    rows, cols = table.shape
    return {"rows": rows, "columns": cols, "summary": [asdict(s) for s in summaries]}
