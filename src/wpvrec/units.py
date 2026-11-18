"""Unit conversions: the only place where conversion constants may appear.

The no-magic-numbers test (specification Section 3.3) allows numeric literals
in the model, REC and economics code only if they are 0, 1, 24, 100 or one of
the names defined here. These are definitions of units, not data. The same
names can be used in the formulas of derived registry entries.
"""

WH_PER_KWH = 1_000
KWH_PER_MWH = 1_000
SECONDS_PER_HOUR = 3_600
HOURS_PER_DAY = 24
PERCENT = 100
KJ_PER_WH = 3.6
