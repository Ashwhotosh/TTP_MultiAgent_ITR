"""
itr_text_corpus.py — Full text corpus of the Income Tax Act sections relevant
to FinITR-AI V2 (New Regime focus).

Structured as a hierarchical tree for PageIndex retrieval.

V2 changes:
- Removed old-regime deduction nodes (80C subtree, 80D, 80E, 80G, 80TTA, 80TTB, 80GG, 10(13A))
- Added Section 115BAC (New Tax Regime), 115BBH (Crypto/VDA), 111A/112A (Capital Gains)
- Added Section 44ADA (Freelance Presumptive), 80CCH (Agniveer), 87A Marginal Relief
- Kept 80CCD(2) (Employer NPS) — allowed in new regime
"""

ITR_CORPUS: dict[str, dict] = {
    # ────────────────────────── ROOT ──────────────────────────
    "root": {
        "title": "Income Tax Act 1961 — FY 25-26 New Regime Reference",
        "summary": (
            "Root of the ITR knowledge tree covering the New Tax Regime (Section 115BAC), "
            "allowed deductions, income classification, capital gains, crypto taxation, "
            "and marginal relief for individual taxpayers in India."
        ),
        "children": [
            "section_115BAC",
            "allowed_deductions",
            "income_classification",
            "section_87A",
        ],
    },

    # ─────────────────── SECTION 115BAC ────────────────────────
    "section_115BAC": {
        "title": "Section 115BAC: New Tax Regime",
        "full_text": (
            "Notwithstanding anything contained in this Act but subject to the "
            "provisions of this Chapter, the income-tax payable in respect of the "
            "total income of a person, being an individual or a Hindu undivided "
            "family or an association of persons (other than a co-operative society), "
            "or a body of individuals, whether incorporated or not, for any previous "
            "year relevant to the assessment year beginning on or after the 1st day "
            "of April, 2024, shall be computed at the rates provided under this section. "
            "The tax slabs for FY 2025-26 are: 0-4L: Nil, 4L-8L: 5%, 8L-12L: 10%, "
            "12L-16L: 15%, 16L-20L: 20%, 20L-24L: 25%, above 24L: 30%. "
            "A standard deduction of Rs 75,000 is allowed from salary income. "
            "Most Chapter VI-A deductions under the old regime are NOT available. "
            "Only employer NPS (80CCD(2)), Agniveer (80CCH), and family pension "
            "deduction are allowed."
        ),
        "summary": (
            "New Tax Regime is default from FY 2023-24. Lower slab rates but almost "
            "all deductions abolished. Standard deduction Rs 75,000. Rebate under "
            "87A up to Rs 60,000 if taxable income does not exceed Rs 12,00,000."
        ),
        "children": [],
    },

    # ─────────────── ALLOWED DEDUCTIONS (NEW REGIME) ──────────
    "allowed_deductions": {
        "title": "Allowed Deductions Under New Tax Regime",
        "summary": (
            "Only three deductions are available under the New Tax Regime: "
            "Employer NPS contribution (80CCD(2)), Agniveer Corpus Fund (80CCH), "
            "and Family Pension Standard Deduction (Section 57(iia))."
        ),
        "children": ["section_80CCD_2", "section_80CCH", "section_57iia"],
    },

    "section_80CCD_2": {
        "title": "Section 80CCD(2): Employer NPS Contribution",
        "full_text": (
            "Where, in the case of an assessee referred to in sub-section (1), the "
            "Central Government or any other employer makes any contribution to his "
            "account referred to in that sub-section, the assessee shall be allowed "
            "a deduction in the computation of his total income, of the whole of the "
            "amount contributed by the Central Government or any other employer as "
            "does not exceed fourteen per cent of his salary in the previous year "
            "(for central government employees) or ten per cent (for others). "
            "This deduction is available in BOTH old and new tax regimes."
        ),
        "summary": (
            "Employer's contribution to employee's NPS account: deduction up to "
            "10% of Basic+DA for private sector (14% for central government). "
            "Available in BOTH old and new tax regimes. This is the primary "
            "micro-optimization available under the new regime — negotiate with "
            "employer to restructure CTC to include NPS contribution."
        ),
        "children": [],
    },

    "section_80CCH": {
        "title": "Section 80CCH: Agniveer Corpus Fund",
        "full_text": (
            "Any sum paid or deposited by an individual enrolled under the "
            "Agnipath Scheme and notified by the Central Government, in the "
            "Agniveer Corpus Fund, shall be allowed as a deduction in computing "
            "the total income of such individual. Additionally, the contribution "
            "made by the Central Government to the individual's Agniveer Corpus "
            "Fund account shall also be allowed as a deduction."
        ),
        "summary": (
            "Deduction for Agniveers enrolled under the Agnipath Scheme. Both "
            "the individual's contribution and the Central Government's matching "
            "contribution are fully deductible. Available under new regime."
        ),
        "children": [],
    },

    "section_57iia": {
        "title": "Section 57(iia): Family Pension Standard Deduction",
        "full_text": (
            "In the case of income in the nature of family pension, a deduction "
            "of a sum equal to thirty-three and one-third per cent of such income "
            "or fifteen thousand rupees, whichever is less. Note: For FY 2025-26 "
            "under new regime, the limit has been enhanced to Rs 25,000."
        ),
        "summary": (
            "Family pension recipients can deduct the lower of Rs 25,000 or "
            "one-third of the pension amount. Available in new regime."
        ),
        "children": [],
    },

    # ───────────── INCOME CLASSIFICATION ───────────────────────
    "income_classification": {
        "title": "Income Classification & Special Tax Rates",
        "summary": (
            "Different income types are taxed at different rates: salary at slab rates, "
            "crypto/VDA at flat 30%, equity capital gains at 20%/12.5%, and "
            "freelance income under presumptive taxation (44ADA)."
        ),
        "children": [
            "section_115BBH",
            "section_111A",
            "section_112A",
            "section_44ADA",
        ],
    },

    "section_115BBH": {
        "title": "Section 115BBH: Income from Virtual Digital Assets (Crypto/NFT)",
        "full_text": (
            "Where the total income of an assessee includes any income from the "
            "transfer of any virtual digital asset, the income-tax payable shall "
            "be the aggregate of the amount of income-tax calculated on the income "
            "from transfer of such virtual digital asset at the rate of thirty per "
            "cent, and the amount of income-tax with which the assessee would have "
            "been chargeable had the total income of the assessee been reduced by "
            "the income from transfer of such virtual digital asset. "
            "No deduction in respect of any expenditure (other than cost of "
            "acquisition) or allowance or set-off of any loss shall be allowed. "
            "Section 194S provides for TDS at 1% on transfer of VDA above Rs 50,000 "
            "(Rs 10,000 for specified persons)."
        ),
        "summary": (
            "Crypto, NFTs, and all Virtual Digital Assets taxed at flat 30% on "
            "profits. NO basic exemption applies. NO loss set-off allowed — "
            "crypto losses cannot reduce other income. 1% TDS on all transfers "
            "above Rs 50,000. Cost of acquisition is the only deductible expense."
        ),
        "children": [],
    },

    "section_111A": {
        "title": "Section 111A: Short-Term Capital Gains on Equity",
        "full_text": (
            "Where the total income of an assessee includes any income chargeable "
            "under the head 'Capital gains', arising from the transfer of a short-term "
            "capital asset, being an equity share in a company or a unit of an equity "
            "oriented fund or a unit of a business trust, where such transaction is "
            "chargeable to securities transaction tax, such capital gains shall be "
            "taxed at the rate of twenty per cent."
        ),
        "summary": (
            "Short-Term Capital Gains (STCG) on listed equity shares and equity "
            "mutual funds (held less than 12 months) are taxed at a flat rate "
            "of 20% (changed from 15% effective from Budget 2024)."
        ),
        "children": [],
    },

    "section_112A": {
        "title": "Section 112A: Long-Term Capital Gains on Equity",
        "full_text": (
            "Where the total income of an assessee includes any income chargeable "
            "under the head 'Capital gains', arising from the transfer of a long-term "
            "capital asset, being an equity share in a company or a unit of an equity "
            "oriented fund or a unit of a business trust, where such transaction is "
            "chargeable to securities transaction tax, such capital gains exceeding "
            "one lakh twenty-five thousand rupees shall be taxed at the rate of "
            "twelve and one-half per cent."
        ),
        "summary": (
            "Long-Term Capital Gains (LTCG) on listed equity shares and equity "
            "mutual funds (held 12 months or more) are taxed at 12.5% on gains "
            "exceeding Rs 1,25,000 per year. No indexation benefit."
        ),
        "children": [],
    },

    "section_44ADA": {
        "title": "Section 44ADA: Presumptive Taxation for Professionals",
        "full_text": (
            "Notwithstanding anything to the contrary contained in sections 28 to 43C, "
            "in the case of an assessee, being a resident in India, who is engaged "
            "in a profession referred to in sub-section (1) of section 44AA and whose "
            "total gross receipts do not exceed seventy-five lakh rupees in a previous "
            "year, a sum equal to fifty per cent of the total gross receipts of the "
            "assessee in the previous year on account of such profession shall be "
            "deemed to be the profits and gains of such profession chargeable to tax "
            "under the head 'Profits and gains of business or profession'. "
            "No audit is required if the assessee opts for presumptive taxation."
        ),
        "summary": (
            "Freelancers and professionals (doctors, lawyers, engineers, architects, "
            "accountants, etc.) with gross receipts up to Rs 75 lakh can declare "
            "50% of receipts as deemed profit. No need for audit. Simplifies "
            "compliance for gig workers receiving income from Upwork, Fiverr, etc."
        ),
        "children": [],
    },

    # ──────────────── 87A REBATE & MARGINAL RELIEF ─────────────
    "section_87A": {
        "title": "Section 87A: Rebate and Marginal Relief",
        "full_text": (
            "An assessee, being an individual resident in India, whose total income "
            "does not exceed twelve lakh rupees, shall be entitled to a deduction, "
            "from the amount of income-tax (as computed before allowing the "
            "deductions under this Chapter) on his total income with which he is "
            "chargeable for any assessment year, of an amount equal to the amount "
            "of such income-tax or an amount of sixty thousand rupees, whichever is "
            "less. MARGINAL RELIEF: Where the total income exceeds Rs 12,00,000, "
            "and the tax payable (before rebate) exceeds the amount by which the "
            "total income exceeds Rs 12,00,000, the tax payable shall be reduced "
            "to the amount by which the total income exceeds Rs 12,00,000. "
            "This prevents the 'tax cliff' where earning Rs 1 more than Rs 12 lakh "
            "would result in a disproportionately high tax liability."
        ),
        "summary": (
            "If taxable income <= Rs 12,00,000: full rebate, zero tax. "
            "If taxable income between Rs 12,00,001 and ~Rs 12,75,000: Marginal Relief "
            "kicks in — tax cannot exceed the extra income earned above Rs 12 lakh. "
            "Example: Taxable income Rs 12,05,000 means tax is capped at Rs 5,000 "
            "(not Rs 60,500 which normal slabs would produce)."
        ),
        "children": [],
    },
}
