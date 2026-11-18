"""Household hourly load shape, read from any documented CSV.

The approved source, Besagni, Premoli Vila, Borgarello (2020), Buildings 10(12) 217,
doi:10.3390/buildings10120217, cannot be digitised: its Figure 13 ("Load profiles of
monitored households' clusters", p. 15) reproduces Figure 12 (daily usage probability of
microwaves). The household shape is therefore an open input (registry ``household_profile``).

Accepted CSV layouts (comma separated, header required):
- ``slot,share`` with 24 rows: one daily shape for every month and day type;
- ``month,day_type,1,...,24``: shares per month and day type ("working", "non_working").
Shares are normalised so that each daily shape sums to 1; the daily energy is the annual
consumption divided by 365 (no seasonal modulation unless the CSV provides it).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DAY_TYPES = ("working", "non_working")


def load_shape(path: Path) -> pd.DataFrame:
    """Daily shapes indexed by (month, day_type), columns slot 1..24, rows summing to 1."""
    df = pd.read_csv(path)
    if {"slot", "share"} <= set(df.columns):
        s = df.set_index("slot")["share"].reindex(range(1, 25)).to_numpy(dtype=float)
        rows = [(m, d) for m in range(1, 13) for d in DAY_TYPES]
        out = pd.DataFrame(np.tile(s, (len(rows), 1)), columns=range(1, 25))
        out.index = pd.MultiIndex.from_tuples(rows, names=["month", "day_type"])
    elif {"month", "day_type"} <= set(df.columns):
        out = df.set_index(["month", "day_type"])
        out.columns = [int(c) for c in out.columns]
    else:
        raise ValueError(f"{path}: unknown household profile layout {list(df.columns)}")
    if np.isnan(out.to_numpy()).any() or (out.to_numpy() < 0).any():
        raise ValueError(f"{path}: missing or negative values")
    return out.div(out.sum(axis=1), axis=0)
