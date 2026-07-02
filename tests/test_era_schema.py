"""Schema-mechanics tests for the declarative era-ruleset (Stage 0).

These exercise the schema + validators with minimal DUMMY data only — they do
NOT assert any real regulatory fact (real era data is filled in a later step).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sec10k.contracts import LegalStructure
from sec10k.ruleset.era import (
    ERA_1994,
    ERA_2005,
    ERA_2020,
    ERA_2023,
    EraRuleset,
    EvidenceLevel,
    ItemExpectation,
    ItemRule,
    Part,
)


def _rule(item_id: str, exp=ItemExpectation.REQUIRED, part=Part.PART_I, topic="Dummy") -> ItemRule:
    return ItemRule(item_id=item_id, expectation=exp, part=part, topic=topic)


def _absent(item_id: str, topic="Dummy") -> ItemRule:
    return ItemRule(item_id=item_id, expectation=ItemExpectation.ABSENT, part=None, topic=topic)


def test_build_valid_era_ruleset():
    era = EraRuleset(
        era_id="era_dummy",
        effective_from_fye="2020-01-01",
        effective_until_fye="2023-12-15",
        items=[
            _rule("1", ItemExpectation.REQUIRED, Part.PART_I, "Business"),
            _rule("1A", ItemExpectation.REQUIRED, Part.PART_I, "Risk Factors"),
            _rule("6", ItemExpectation.RESERVED, Part.PART_II, "Reserved"),
            _absent("1C", "Cybersecurity"),
        ],
        legal_structures=[LegalStructure(name="standard")],
        evidence_level=EvidenceLevel.SEC_PRIMARY,
        pending_notes=["dummy note"],
        unenforced_rules=["dummy stayed rule"],
    )
    assert era.era_id == "era_dummy"
    assert [r.item_id for r in era.items] == ["1", "1A", "6", "1C"]
    assert era.items[2].expectation is ItemExpectation.RESERVED
    assert era.items[3].expectation is ItemExpectation.ABSENT
    assert era.items[1].part is Part.PART_I
    assert era.evidence_level is EvidenceLevel.SEC_PRIMARY
    # open-interval newest era: bounds may be None
    open_era = EraRuleset(
        era_id="era_open", effective_from_fye="2023-12-15", effective_until_fye=None,
        items=[_rule("1")],
        evidence_level=EvidenceLevel.REAL_FILING,
    )
    assert open_era.effective_until_fye is None


def test_validator_rejects_duplicate_item_id():
    with pytest.raises(ValidationError):
        EraRuleset(
            era_id="era_dup",
            items=[_rule("1"), _rule("1")],  # same item_id twice
            evidence_level=EvidenceLevel.PENDING,
        )


def test_validator_rejects_inverted_fye_window():
    with pytest.raises(ValidationError):
        EraRuleset(
            era_id="era_bad_window",
            effective_from_fye="2023-12-15",   # from AFTER until -> degenerate window
            effective_until_fye="2021-08-09",
            items=[_rule("1")],
            evidence_level=EvidenceLevel.PENDING,
        )


def test_validator_allows_absent_item_with_part():
    # New rule: ABSENT does NOT enforce part — giving an ABSENT item a Part is
    # now legal (part is simply not checked for ABSENT/CONDITIONAL).
    era = EraRuleset(
        era_id="era_absent_with_part",
        items=[ItemRule(item_id="1A", expectation=ItemExpectation.ABSENT,
                        part=Part.PART_I, topic="absent-but-parted, allowed now")],
        evidence_level=EvidenceLevel.PENDING,
    )
    assert era.items[0].part is Part.PART_I


def test_validator_rejects_required_item_without_part():
    with pytest.raises(ValidationError):
        EraRuleset(
            era_id="era_present_no_part",
            items=[ItemRule(item_id="1", expectation=ItemExpectation.REQUIRED,
                            part=None, topic="oops")],  # REQUIRED must have a Part
            evidence_level=EvidenceLevel.PENDING,
        )


def test_validator_rejects_reserved_item_without_part():
    with pytest.raises(ValidationError):
        EraRuleset(
            era_id="era_reserved_no_part",
            items=[ItemRule(item_id="6", expectation=ItemExpectation.RESERVED,
                            part=None, topic="oops")],  # RESERVED must have a Part
            evidence_level=EvidenceLevel.PENDING,
        )


def test_validator_allows_conditional_item_without_part():
    # New rule: CONDITIONAL does NOT enforce part — part=None is legal (e.g. a
    # Form 10-K Summary that spans the whole form and belongs to no single Part).
    era = EraRuleset(
        era_id="era_conditional_no_part",
        items=[ItemRule(item_id="16", expectation=ItemExpectation.CONDITIONAL,
                        part=None, topic="Form 10-K Summary")],
        evidence_level=EvidenceLevel.PENDING,
    )
    assert era.items[0].part is None
    assert era.items[0].expectation is ItemExpectation.CONDITIONAL


# --------------------------------------------------------------------------- #
# era_1994 data (uses the real ERA_1994 constant, not dummy data)
# --------------------------------------------------------------------------- #
def test_era_1994_constructs_and_is_self_consistent():
    # ERA_1994 building at import time already ran every validator (18 unique
    # item_ids, ABSENT items part=None, present items have a Part). Re-assert.
    assert ERA_1994.era_id == "era_1994"
    assert ERA_1994.effective_from_fye is None
    assert ERA_1994.effective_until_fye == "2005-12-01"
    assert ERA_1994.evidence_level is EvidenceLevel.REAL_FILING
    assert len(ERA_1994.items) == 18
    assert len({r.item_id for r in ERA_1994.items}) == 18


def test_era_1994_item_14_is_part_iv_required():
    by_id = {r.item_id: r for r in ERA_1994.items}
    assert by_id["14"].part is Part.PART_IV          # bug-fix core: Exhibits in Part IV
    assert by_id["14"].expectation is ItemExpectation.REQUIRED


def test_era_1994_absent_items():
    by_id = {r.item_id: r for r in ERA_1994.items}
    for item_id in ("1A", "7A", "9A"):
        assert by_id[item_id].expectation is ItemExpectation.ABSENT, item_id
        assert by_id[item_id].part is None, item_id


def test_era_1994_legal_structure_absences():
    absences = [ls.absences for ls in ERA_1994.legal_structures]
    assert absences == [["11", "12", "13"]]          # Item 10 deliberately excluded


# --------------------------------------------------------------------------- #
# era_2005 data (uses the real ERA_2005 constant, not dummy data)
# --------------------------------------------------------------------------- #
def test_era_2005_constructs_and_is_self_consistent():
    # ERA_2005 building at import time already ran every validator (19 unique
    # item_ids, every present item has a Part). Re-assert the shape.
    assert ERA_2005.era_id == "era_2005"
    assert ERA_2005.effective_from_fye == "2005-12-01"
    assert ERA_2005.effective_until_fye == "2021-08-09"
    assert ERA_2005.evidence_level is EvidenceLevel.SEC_PRIMARY
    assert len(ERA_2005.items) == 21          # 19 base + 9B + 16 (step-2 additions)
    assert len({r.item_id for r in ERA_2005.items}) == 21


def test_era_2005_1a_1b_7a_9a_now_required():
    # Key contrast with era_1994, where these four are ABSENT/part=None.
    by_id = {r.item_id: r for r in ERA_2005.items}
    for item_id in ("1A", "1B", "7A", "9A"):
        assert by_id[item_id].expectation is ItemExpectation.REQUIRED, item_id
        assert by_id[item_id].part is not None, item_id


def test_era_2005_item_14_is_part_iii_accountant_fees():
    # Post-shift structure: Item 14 = Principal Accountant Fees in Part III
    # (contrast era_1994, where Item 14 = Exhibits in Part IV).
    by_id = {r.item_id: r for r in ERA_2005.items}
    assert by_id["14"].part is Part.PART_III
    assert by_id["14"].topic == "Principal Accountant Fees and Services"


def test_era_2005_item_15_is_part_iv_exhibits():
    # Exhibits shifted to Item 15 in Part IV.
    by_id = {r.item_id: r for r in ERA_2005.items}
    assert by_id["15"].part is Part.PART_IV


def test_era_2005_has_21_items_with_9b_and_16():
    assert len(ERA_2005.items) == 21
    by_id = {r.item_id: r for r in ERA_2005.items}
    # 9B: Other Information — REQUIRED, Part II
    assert by_id["9B"].expectation is ItemExpectation.REQUIRED
    assert by_id["9B"].part is Part.PART_II
    # 16: Form 10-K Summary — CONDITIONAL (optional), no single Part
    assert by_id["16"].expectation is ItemExpectation.CONDITIONAL
    assert by_id["16"].part is None


# --------------------------------------------------------------------------- #
# era_2020 data (uses the real ERA_2020 constant, not dummy data)
# --------------------------------------------------------------------------- #
def test_era_2020_constructs_and_is_self_consistent():
    assert ERA_2020.era_id == "era_2020"
    assert ERA_2020.effective_from_fye == "2021-08-09"
    assert ERA_2020.effective_until_fye == "2023-12-15"
    assert ERA_2020.evidence_level is EvidenceLevel.REAL_FILING
    assert len(ERA_2020.items) == 22          # era_2005's 21 + 9C
    assert len({r.item_id for r in ERA_2020.items}) == 22


def test_era_2020_item_6_is_reserved():
    by_id = {r.item_id: r for r in ERA_2020.items}
    assert by_id["6"].expectation is ItemExpectation.RESERVED   # key era_2020 change
    assert by_id["6"].part is Part.PART_II


def test_era_2020_item_9c_conditional_with_part():
    by_id = {r.item_id: r for r in ERA_2020.items}
    assert by_id["9C"].expectation is ItemExpectation.CONDITIONAL
    assert by_id["9C"].part is Part.PART_II     # has a definite Part, only applicability is conditional


def test_era_2020_item_16_conditional_no_part():
    by_id = {r.item_id: r for r in ERA_2020.items}
    assert by_id["16"].expectation is ItemExpectation.CONDITIONAL
    assert by_id["16"].part is None             # summary spans the whole form, no single Part


def test_era_2020_item_4_is_mine_safety():
    by_id = {r.item_id: r for r in ERA_2020.items}
    assert by_id["4"].topic == "Mine Safety Disclosures"   # modern title, not the 1994 shareholder-vote


# --------------------------------------------------------------------------- #
# era_2023 data (uses the real ERA_2023 constant, not dummy data)
# --------------------------------------------------------------------------- #
def test_era_2023_constructs_and_is_self_consistent():
    assert ERA_2023.era_id == "era_2023"
    assert ERA_2023.effective_from_fye == "2023-12-15"
    assert ERA_2023.effective_until_fye is None            # newest era: open interval
    assert ERA_2023.evidence_level is EvidenceLevel.REAL_FILING
    assert len(ERA_2023.items) == 23                       # era_2020's 22 + 1C
    assert len({r.item_id for r in ERA_2023.items}) == 23


def test_era_2023_item_1c_introduced():
    # KEY era_2023 addition vs era_2020: Item 1C Cybersecurity in Part I.
    by_id = {r.item_id: r for r in ERA_2023.items}
    assert by_id["1C"].expectation is ItemExpectation.REQUIRED
    assert by_id["1C"].part is Part.PART_I
    assert by_id["1C"].topic == "Cybersecurity"


def test_era_2023_item_6_is_reserved():
    by_id = {r.item_id: r for r in ERA_2023.items}
    assert by_id["6"].expectation is ItemExpectation.RESERVED
    assert by_id["6"].part is Part.PART_II


def test_era_2023_conditional_items():
    by_id = {r.item_id: r for r in ERA_2023.items}
    # 9C: conditional with a definite Part (II)
    assert by_id["9C"].expectation is ItemExpectation.CONDITIONAL
    assert by_id["9C"].part is Part.PART_II
    # 16: conditional with no single Part
    assert by_id["16"].expectation is ItemExpectation.CONDITIONAL
    assert by_id["16"].part is None


def test_era_2023_item_4_is_mine_safety():
    by_id = {r.item_id: r for r in ERA_2023.items}
    assert by_id["4"].topic == "Mine Safety Disclosures"
