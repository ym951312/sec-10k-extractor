"""Declarative era-ruleset schema (Stage 0).

A per-item, declarative representation of "what each regulatory era legally
expects of each 10-K item". This replaces the current implicit approach where a
single era's rules are scattered across four parallel collections
(``expected_items`` / ``reserved_items`` / ``_PART_OF`` / ``checks.OPTIONAL_ITEMS``)
and recovered by set arithmetic. Here every item carries one explicit
expectation record.

Two orthogonal dimensions live side by side:

* **per-item expectation** (:class:`ItemRule`) — the four-state, item-by-item
  "should this item exist / be reserved / be absent / be conditional" axis.
* **cross-item legal structure** (reused :class:`~sec10k.contracts.LegalStructure`)
  — merge authorizations and incorporation-by-reference absences that span
  *multiple* items.

This milestone defines the schema + validators only; no real era data is filled
in yet (that is the next step). Nothing here selects a ruleset by
``fiscal_year_end`` — the picker is a later step and is not touched.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from ..contracts import LegalStructure


# --------------------------------------------------------------------------- #
# Enums (new — deliberately NOT reusing ItemStatus)
# --------------------------------------------------------------------------- #
class ItemExpectation(str, Enum):
    """A ruleset's *normative expectation* for one item in one era.

    This is the "ruleset expectation" axis — what the law/spec expects of an
    item for filings in this era. It is DELIBERATELY separate from
    :class:`sec10k.enums.ItemStatus`, which is the "runtime observation" axis
    (what a given filing's item was actually extracted as). The two are
    different dimensions and their members do not correspond; do not conflate
    them.
    """

    REQUIRED = "required"        # this era expects the item to be present
    RESERVED = "reserved"        # a legally-empty placeholder (correctly empty -> PASS)
    ABSENT = "absent"            # the item does not exist in this era (e.g. no 1A in 1994)
    CONDITIONAL = "conditional"  # present-or-absent both legal (e.g. a transition window)


class Part(str, Enum):
    """An item's Part membership — a typed form of loader.py's ``_PART_OF`` dict."""

    PART_I = "I"
    PART_II = "II"
    PART_III = "III"
    PART_IV = "IV"


class EvidenceLevel(str, Enum):
    """How well an era's rules are corroborated (the "success is only
    corroborated" epistemology — see DESIGN.md §5)."""

    REAL_FILING = "real_filing"  # a real EDGAR filing exists to run/verify this era
    SEC_PRIMARY = "sec_primary"  # authoritative SEC final-rule source, but no real fixture in repo
    PENDING = "pending"          # known to exist but precise source unverified + no fixture;
                                 # NOT used for enforced judgement


# --------------------------------------------------------------------------- #
# Per-item declaration
# --------------------------------------------------------------------------- #
class ItemRule(BaseModel):
    """One era's complete declaration for a single item.

    ``ItemRule`` (rather than e.g. ``ItemSpec``) mirrors the repo's convention of
    naming rule-bearing records after their role (cf. ``LegalStructure``): it is
    the per-item *rule* within an era's ruleset.
    """

    item_id: str                    # item number, e.g. "1", "1A", "7A", "14"
    expectation: ItemExpectation    # the four-state normative expectation
    part: Optional[Part] = None     # Part membership; None iff the item is ABSENT
    topic: str                      # human-readable topic label, e.g. "Risk Factors".
    # ^ topic is FOR HUMAN READING / REPORT DISPLAY ONLY. Judgement logic
    #   (anchoring, should_exist, etc.) must NEVER key on this field. The anchor
    #   is always item_id + order, never the topic string (CLAUDE.md rule 2).


# --------------------------------------------------------------------------- #
# Era-level ruleset
# --------------------------------------------------------------------------- #
class EraRuleset(BaseModel):
    """The complete legal ruleset for one regulatory era.

    ``effective_from_fye`` / ``effective_until_fye`` are ISO ``YYYY-MM-DD``
    fiscal-year-end thresholds bounding this era; the oldest era has no lower
    bound (``None``) and the newest has no upper bound (``None``, open interval).
    """

    era_id: str                          # era identifier, e.g. "era_1994", "era_2023"
    effective_from_fye: Optional[str] = None   # inclusive lower FYE bound (None = oldest)
    effective_until_fye: Optional[str] = None  # upper FYE bound = next era's threshold (None = newest)
    items: list[ItemRule]                # ordered per-item declarations (order = item ordering)
    legal_structures: list[LegalStructure] = Field(default_factory=list)
    evidence_level: EvidenceLevel        # corroboration level for this era
    pending_notes: list[str] = Field(default_factory=list)     # what is still "待補" in this era
    unenforced_rules: list[str] = Field(default_factory=list)  # exists-but-not-judged (e.g. stayed rules);
                                                               # purely recorded, affects no item expectation

    @model_validator(mode="after")
    def _check_self_consistent(self) -> "EraRuleset":
        # (1) an item may be declared at most once per era — a duplicate item_id
        #     would make the per-item expectation ambiguous.
        seen: set[str] = set()
        for rule in self.items:
            if rule.item_id in seen:
                raise ValueError(f"duplicate item_id in era {self.era_id!r}: {rule.item_id!r}")
            seen.add(rule.item_id)

        # (2) the FYE window must be non-degenerate when both bounds are set:
        #     the lower threshold must be strictly before the upper one, else the
        #     era covers no fiscal-year-end (an unusable / mis-entered range).
        lo, hi = self.effective_from_fye, self.effective_until_fye
        if lo is not None and hi is not None and lo >= hi:
            raise ValueError(
                f"era {self.era_id!r}: effective_from_fye {lo!r} must be before "
                f"effective_until_fye {hi!r}")

        # (3) part must agree with expectation, but only for the two "definitely
        #     present, definitely located" states:
        #       * REQUIRED / RESERVED -> the item occupies a concrete slot in the
        #         filing (RESERVED is an empty-but-present placeholder), so it MUST
        #         carry a Part; part=None is an error.
        #       * ABSENT / CONDITIONAL -> part is NOT enforced (None or a Part are
        #         both legal). ABSENT items may not exist at all (no Part); a
        #         CONDITIONAL item may be an optional/applicability-conditional item
        #         that either has a definite Part (e.g. 9C in Part II) or spans the
        #         whole form and belongs to no single Part (e.g. a Form 10-K Summary).
        for rule in self.items:
            if (rule.expectation in (ItemExpectation.REQUIRED, ItemExpectation.RESERVED)
                    and rule.part is None):
                raise ValueError(
                    f"item {rule.item_id!r}: {rule.expectation.value} items must "
                    f"have a Part, got part=None")
        return self


# --------------------------------------------------------------------------- #
# era data
# --------------------------------------------------------------------------- #
# era_1994 — the 1994-era 10-K item structure. Every REQUIRED/ABSENT/part value
# below was verified against the real MSFT FY1994 fixture (item headings + Part
# dividers + line-start grep for absent items); see docs/reports & the
# fiscal-year-end / ruleset-history research. Do not add, drop, or edit item
# expectation/part/topic values without re-verifying against a real filing.
ERA_1994 = EraRuleset(
    era_id="era_1994",
    effective_from_fye=None,             # oldest era: no lower bound
    effective_until_fye="2005-12-01",    # upper bound = 2005 Item 1A/1B introduction
    items=[
        ItemRule(item_id="1", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Business"),
        ItemRule(item_id="1A", expectation=ItemExpectation.ABSENT, part=None,
                 topic="Risk Factors (not yet introduced)"),
        ItemRule(item_id="1B", expectation=ItemExpectation.ABSENT, part=None,
                 topic="Unresolved Staff Comments (not yet introduced)"),
        ItemRule(item_id="2", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Properties"),
        ItemRule(item_id="3", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Legal Proceedings"),
        ItemRule(item_id="4", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Submission of Matters to a Vote of Security Holders"),
        ItemRule(item_id="5", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Market for Registrant's Common Stock and Related Stockholder Matters"),
        ItemRule(item_id="6", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Selected Financial Data"),
        ItemRule(item_id="7", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Management's Discussion and Analysis"),
        ItemRule(item_id="7A", expectation=ItemExpectation.ABSENT, part=None,
                 topic="Quantitative and Qualitative Disclosures About Market Risk (not yet introduced)"),
        ItemRule(item_id="8", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Financial Statements and Supplementary Data"),
        ItemRule(item_id="9", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Changes in and Disagreements with Accountants"),
        ItemRule(item_id="9A", expectation=ItemExpectation.ABSENT, part=None,
                 topic="Controls and Procedures (not yet introduced)"),
        ItemRule(item_id="10", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Directors and Executive Officers"),
        ItemRule(item_id="11", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Executive Compensation"),
        ItemRule(item_id="12", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Security Ownership"),
        ItemRule(item_id="13", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Certain Relationships and Related Transactions"),
        ItemRule(item_id="14", expectation=ItemExpectation.REQUIRED, part=Part.PART_IV,
                 topic="Exhibits, Financial Statement Schedules, and Reports on Form 8-K"),
    ],
    legal_structures=[
        # Item 10 is NOT in absences: in MSFT FY1994 part of Item 10 (Executive
        # Officers) is in-document, so it is not a pure incorporation-by-reference.
        LegalStructure(
            name="part_iii_incorporated_by_reference",
            merges=[],
            absences=["11", "12", "13"],
        ),
    ],
    evidence_level=EvidenceLevel.REAL_FILING,
    pending_notes=[
        "此 era 僅由 MSFT 1994 單一發行人單一檔（msft_10k_fy1994_ascii）佐證，尚未跨發行人抽樣；1994 其他公司的變異未驗證。",
        "era 上界暫定 2005-12-01，但 1994~2005 之間 7A（約1997）、9A（2002）等為陸續引入；本 era 將此區間粗略視為單一 era，中間變動點的精確 final rule 出處待補。",
    ],
)


# era_2005 — post-2005 structure: Item 1A/1B introduced (Release 33-8591, 2005),
# Item 14->15 shift already in effect (Item 14 = Principal Accountant Fees in
# Part III, Item 15 = Exhibits in Part IV). Item 6 still REQUIRED (only the 2020
# Release 33-10890 made it reserved). No real fixture in repo, so this era is
# corroborated only by SEC final-rule sources (evidence_level=SEC_PRIMARY).
# Do not add/drop/edit any item without re-verifying against a primary source.
ERA_2005 = EraRuleset(
    era_id="era_2005",
    effective_from_fye="2005-12-01",     # lower bound = 2005 Item 1A/1B introduction
    effective_until_fye="2021-08-09",    # upper bound = 2020 Item 6 -> reserved (Release 33-10890)
    items=[
        ItemRule(item_id="1", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Business"),
        ItemRule(item_id="1A", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Risk Factors"),
        ItemRule(item_id="1B", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Unresolved Staff Comments"),
        ItemRule(item_id="2", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Properties"),
        ItemRule(item_id="3", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Legal Proceedings"),
        ItemRule(item_id="4", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Submission of Matters to a Vote of Security Holders"),
        ItemRule(item_id="5", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Market for Registrant's Common Equity"),
        ItemRule(item_id="6", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Selected Financial Data"),
        ItemRule(item_id="7", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Management's Discussion and Analysis"),
        ItemRule(item_id="7A", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Quantitative and Qualitative Disclosures About Market Risk"),
        ItemRule(item_id="8", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Financial Statements and Supplementary Data"),
        ItemRule(item_id="9", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Changes in and Disagreements with Accountants"),
        ItemRule(item_id="9A", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Controls and Procedures"),
        ItemRule(item_id="9B", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Other Information"),
        ItemRule(item_id="10", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Directors and Executive Officers"),
        ItemRule(item_id="11", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Executive Compensation"),
        ItemRule(item_id="12", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Security Ownership"),
        ItemRule(item_id="13", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Certain Relationships and Related Transactions"),
        ItemRule(item_id="14", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Principal Accountant Fees and Services"),
        ItemRule(item_id="15", expectation=ItemExpectation.REQUIRED, part=Part.PART_IV,
                 topic="Exhibits and Financial Statement Schedules"),
        ItemRule(item_id="16", expectation=ItemExpectation.CONDITIONAL, part=None,
                 topic="Form 10-K Summary"),
    ],
    legal_structures=[
        # 2005 era: Part III items 10-13 content may be incorporated by reference
        # to the proxy statement (authorized absence, not a merge).
        LegalStructure(
            name="part_iii_incorporated_by_reference",
            merges=[],
            absences=["10", "11", "12", "13", "14"],
        ),
    ],
    evidence_level=EvidenceLevel.SEC_PRIMARY,
    pending_notes=[
        "era_2005 無真實檔佐證（evidence_level=SEC_PRIMARY）；此 era 涵蓋 FYE 2005-12-01 至 2021-08-09。多數基礎 item（1,2,3,4,5,7,8,9,10-13）為穩定性推導、無獨立 2005 出處，無真實檔可逐筆核對。",
        "有 SEC 出處的 item：1A/1B（Release 33-8591, 2005 引入）、7A（Release 33-7386, 1997, 遠早於本 era）、9A（Release 33-8124, 2002 SOX §302, 早於本 era）、Item 6 仍 required（2020 Release 33-10890 才改 reserved）、Item 14→15 位移已於 2003 發生（故 Item 14=Principal Accountant Fees/Part III、Item 15=Exhibits/Part IV）。",
        "Item 9B（Other Information）依 Release 33-8400（2004-08-23 生效，早於 era_2005 下界 2005-12-01）已列入，REQUIRED、Part II。",
        "注意：9A 的 trigger 是 filing-date 語意（2002-08-29 後申報），非 fiscal-year-end 語意；對 2005 無影響但為記錄。Item 14→15 位移的精確 final rule（約 2003 audit committee 規則）僅有 FY2003 他家真實檔間接佐證。",
        "Item 16（Form 10-K Summary）於 2016 引入，era_2005 涵蓋 FYE 2005~2021 橫跨此引入點：2016 前的檔不應有 16、2016 後可有（optional）。此 era 為粗略近似，未細分——細分需該區間真實檔方能驗證，目前無此區間真實檔，故維持單一粗略 era 並在此誠實註記。",
    ],
    unenforced_rules=[],
)


# era_2020 — post-2020 structure: Item 6 became [RESERVED] (Selected Financial
# Data removed, Release 33-10890, effective 2021-02-10 / mandatory 2021-08-09),
# and Item 1C (Cybersecurity) is NOT yet introduced (that is 2023-12-15+, the
# next era). Highly similar to era_2005; the only expectation change is Item 6
# REQUIRED -> RESERVED, plus the Item 9C row (Foreign Jurisdictions, conditional)
# that is visible in the MSFT FY2023 fixture. Corroborated by a real filing
# (MSFT FY2023, FYE 2023-06-30, which falls in this era's window), so
# evidence_level=REAL_FILING. Every value below was cross-checked against that
# fixture (see docs/reports); do not add/drop/edit an item without re-verifying.
ERA_2020 = EraRuleset(
    era_id="era_2020",
    effective_from_fye="2021-08-09",     # lower bound = 2020 Item 6 reserved mandatory date
    effective_until_fye="2023-12-15",    # upper bound = 2023 Item 1C introduction
    items=[
        ItemRule(item_id="1", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Business"),
        ItemRule(item_id="1A", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Risk Factors"),
        ItemRule(item_id="1B", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Unresolved Staff Comments"),
        ItemRule(item_id="2", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Properties"),
        ItemRule(item_id="3", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Legal Proceedings"),
        ItemRule(item_id="4", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Mine Safety Disclosures"),
        ItemRule(item_id="5", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Market for Registrant's Common Equity"),
        # KEY era_2020 difference vs era_2005: Item 6 became a reserved placeholder.
        ItemRule(item_id="6", expectation=ItemExpectation.RESERVED, part=Part.PART_II,
                 topic="Reserved (formerly Selected Financial Data)"),
        ItemRule(item_id="7", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Management's Discussion and Analysis"),
        ItemRule(item_id="7A", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Quantitative and Qualitative Disclosures About Market Risk"),
        ItemRule(item_id="8", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Financial Statements and Supplementary Data"),
        ItemRule(item_id="9", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Changes in and Disagreements with Accountants"),
        ItemRule(item_id="9A", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Controls and Procedures"),
        ItemRule(item_id="9B", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Other Information"),
        # 9C has a definite Part (II); only its applicability is conditional
        # (Commission-Identified Issuers only), hence CONDITIONAL with a real Part.
        ItemRule(item_id="9C", expectation=ItemExpectation.CONDITIONAL, part=Part.PART_II,
                 topic="Disclosure Regarding Foreign Jurisdictions that Prevent Inspections"),
        ItemRule(item_id="10", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Directors and Executive Officers"),
        ItemRule(item_id="11", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Executive Compensation"),
        ItemRule(item_id="12", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Security Ownership"),
        ItemRule(item_id="13", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Certain Relationships and Related Transactions"),
        ItemRule(item_id="14", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Principal Accountant Fees and Services"),
        ItemRule(item_id="15", expectation=ItemExpectation.REQUIRED, part=Part.PART_IV,
                 topic="Exhibits and Financial Statement Schedules"),
        # Form 10-K Summary spans the whole form -> no single Part; optional.
        ItemRule(item_id="16", expectation=ItemExpectation.CONDITIONAL, part=None,
                 topic="Form 10-K Summary"),
    ],
    legal_structures=[
        # Part III items 10-13 content may be incorporated by reference to the
        # proxy statement (confirmed in MSFT FY2023: items 11-14 IBR to Proxy).
        LegalStructure(
            name="part_iii_incorporated_by_reference",
            merges=[],
            absences=["10", "11", "12", "13", "14"],
        ),
    ],
    evidence_level=EvidenceLevel.REAL_FILING,
    pending_notes=[
        "era_2020 由 MSFT 2023 真實檔（msft_10k_fy2023, FYE 2023-06-30）佐證，逐筆核對確認。此 era 涵蓋 FYE 2021-08-09 至 2023-12-15（Item 6 已 reserved、Item 1C 尚未引入）。",
        "關鍵特徵由真實檔確認：Item 6=[RESERVED]（檔內標題 ITEM 6. [RESERVED]，其後無 Selected Financial Data 內容）、無 Item 1C（item 1c grep 命中 0 次，cybersecur 字根雖出現但無獨立 ITEM 1C 標題）。",
        "Item 9C（Foreign Jurisdictions）標 CONDITIONAL：僅 Commission-Identified Issuers（審計師在 PCAOB 無法檢查之外國轄區）實質適用；MSFT 為美國公司、Deloitte 審計，9C 標題在但內容不適用，符合 CONDITIONAL 期待。",
        "Item 16（Form 10-K Summary）標 CONDITIONAL（optional）；MSFT 2023 檔內 Item 16 為 None，符合 CONDITIONAL。",
        "單一發行人（MSFT）佐證，尚未跨發行人抽樣；此 era 其他公司的變異未驗證。",
    ],
    unenforced_rules=[],
)


# era_2023 — the current (newest, open-interval) era: Item 1C (Cybersecurity)
# introduced (effective 2023-12-15). Identical to era_2020 except for the added
# Item 1C. Corroborated by a real filing (APA FY2023, FYE 2023-12-31, which
# falls in this era's window) verified item-by-item; evidence_level=REAL_FILING.
# legal_structures is deliberately kept minimal this round (same single IBR
# structure as era_2020); every unresolved legal-structure complication (absences
# "allowed vs actual" semantics, General Instruction I omission, Item 1+2 merge)
# is recorded in pending_notes for the picker milestone, NOT encoded here yet.
ERA_2023 = EraRuleset(
    era_id="era_2023",
    effective_from_fye="2023-12-15",     # lower bound = 2023 Item 1C introduction
    effective_until_fye=None,            # newest era: open interval, no upper bound
    items=[
        ItemRule(item_id="1", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Business"),
        ItemRule(item_id="1A", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Risk Factors"),
        ItemRule(item_id="1B", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Unresolved Staff Comments"),
        # KEY era_2023 difference vs era_2020: Item 1C introduced (2023-12-15).
        ItemRule(item_id="1C", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Cybersecurity"),
        ItemRule(item_id="2", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Properties"),
        ItemRule(item_id="3", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Legal Proceedings"),
        ItemRule(item_id="4", expectation=ItemExpectation.REQUIRED, part=Part.PART_I,
                 topic="Mine Safety Disclosures"),
        ItemRule(item_id="5", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Market for Registrant's Common Equity"),
        ItemRule(item_id="6", expectation=ItemExpectation.RESERVED, part=Part.PART_II,
                 topic="Reserved (formerly Selected Financial Data)"),
        ItemRule(item_id="7", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Management's Discussion and Analysis"),
        ItemRule(item_id="7A", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Quantitative and Qualitative Disclosures About Market Risk"),
        ItemRule(item_id="8", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Financial Statements and Supplementary Data"),
        ItemRule(item_id="9", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Changes in and Disagreements with Accountants"),
        ItemRule(item_id="9A", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Controls and Procedures"),
        ItemRule(item_id="9B", expectation=ItemExpectation.REQUIRED, part=Part.PART_II,
                 topic="Other Information"),
        ItemRule(item_id="9C", expectation=ItemExpectation.CONDITIONAL, part=Part.PART_II,
                 topic="Disclosure Regarding Foreign Jurisdictions that Prevent Inspections"),
        ItemRule(item_id="10", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Directors and Executive Officers"),
        ItemRule(item_id="11", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Executive Compensation"),
        ItemRule(item_id="12", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Security Ownership"),
        ItemRule(item_id="13", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Certain Relationships and Related Transactions"),
        ItemRule(item_id="14", expectation=ItemExpectation.REQUIRED, part=Part.PART_III,
                 topic="Principal Accountant Fees and Services"),
        ItemRule(item_id="15", expectation=ItemExpectation.REQUIRED, part=Part.PART_IV,
                 topic="Exhibits and Financial Statement Schedules"),
        ItemRule(item_id="16", expectation=ItemExpectation.CONDITIONAL, part=None,
                 topic="Form 10-K Summary"),
    ],
    legal_structures=[
        # Kept minimal this round (same as era_2020): a single IBR structure. The
        # "allowed max set" fix (10-14), the General Instruction I omission
        # structure, and the Item 1+2 merge are ALL deferred to the picker
        # milestone — see the legal_structures pending_note below.
        LegalStructure(
            name="part_iii_incorporated_by_reference",
            merges=[],
            absences=["10", "11", "12", "13", "14"],
        ),
    ],
    evidence_level=EvidenceLevel.REAL_FILING,
    pending_notes=[
        "era_2023 由 APA 2023 真實檔（apa_10k_fy2023_merged12, FYE 2023-12-31）逐筆核對佐證。此 era 涵蓋 FYE >= 2023-12-15（Item 1C 已引入），為目前最新 era（無上界）。",
        "關鍵特徵由真實檔確認：Item 1C（Cybersecurity）存在（檔內標題 ITEM 1C. CYBERSECURITY，屬 Part I，夾在 1B 與 3 之間）；此與 MSFT 2023（FYE 2023-06-30, 無 1C）構成 1C 於 2023-12-15 引入的正反佐證（門檻後有、門檻前無）。",
        "Item 6 標題變體警示：APA 2023 的 Item 6 標題是 'SELECTED FINANCIAL DATA ... Omitted'，非 MSFT 2023 的 '[RESERVED]'。兩份真實檔對同一個已保留的 Item 6 用了不同字面呈現，實質都是保留位。故 Stage 2/Stage 3 偵測 Item 6 為 RESERVED 時，不可只認 '[Reserved]' 字串，須容忍 'Selected Financial Data + Omitted' 等變體（呼應錨點=編號+順序、非標題字串）。",
        "Item 4（Mine Safety）：APA 為石油天然氣公司，但其 Item 4 為 'Not applicable'（Mine Safety 針對煤/金屬礦，油氣不適用）。Item 4 仍 REQUIRED，此為真實檔觀察。",
        "Item 7 標題變體：APA 的 Item 7 標題是 'MANAGEMENT'S NARRATIVE ANALYSIS OF RESULTS OF OPERATIONS'，非常規 MD&A（因 APA 為全資子公司採 narrative 形式）。錨點仍為 Item 7，標題字串不可作判定。",
        "【待柱子三處理的 legal_structures 坑 - 重要】此 era（及 era_2020/era_2005）的 legal_structures 有以下未解決問題，柱子三處理 picker 與 merged 判定時須一併定清楚後，再統一修正四個 era：（1）absences 的『允許 vs 實際』語意未定——era 層 absences 應表達『此 era 允許 Part III 哪些 item 合法缺席的最大集合』，按此 Part III 應為 10-14（五個都可能透過 IBR 或 General Instruction I 合法缺席），而非某份檔實際缺哪些。（2）現有 era_2020/era_2005/era_2023 的 absences 目前是 [10,11,12,13]（缺 14），按『允許最大集合』語意應為 [10,11,12,13,14]——MSFT 2023（era_2020）核對時其 Item 14 就是 IBR，證明 14 在允許缺席集合內。此為既有不一致，待統一修正。（3）Part III 授權缺席有多法源：IBR-to-proxy（MSFT 式）與 General Instruction I(2)(c) omission（APA 全資子公司式），現有只有 part_iii_incorporated_by_reference 一個結構，名稱與涵蓋不足，需加第二個 LegalStructure 表達 General Instruction I 省略。（4）Item 1+2 merge：APA 2023 的 Item 1（Business）與 Item 2（Properties）合併為單一標題 'ITEMS 1 and 2. BUSINESS AND PROPERTIES'（Item 2 無獨立標題），此為油氣公司公司屬性（非 era 屬性），merge 該放 era 層或跨 era 的公司結構層待定。（5）核心：legal_structures 表達『era 層允許什麼』vs『某份檔實際什麼』的語意區分未確立，是上述所有問題的根源。",
        "單一發行人（APA）佐證，尚未跨發行人抽樣；此 era 其他公司的變異未驗證。APA 的 Part III（10-13）採 General Instruction I 省略、Item 14 有實際內容（E&Y fees）未省略，與 MSFT 式 IBR 不同。",
    ],
    unenforced_rules=[],
)
