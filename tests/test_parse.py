import pytest

from core.parse import (ParseError, format_heats, format_time, parse_bibs,
                        parse_heats, parse_sprints, parse_time, parse_time_safe)


def test_parse_sprints():
    assert parse_sprints("2,3,4,5-1,2,3,4") == [[2, 3, 4, 5], [1, 2, 3, 4]]
    assert parse_sprints("7") == [[7]]
    assert parse_sprints("") == []
    assert parse_sprints("  2, 3 - 4 ,5  ") == [[2, 3], [4, 5]]
    assert parse_sprints("2,3-4,5-") == [[2, 3], [4, 5]]      # trailing separator


def test_parse_heats():
    assert parse_heats("1,2-3,4/5,6-7,8") == [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
    assert parse_heats("1-2/3-4") == [[[1], [2]], [[3], [4]]]
    assert parse_heats("1,2,3,4/5,6,7,8") == [[[1, 2, 3, 4]], [[5, 6, 7, 8]]]
    assert parse_heats("") == []


def test_format_heats_roundtrip():
    txt = "1,2-3,4/5,6-7,8"
    assert format_heats(parse_heats(txt)) == txt


def test_parse_bibs():
    assert parse_bibs("7, 12, 3") == [7, 12, 3]
    assert parse_bibs("1,2-3/4") == [1, 2, 3, 4]
    assert parse_bibs("") == []


def test_bad_input_raises_a_readable_error():
    with pytest.raises(ParseError, match="non è un dorsale valido"):
        parse_sprints("2,x,4")
    with pytest.raises(ParseError, match="batteria 2"):
        parse_heats("1-2/3-y")
    with pytest.raises(ParseError, match="sprint 2"):
        parse_sprints("1,2-3,4,cinque")
    assert parse_sprints("1,,2-3") == [[1, 2], [3]]           # empty token skipped


@pytest.mark.parametrize("text,ms", [
    ("3:31.370", 211370),
    ("03:31,370", 211370),
    ("0:34,670", 34670),
    ("34,67", 34670),
    ("2:40.161", 160161),
    ("12", 12000),
])
def test_parse_time(text, ms):
    assert parse_time(text) == ms


def test_parse_time_rejects_garbage():
    with pytest.raises(ParseError):
        parse_time("abc")
    with pytest.raises(ParseError):
        parse_time("")
    ms, err = parse_time_safe("nope")
    assert ms is None and "non valido" in err


def test_format_time():
    assert format_time(211370) == "3:31,370"
    assert format_time(34670) == "34,670"
    assert format_time(None) == ""
    assert format_time(211370, decimals=0) == "3:31"


def test_time_roundtrip():
    for txt in ("3:31,370", "2:40,161", "0:34,670", "1:04,000"):
        ms = parse_time(txt)
        assert parse_time(format_time(ms)) == ms
