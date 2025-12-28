from __future__ import annotations

from typing import Optional

import pandas as pd


def compute_records(game_rows: Optional[pd.DataFrame]) -> dict[str, dict[str, int | float | str]]:
    """Compute wins/losses/ties and win% from per-team game rows.

    Games with missing scores (points_for/points_against < 0 or NaN) are ignored.
    """

    if game_rows is None or game_rows.empty:
        return {}
    if not {"points_for", "points_against"}.issubset(game_rows.columns):
        return {}

    records: dict[str, dict[str, int | float | str]] = {}
    for team, group in game_rows.groupby("team"):
        wins = losses = ties = 0
        counted = 0
        for _, row in group.iterrows():
            pf = pd.to_numeric(row.get("points_for"), errors="coerce")
            pa = pd.to_numeric(row.get("points_against"), errors="coerce")
            if pd.isna(pf) or pd.isna(pa) or pf < 0 or pa < 0:
                continue
            counted += 1
            if pf > pa:
                wins += 1
            elif pf < pa:
                losses += 1
            else:
                ties += 1
        if counted:
            record_str = f"{wins}-{losses}-{ties}" if ties else f"{wins}-{losses}"
            win_pct = (wins + 0.5 * ties) / counted
            records[str(team)] = {
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "record": record_str,
                "win_pct": win_pct,
            }
    return records

