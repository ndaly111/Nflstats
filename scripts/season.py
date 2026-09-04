"""Single source of truth for which NFL season the pipeline should target.

nflverse only serves a season once it has kicked off, and it defines kickoff as
the Thursday following Labor Day. A plain calendar rule like "September or
later" rolls over up to nine days early and asks nflverse for a season it flatly
refuses to serve (``ValueError: Season must be between 1999 and 2025``), which
is what broke the nightly refresh on 2026-09-01.

Mirroring ``nflreadpy.get_current_season()`` keeps the two in step;
``tests/test_unpublished_season.py`` asserts they still agree.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union


def season_opener(year: int) -> date:
    """Return the Thursday following Labor Day (the first Monday in September)."""
    for day in range(1, 8):
        candidate = date(year, 9, day)
        if candidate.weekday() == 0:  # Monday
            return candidate + timedelta(days=3)
    raise AssertionError(f"September {year} somehow has no Monday in its first week")


def current_nfl_season(today: Optional[Union[date, datetime]] = None) -> int:
    """Return the newest season nflverse has data for.

    Season N runs from its September opener into January-February of year N+1,
    so before this year's opener the current season is still the prior year.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    elif isinstance(today, datetime):
        today = today.date()
    return today.year if today >= season_opener(today.year) else today.year - 1
