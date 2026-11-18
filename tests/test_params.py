"""Phase 1: parameter registry, provenance rules, derived formulas, gate, table export."""

import textwrap

import pytest

from wpvrec.params import ProvenanceGateError, RegistryError, load_registry
from wpvrec.params import formula as fx
from wpvrec.params.table import to_csv, to_latex, to_markdown

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures" / "params"

# One id per row of specification Appendix A (some rows are split into several ids).
APPENDIX_A_IDS = {
    # A.1 warehouse
    "system_type", "avsrs_installed_power", "location", "shift_start", "shift_end",
    "working_days_per_year", "missions_per_day", "n_inbound", "n_picks", "n_replenishment",
    "n_reslotting", "shiftable_share", "pallet_mass", "e_mission_gross", "regen_share",
    "e_mission_net", "e_mission_sbsrs", "avsrs_standby_kw", "capacity_c", "rho_max",
    "n_pwl_cuts", "n_forklifts", "forklift_kwh_per_h", "forklift_use_hours", "battery_kwh",
    "charger_kw", "soc_min", "charge_efficiency", "charging_hours", "lighting_kw", "offices_kw",
    "other_kw", "offshift_standby_kw", "fixed_load_shape",
    # A.2 PV
    "pv_profile", "pv_kwp", "pv_losses", "pv_azimuth", "pv_tilt",
    # A.3 orders
    "cutoff_hour", "order_share_previous_evening", "order_arrival_start", "order_arrival_end",
    "predictable_share", "prepick_lead", "inbound_start", "inbound_end", "buffer_max",
    "stock_initial_days", "stock_min_days", "kappa",
    # A.4 REC
    "rec_member_set", "n_households", "n_businesses", "household_profile", "household_kwh",
    "business_mwh", "business_profile", "w_rec_annual",
    # A.5 incentives
    "tip_fixed", "tip_var_reference", "tip_var_cap", "tip_regional_bonus", "theta_enterprise",
    "zonal_price", "pi_arera", "beta_warehouse",
    # A.6 economics
    "pv_cost", "pv_om", "pv_insurance", "pv_life", "investment_incentive", "rec_fee",
    "retail_price", "discount_rate",
}  # fmt: skip
APPENDIX_A_CHECKS = {"site_consumption_split", "annual_site_consumption", "specific_yield"}


@pytest.fixture(scope="module")
def base():
    return load_registry()


# ---- base registry ------------------------------------------------------------------------
def test_all_appendix_rows_present(base):
    assert APPENDIX_A_IDS - base.params.keys() == set()
    assert APPENDIX_A_CHECKS - base.checks.keys() == set()


def test_every_entry_has_provenance(base):
    for pid, p in base.params.items():
        assert p.source.strip() and p.unit.strip(), pid
        assert p.source_type is not None or p.status == "to_be_provided", pid
        assert p.source_type != "placeholder_test_only", pid


def test_derived_values(base):
    v = base.values
    assert v["e_mission_gross"] == pytest.approx(75 / 3.6)
    assert v["e_mission_net"] == pytest.approx(75 / 3.6 * (1 - 0.283))
    assert v["mission_cycle_time"] == pytest.approx(88268 / 5772 * 3600 / 1200)
    assert v["capacity_c"] == pytest.approx(5 * 3600 / v["mission_cycle_time"])
    assert v["kappa"] == pytest.approx(6.5)
    assert v["stock_initial"] == pytest.approx(650)
    assert v["stock_min"] == pytest.approx(195)
    assert v["dock_hours_total"] == 20
    assert v["w_rec_annual"] == pytest.approx(195)


def test_sanity_capacity_vs_average_load(base):
    # Spec Sect. 3.5: 1,500 missions in 16 h is about 94 missions/h on average.
    hours = base.value("shift_end") - base.value("shift_start")
    average = base.value("missions_per_day") / hours
    assert average == pytest.approx(93.75)
    assert base.value("rho_max") * base.value("capacity_c") > average


def test_base_gates(base):
    base.gate("model")  # the LP inputs are all available
    with pytest.raises(ProvenanceGateError, match="household_profile"):
        base.gate("rec")
    with pytest.raises(ProvenanceGateError, match="retail_price"):
        base.gate("economics")


def test_provenance_summary(base):
    s = base.provenance_summary()
    assert len(s["registry_sha256"]) == 64
    assert sum(s["counts_by_source_type"].values()) == len(base.params)
    assert s["parameters"]["capacity_c"]["source_type"] == "derived"
    assert any(w.startswith("capacity_c") for w in s["warnings"])


# ---- gate on fixtures ---------------------------------------------------------------------
def test_gate_blocks_missing_capacity_with_clear_message():
    reg = load_registry(FIXTURES / "missing_c.yaml")
    assert reg.values["capacity_c"] is None
    with pytest.raises(ProvenanceGateError) as err:
        reg.gate("model")
    msg = str(err.value)
    assert "capacity_c" in msg and "needs n_active_shuttles" in msg
    assert "n_active_shuttles" in msg and "To be provided by Ema" in msg
    assert "mission_cycle_time: test placeholder" in msg
    with pytest.raises(ProvenanceGateError, match="household_kwh: test placeholder"):
        reg.gate("rec")


# ---- schema violations --------------------------------------------------------------------
GOOD = """
  - id: a
    group: warehouse
    description: an input
    value: 2
    unit: kW
    source: somewhere
    source_type: literature
    used_by: [model]
"""


def _write(tmp_path, entries, extra=""):
    f = tmp_path / "reg.yaml"
    f.write_text("parameters:\n" + textwrap.dedent(entries) + extra)
    return f


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (GOOD.replace("literature", "rumour"), "unknown source_type"),
        (GOOD.replace("    source: somewhere\n", ""), "source"),
        (GOOD.replace("    source: somewhere\n", "    source: '  '\n"), "blank"),
        (GOOD.replace("    unit: kW\n", ""), "unit"),
        (GOOD.replace("    source_type: literature\n", ""), "source_type missing"),
        (GOOD.replace("literature", "assumption"), "needs a sensitivity range"),
        (GOOD.replace("literature", "placeholder_test_only"), "only in tests/fixtures"),
        (GOOD.replace("value: 2", "value: null"), "status must be to_be_derived"),
        (GOOD + "    formula: '1 + 1'\n", "only derived entries may have a formula"),
        (GOOD.replace("literature", "derived") + "    formula: '1 + 1'\n", "do not write them"),
        (GOOD.replace("id: a", "id: BadId"), "snake_case"),
        (GOOD.replace("[model]", "[nobody]"), "unknown used_by"),
        (GOOD.replace("warehouse", "garden"), "unknown group"),
        (GOOD + "    sensitivity: {low: 5, high: 1}\n", "low 5.0 > high 1.0"),
    ],
)
def test_schema_violations(tmp_path, entry, message):
    with pytest.raises(RegistryError, match=message):
        load_registry(_write(tmp_path, entry))


def test_assumption_with_range_is_valid(tmp_path):
    entry = GOOD.replace("literature", "assumption") + "    sensitivity: {low: 1, high: 3}\n"
    assert load_registry(_write(tmp_path, entry)).value("a") == 2


DERIVED = """
  - id: b
    group: warehouse
    description: derived
    value: null
    formula: "{formula}"
    unit: kW
    source: formula
    source_type: derived
    used_by: [model]
"""


def test_formula_unknown_id(tmp_path):
    with pytest.raises(RegistryError, match="unknown ids"):
        load_registry(_write(tmp_path, GOOD + DERIVED.format(formula="a * zz")))


def test_formula_cycle(tmp_path):
    c = DERIVED.replace("id: b", "id: c").format(formula="b + 1")
    with pytest.raises(RegistryError, match="circular"):
        load_registry(_write(tmp_path, GOOD + DERIVED.format(formula="c * a") + c))


def test_duplicate_id(tmp_path):
    with pytest.raises(RegistryError, match="duplicate"):
        load_registry(_write(tmp_path, GOOD + GOOD))


def test_consistency_rule(tmp_path):
    with pytest.raises(RegistryError, match="consistency rule violated: a > 3"):
        load_registry(_write(tmp_path, GOOD, "consistency:\n  - 'a > 3'\n"))
    assert load_registry(_write(tmp_path, GOOD, "consistency:\n  - 'a == 2'\n"))


def test_derived_with_units(tmp_path):
    reg = load_registry(_write(tmp_path, GOOD + DERIVED.format(formula="a * SECONDS_PER_HOUR")))
    assert reg.value("b") == 7200


@pytest.mark.parametrize(
    "expr", ["__import__('os')", "a.real", "'text'", "[a]", "a if a else 1", "open('x')"]
)
def test_formula_rejects_unsafe(expr):
    with pytest.raises(fx.FormulaError):
        fx.evaluate(expr, {"a": 1})


# ---- table export -------------------------------------------------------------------------
def test_table_exports(base):
    csv_text = to_csv(base)
    assert csv_text.splitlines()[0].startswith("Group,Parameter")
    assert len(csv_text.strip().splitlines()) == len(base.params) + 1  # no multi-line cells
    md = to_markdown(base)
    assert "| Ipotesi |" in md and "| Letteratura |" in md and "| Derivato |" in md
    tex = to_latex(base)
    assert tex.startswith(r"\begin{longtable}") and r"\%" in tex
    assert "Hourly capacity of the AVS/RS" in to_markdown(base, lang="en")


def test_docs_table_up_to_date(base):
    """docs/params_base.md is generated from the registry; regenerate it after any change."""
    doc = FIXTURES.parents[2] / "docs" / "params_base.md"
    assert doc.read_text(encoding="utf-8") == to_markdown(base), (
        "run: wpvrec params table --format markdown -o docs/params_base.md"
    )
