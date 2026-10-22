import io
import json

import pytest

from mtool import stats

CSV = """name,age,score,city
Ann,30,1.5,Oslo
Bob,40,2.5,Oslo
Cid,,3.5,"Rome, IT"
Dee,50,x,
"""


def table(text=CSV, **kw):
    return stats.load_table(io.StringIO(text), **kw)


def test_load_table_shape_and_quoting():
    t = table()
    assert t.shape == (4, 4)
    assert t.columns == ["name", "age", "score", "city"]
    assert t.column("city") == ["Oslo", "Oslo", "Rome, IT", ""]


def test_load_table_custom_delimiter():
    t = table("a;b\n1;2\n", delimiter=";")
    assert t.columns == ["a", "b"]
    assert t.column("b") == ["2"]


def test_load_table_short_rows_are_missing_values():
    t = table("a,b\n1\n")
    assert t.column("b") == [""]


def test_load_table_empty():
    with pytest.raises(stats.StatsError, match="empty"):
        table("")


def test_load_table_header_only():
    assert table("a,b\n").shape == (0, 2)


def test_load_table_too_many_fields():
    # the shape of the original prototype's broken employee.csv
    bad = "full_name,age\n'Denise',40,'Blake, Bailey'\n"
    with pytest.raises(stats.StatsError, match="line 2: expected 2 fields"):
        table(bad)


def test_load_table_duplicate_header():
    with pytest.raises(stats.StatsError, match="duplicate"):
        table("a,a\n1,2\n")


def test_unknown_column():
    with pytest.raises(stats.StatsError, match="unknown column 'zzz'; available: name"):
        table().column("zzz")


@pytest.mark.parametrize(
    "value,expected",
    [("1", 1.0), (" 2.5 ", 2.5), ("-3", -3.0), ("1e3", 1000.0), ("1_000", 1000.0),
     ("", None), ("abc", None), ("nan", None), ("inf", None)],
)
def test_parse_number(value, expected):
    assert stats.parse_number(value) == expected


def test_summarize_numeric_column_with_missing():
    s = stats.summarize_column("age", ["30", "40", "", "50"])
    assert s.kind == "numeric"
    assert (s.count, s.missing, s.unique) == (3, 1, 3)
    assert s.mean == 40
    assert s.median == 40
    assert s.minimum == 30 and s.maximum == 50
    assert s.stdev == pytest.approx(10.0)


def test_summarize_single_value_stdev_zero():
    assert stats.summarize_column("x", ["7"]).stdev == 0.0


def test_summarize_mixed_column_is_text():
    s = stats.summarize_column("score", ["1.5", "x", "1.5"])
    assert s.kind == "text"
    assert s.top[0] == ("1.5", 2)


def test_summarize_all_missing_is_text():
    s = stats.summarize_column("e", ["", " "])
    assert s.kind == "text" and s.count == 0 and s.missing == 2 and s.top == []


def test_summarize_top_n_ties_sorted():
    s = stats.summarize_column("c", ["b", "a", "b", "a", "c"], top_n=2)
    assert s.top == [("a", 2), ("b", 2)]


def test_summarize_selected_columns():
    out = stats.summarize(table(), ["age"])
    assert [s.name for s in out] == ["age"]


def test_summarize_all_columns_default():
    assert [s.name for s in stats.summarize(table())] == ["name", "age", "score", "city"]


def test_format_summary():
    t = table()
    text = stats.format_summary(t, stats.summarize(t))
    assert text.startswith("Shape: 4 rows x 4 columns")
    assert "age (numeric)" in text
    assert "mean: 40  median: 40  stdev: 10" in text
    assert "min: 30  max: 50" in text
    assert "city (text)" in text
    assert "top: 'Oslo' x2" in text
    # all-distinct column has no 'top' line
    assert "top: 'Ann'" not in text


def test_summary_as_dict_is_json_serialisable():
    t = table()
    d = stats.summary_as_dict(t, stats.summarize(t, ["age"]))
    data = json.loads(json.dumps(d))
    assert data["rows"] == 4
    assert data["summary"][0]["mean"] == 40
