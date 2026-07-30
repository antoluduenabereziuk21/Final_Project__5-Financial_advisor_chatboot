"""
Canonical section mapping between Form 10-K and Form 20-F items.

Built directly from the official item lists (SEC.gov filings, Form 20-F item
list) rather than guessed. Several mappings are legitimately many-to-one,
partial, or unmapped -- forcing a clean 1:1 correspondence where none exists
would be worse than leaving a gap and flagging it.

Each entry:
    canonical_section : short slug used in chunk/table metadata
    label              : human-readable name
    form_10k           : list of 10-K item ids this maps to, or [] if none
    form_20f           : list of 20-F item ids this maps to, or [] if none
    notes              : caveats -- read these before trusting a mapping blindly
"""

CANONICAL_SECTIONS = [
    {
        "canonical_section": "business_overview",
        "label": "Business overview",
        "form_10k": ["1"],
        "form_20f": ["4"],
        "notes": "20-F Item 4 also folds in Property/Plant/Equipment, which 10-K splits out separately (see properties).",
    },
    {
        "canonical_section": "properties",
        "label": "Properties / property, plant & equipment",
        "form_10k": ["2"],
        "form_20f": ["4"],
        "notes": "20-F has no standalone item -- property/plant/equipment is a subsection within Item 4, not separately numbered. Same form_20f target as business_overview; disambiguate by subsection heading in the actual text, not item number alone.",
    },
    {
        "canonical_section": "risk_factors",
        "label": "Risk factors",
        "form_10k": ["1A"],
        "form_20f": ["3.D"],
        "notes": "Direct match.",
    },
    {
        "canonical_section": "unresolved_staff_comments",
        "label": "Unresolved staff comments",
        "form_10k": ["1B"],
        "form_20f": ["4A"],
        "notes": "Direct match, identical title in both forms.",
    },
    {
        "canonical_section": "cybersecurity",
        "label": "Cybersecurity",
        "form_10k": ["1C"],
        "form_20f": ["16K"],
        "notes": "20-F bundles this inside the 16A-16K disclosures group rather than a standalone Part-level item.",
    },
    {
        "canonical_section": "legal_proceedings",
        "label": "Legal proceedings",
        "form_10k": ["3"],
        "form_20f": [],
        "notes": "No standalone 20-F item in the official list -- typically appears as a subsection of Item 8 (Financial Information) in practice. Verify against the actual VNET_2019 text rather than assume; do not force a mapping to Item 8 without checking.",
    },
    {
        "canonical_section": "mine_safety_disclosures",
        "label": "Mine safety disclosures",
        "form_10k": ["4"],
        "form_20f": ["16-bundle"],
        "notes": "Listed within the 16A-16K bundle; exact sub-letter not enumerated in the source list -- verify against real filing text if this section is ever hit.",
    },
    {
        "canonical_section": "market_for_registrant_equity",
        "label": "Market for registrant's equity",
        "form_10k": ["5"],
        "form_20f": ["9"],
        "notes": "20-F 'The Offer and Listing' is the closest equivalent for market/trading information.",
    },
    {
        "canonical_section": "reserved_selected_financial_data",
        "label": "[Reserved] (was Selected Financial Data)",
        "form_10k": ["6"],
        "form_20f": ["3.A"],
        "notes": "Both explicitly [Reserved] for the same reason -- Selected Financial Data requirement eliminated for FY ending on/after Aug 9, 2021.",
    },
    {
        "canonical_section": "mdna",
        "label": "Management's discussion and analysis",
        "form_10k": ["7"],
        "form_20f": ["5"],
        "notes": "Direct, well-established equivalence.",
    },
    {
        "canonical_section": "market_risk_disclosures",
        "label": "Quantitative and qualitative disclosures about market risk",
        "form_10k": ["7A"],
        "form_20f": ["11"],
        "notes": "Identical title in both forms.",
    },
    {
        "canonical_section": "financial_statements",
        "label": "Financial statements",
        "form_10k": ["8"],
        "form_20f": ["17", "18"],
        "notes": "20-F splits into two mutually exclusive alternative presentations (17 vs 18) -- both map to this one canonical section.",
    },
    {
        "canonical_section": "accountant_changes",
        "label": "Changes in / disagreements with accountants",
        "form_10k": ["9"],
        "form_20f": [],
        "notes": "Not a clean match to the 16-bundle's 'Principal Accountant Fees' -- that's a different disclosure (fees, not disagreements). Flag for manual review, don't assume equivalence.",
    },
    {
        "canonical_section": "controls_and_procedures",
        "label": "Controls and procedures",
        "form_10k": ["9A"],
        "form_20f": ["15"],
        "notes": "Identical title in both forms.",
    },
    {
        "canonical_section": "other_information",
        "label": "Other information",
        "form_10k": ["9B"],
        "form_20f": [],
        "notes": "No 20-F equivalent identified.",
    },
    {
        "canonical_section": "foreign_jurisdiction_inspection",
        "label": "Foreign jurisdictions that prevent inspections",
        "form_10k": ["9C"],
        "form_20f": ["16-bundle"],
        "notes": "Explicitly listed within the 20-F 16A-16K group.",
    },
    {
        "canonical_section": "directors_and_governance",
        "label": "Directors, executive officers and corporate governance",
        "form_10k": ["10"],
        "form_20f": ["6"],
        "notes": "20-F Item 6 is broader -- bundles directors, compensation, board practices, employees, and share ownership into one item that 10-K splits across Items 10-12. Many-to-one.",
    },
    {
        "canonical_section": "executive_compensation",
        "label": "Executive compensation",
        "form_10k": ["11"],
        "form_20f": ["6.B"],
        "notes": "Subsection of 20-F Item 6, not a standalone top-level item.",
    },
    {
        "canonical_section": "security_ownership",
        "label": "Security ownership of beneficial owners and management",
        "form_10k": ["12"],
        "form_20f": ["6.E", "7"],
        "notes": "Split across two 20-F items -- 6.E covers management's own share ownership, 7 covers major shareholders generally. No single clean target; disambiguate by content, not assume 6.E.",
    },
    {
        "canonical_section": "related_party_transactions",
        "label": "Certain relationships and related transactions",
        "form_10k": ["13"],
        "form_20f": ["7"],
        "notes": "Same 20-F item (7) as security_ownership above -- 20-F Item 7 covers both major shareholders AND related party transactions in one item; 10-K splits them (12 vs 13). Real many-to-one, not an error.",
    },
    {
        "canonical_section": "principal_accountant_fees",
        "label": "Principal accountant fees and services",
        "form_10k": ["14"],
        "form_20f": ["16-bundle"],
        "notes": "Explicitly listed ('Principal Accountant Fees') within the 16A-16K group.",
    },
    {
        "canonical_section": "exhibits",
        "label": "Exhibits",
        "form_10k": ["15"],
        "form_20f": ["19"],
        "notes": "Direct match in purpose; 10-K also bundles financial statement schedules here, 20-F does not.",
    },
    {
        "canonical_section": "form_summary",
        "label": "Form 10-K summary (optional)",
        "form_10k": ["16"],
        "form_20f": [],
        "notes": "10-K only, optional item. No 20-F equivalent.",
    },
    {
        "canonical_section": "signatures",
        "label": "Signatures",
        "form_10k": ["signatures"],
        "form_20f": ["signatures"],
        "notes": "Direct match.",
    },
    # 20-F-only items -- offering/listing-specific disclosures domestic 10-K
    # filers handle in different forms (e.g. S-1) rather than the annual report.
    {
        "canonical_section": "offer_statistics_timetable",
        "label": "Offer statistics and expected timetable",
        "form_10k": [],
        "form_20f": ["2"],
        "notes": "No 10-K equivalent -- offering-specific.",
    },
    {
        "canonical_section": "capitalization_indebtedness",
        "label": "Capitalization and indebtedness",
        "form_10k": [],
        "form_20f": ["3.B"],
        "notes": "No 10-K equivalent.",
    },
    {
        "canonical_section": "reasons_for_offer_proceeds",
        "label": "Reasons for the offer and use of proceeds",
        "form_10k": [],
        "form_20f": ["3.C"],
        "notes": "No 10-K equivalent.",
    },
    {
        "canonical_section": "additional_information",
        "label": "Additional information",
        "form_10k": [],
        "form_20f": ["10"],
        "notes": "Broad catch-all (memorandum/articles, taxation, dividends/paying agents). No single 10-K equivalent -- content is scattered across multiple 10-K disclosures elsewhere.",
    },
    {
        "canonical_section": "description_of_securities",
        "label": "Description of securities other than equity securities",
        "form_10k": [],
        "form_20f": ["12"],
        "notes": "No 10-K equivalent.",
    },
    {
        "canonical_section": "defaults_dividend_arrearages",
        "label": "Defaults, dividend arrearages and delinquencies",
        "form_10k": [],
        "form_20f": ["13"],
        "notes": "No 10-K equivalent.",
    },
    {
        "canonical_section": "material_modifications_rights",
        "label": "Material modifications to rights of security holders",
        "form_10k": [],
        "form_20f": ["14"],
        "notes": "No 10-K equivalent.",
    },
]


def _build_lookup():
    """
    Maps (form_type, item_number) -> list of candidate canonical_section slugs.
    A list, not a single value: some 20-F items (e.g. Item 7) legitimately
    correspond to more than one 10-K item/canonical_section. Collapsing that
    to one value silently drops information -- a real bug caught by the
    self-check below, not a hypothetical.
    """
    lookup = {}
    for entry in CANONICAL_SECTIONS:
        for item in entry["form_10k"]:
            lookup.setdefault(("10-K", item.upper()), []).append(entry["canonical_section"])
        for item in entry["form_20f"]:
            lookup.setdefault(("20-F", item.upper()), []).append(entry["canonical_section"])
    return lookup


_LOOKUP = _build_lookup()


def canonical_sections_for(form_type: str, item_number: str):
    """
    form_type: "10-K" or "20-F"
    item_number: e.g. "1A", "7", "3.D" -- case-insensitive, as detected from
                 the filing text (see metadata.py's item-number regex).
    Returns a list of candidate canonical_section slugs (usually length 1,
    sometimes 2+ for genuinely ambiguous items like 20-F Item 7). Empty list
    if not found -- callers must not guess when this is empty.
    """
    if not item_number:
        return []
    return list(_LOOKUP.get((form_type, item_number.strip().upper()), []))


def canonical_section_for(form_type: str, item_number: str, text: str = ""):
    """
    Convenience wrapper for the common case: returns a single canonical_section,
    disambiguating by keyword match against `text` when an item maps to more
    than one candidate. Returns None (not a guess) if nothing matches and the
    mapping is ambiguous -- caller should fall back to storing all candidates
    via canonical_sections_for() rather than force a wrong single answer.
    """
    candidates = canonical_sections_for(form_type, item_number)
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    # ambiguous -- disambiguate by content keywords, don't pick by list order
    text_lower = text.lower()
    keyword_map = {
        "security_ownership": ["beneficial owner", "share ownership", "shares beneficially owned"],
        "related_party_transactions": ["related part", "related-party", "affiliated transaction"],
    }
    for candidate in candidates:
        for kw in keyword_map.get(candidate, []):
            if kw in text_lower:
                return candidate
    return None  # genuinely ambiguous, no keyword match -- don't guess


if __name__ == "__main__":
    # quick self-check: every canonical_section is reachable from at least one form
    for entry in CANONICAL_SECTIONS:
        if not entry["form_10k"] and not entry["form_20f"]:
            raise ValueError(f"{entry['canonical_section']} has no source item at all")
    print(f"{len(CANONICAL_SECTIONS)} canonical sections, {len(_LOOKUP)} item mappings.")
    assert canonical_sections_for("10-K", "1A") == ["risk_factors"]
    assert canonical_sections_for("20-F", "3.D") == ["risk_factors"]
    amb = canonical_sections_for("20-F", "7")
    assert set(amb) == {"security_ownership", "related_party_transactions"}, amb
    assert canonical_section_for("20-F", "7", "the beneficial owner table below") == "security_ownership"
    assert canonical_section_for("20-F", "7", "our related party transactions") == "related_party_transactions"
    assert canonical_section_for("20-F", "7", "unrelated filler text") is None
    print("All self-checks passed.")
