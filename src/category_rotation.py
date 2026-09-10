from __future__ import annotations

from datetime import date


def query_for_day(queries: list[str], run_date: date | None = None) -> str:
    """Pick one stable daily query while rotating through the full list."""
    if not queries:
        raise ValueError("Category must define at least one discovery query")
    selected_date = run_date or date.today()
    return queries[selected_date.toordinal() % len(queries)]
