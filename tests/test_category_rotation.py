from datetime import date, timedelta

import pytest

from src.category_rotation import query_for_day


def test_query_rotation_is_stable_within_a_day():
    queries = ["deodorant", "baby care", "mother care", "feminine wash"]
    run_date = date(2026, 9, 10)
    assert query_for_day(queries, run_date) == query_for_day(queries, run_date)


def test_query_rotation_advances_on_the_next_day():
    queries = ["deodorant", "baby care", "mother care", "feminine wash"]
    run_date = date(2026, 9, 10)
    assert query_for_day(queries, run_date) != query_for_day(queries, run_date + timedelta(days=1))


def test_query_rotation_rejects_empty_configuration():
    with pytest.raises(ValueError, match="at least one"):
        query_for_day([], date(2026, 9, 10))
