import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.records import compute_records


def test_compute_records_ignores_missing_scores():
    rows = pd.DataFrame(
        [
            {"team": "AAA", "points_for": 10, "points_against": 7},
            {"team": "AAA", "points_for": -1, "points_against": -1},
            {"team": "AAA", "points_for": 3, "points_against": 3},
        ]
    )

    records = compute_records(rows)

    assert records["AAA"]["wins"] == 1
    assert records["AAA"]["losses"] == 0
    assert records["AAA"]["ties"] == 1
    assert records["AAA"]["win_pct"] == (1 + 0.5) / 2
