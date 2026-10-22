import csv
import io

import pytest

from mtool import gencsv


def test_generate_rows_uses_provider(stub_provider):
    rows = list(gencsv.generate_rows(2, stub_provider, min_age=21, max_age=30))
    assert rows == [
        ("Person 1", 21, "555-0100", "Engineer, software", "Smith, Jones and Brown"),
        ("Person 2", 21, "555-0100", "Engineer, software", "Smith, Jones and Brown"),
    ]


def test_generate_rows_zero(stub_provider):
    assert list(gencsv.generate_rows(0, stub_provider)) == []


@pytest.mark.parametrize("kw", [{"count": -1}, {"count": 1, "min_age": 9, "max_age": 1}])
def test_generate_rows_validation(stub_provider, kw):
    count = kw.pop("count")
    with pytest.raises(ValueError):
        list(gencsv.generate_rows(count, stub_provider, **kw))


def test_write_csv_round_trips_commas(stub_provider):
    buf = io.StringIO()
    n = gencsv.write_csv(gencsv.generate_rows(3, stub_provider), buf)
    assert n == 3
    buf.seek(0)
    rows = list(csv.reader(buf))
    assert rows[0] == list(gencsv.COLUMNS)
    assert all(len(r) == 5 for r in rows)
    assert rows[1][4] == "Smith, Jones and Brown"  # quoted, not split


def test_make_faker_seeded_is_reproducible():
    pytest.importorskip("faker")
    a = list(gencsv.generate_rows(5, gencsv.make_faker(seed=7)))
    b = list(gencsv.generate_rows(5, gencsv.make_faker(seed=7)))
    assert a == b
    assert all(18 <= row[1] <= 65 for row in a)


def test_make_faker_bad_locale():
    pytest.importorskip("faker")
    with pytest.raises(gencsv.GenError, match="locale"):
        gencsv.make_faker("xx_YY")
