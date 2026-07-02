"""Stage 0 picker: load_ruleset selects an era by fiscal_year_end and adapts it
to a contracts.Ruleset (route-A adapter). These tests pin the selection windows,
the boundary (half-open [from, until)) behaviour, the None degradation, and the
EraRuleset -> Ruleset field mapping (expected_items order, reserved_items, and
the deliberate CONDITIONAL exclusion).
"""

from __future__ import annotations

from sec10k.ruleset.loader import load_ruleset, _pick_era


# --------------------------------------------------------------------------- #
# 1. representative FYE -> correct era (checked via the adapted Ruleset)
# --------------------------------------------------------------------------- #
def test_pick_1994_era_shape():
    rs = load_ruleset("1994-06-30")
    ei = rs.expected_items
    # era_1994: no 1A/1B/7A/9A (ABSENT), no 1C/15/16 (not introduced yet)
    for absent in ("1A", "1B", "7A", "9A", "1C", "15", "16"):
        assert absent not in ei, absent
    # but the era_1994 core items are present, incl. Item 14 (Exhibits, Part IV)
    for present in ("1", "2", "3", "4", "14"):
        assert present in ei, present


def test_pick_2005_era_shape():
    rs = load_ruleset("2010-12-31")
    ei = rs.expected_items
    for present in ("1A", "1B", "7A", "9A", "9B", "14", "15"):
        assert present in ei, present
    assert "1C" not in ei          # 1C not introduced until 2023


def test_pick_2020_era_shape():
    rs = load_ruleset("2022-06-30")
    assert "6" in rs.reserved_items   # Item 6 [Reserved] since 2021
    assert "1C" not in rs.expected_items


def test_pick_2023_era_shape():
    rs = load_ruleset("2024-12-31")
    assert "1C" in rs.expected_items  # Item 1C introduced 2023-12-15


# --------------------------------------------------------------------------- #
# 2. half-open boundary [from, until): the from-date belongs to the newer era
# --------------------------------------------------------------------------- #
def test_boundary_2005_from_is_inclusive():
    assert _pick_era("2005-12-01").era_id == "era_2005"


def test_boundary_2020_from_is_inclusive():
    assert _pick_era("2021-08-09").era_id == "era_2020"


def test_boundary_2023_from_is_inclusive():
    assert _pick_era("2023-12-15").era_id == "era_2023"


def test_boundary_just_before_2023_is_era_2020():
    # one day before the 1C threshold -> still era_2020 (no 1C)
    assert _pick_era("2023-12-14").era_id == "era_2020"


# --------------------------------------------------------------------------- #
# 3. None degradation -> newest era
# --------------------------------------------------------------------------- #
def test_none_fye_degrades_to_newest_era():
    assert _pick_era(None).era_id == "era_2023"
    rs = load_ruleset(None)
    assert "1C" in rs.expected_items   # newest-era ruleset


# --------------------------------------------------------------------------- #
# 4. RESERVED mapping correctness
# --------------------------------------------------------------------------- #
def test_reserved_items_mapping():
    assert "6" in load_ruleset("2022-06-30").reserved_items   # era_2020
    assert "6" in load_ruleset("2024-12-31").reserved_items   # era_2023
    # era_1994's Item 6 is REQUIRED (Selected Financial Data), not RESERVED
    assert "6" not in load_ruleset("1994-06-30").reserved_items


# --------------------------------------------------------------------------- #
# 5. CONDITIONAL items are excluded from expected_items (but exist in the era)
# --------------------------------------------------------------------------- #
def test_conditional_items_excluded_from_expected():
    rs = load_ruleset("2024-12-31")   # era_2023
    assert "9C" not in rs.expected_items   # CONDITIONAL -> excluded
    assert "16" not in rs.expected_items   # CONDITIONAL -> excluded
    # they DO exist in the underlying era (just not "expected to be present")
    era = _pick_era("2024-12-31")
    era_ids = {r.item_id for r in era.items}
    assert "9C" in era_ids and "16" in era_ids


# --------------------------------------------------------------------------- #
# 6. adapted Ruleset provides a working order_index() over expected_items
# --------------------------------------------------------------------------- #
def test_order_index_works_on_adapted_ruleset():
    rs = load_ruleset("2024-12-31")
    # order is preserved from era.items: 1 before 1A before 1C before 2 ...
    assert rs.order_index("1") < rs.order_index("1A") < rs.order_index("1C") < rs.order_index("2")
    assert rs.order_index("nonexistent") is None
