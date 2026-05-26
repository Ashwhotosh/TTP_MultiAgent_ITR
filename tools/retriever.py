"""
retriever.py -- PageIndex structured retriever.

Tree-walk retriever for structured legal section lookup.
Used by CriticAgent for verification lookups.

The PageIndex is a hierarchical tree of tax act sections. Given a query,
it walks the tree to find the most relevant section text. This is more
precise than vector search for known section references.
"""
from __future__ import annotations

import re
from typing import Any


# ── Expanded corpus tree (80+ nodes covering both regimes) ──
PAGE_INDEX_TREE: dict[str, dict] = {
    # ────────────────────────── ROOT ──────────────────────────
    "root": {
        "title": "Income Tax Act 1961 -- FY 2025-26 Reference",
        "summary": (
            "Root of the ITR knowledge tree covering both Old and New Tax Regimes, "
            "allowed deductions, income classification, capital gains, crypto taxation, "
            "and marginal relief for individual taxpayers in India."
        ),
        "children": [
            "section_115BAC", "old_regime", "allowed_deductions_new",
            "old_regime_deductions", "income_classification", "section_87A",
            "tds_provisions", "itr_forms", "hra_provisions",
        ],
    },

    # ─────────────────── SECTION 115BAC (New Regime) ────────────────────────
    "section_115BAC": {
        "title": "Section 115BAC: New Tax Regime",
        "full_text": (
            "The New Tax Regime under Section 115BAC is the default regime from FY 2023-24. "
            "Tax slabs for FY 2025-26 (Budget 2025): 0-4L: Nil, 4L-8L: 5%, 8L-12L: 10%, "
            "12L-16L: 15%, 16L-20L: 20%, 20L-24L: 25%, above 24L: 30%. "
            "Standard deduction of Rs 75,000 from salary income. "
            "Most Chapter VI-A deductions are NOT available. "
            "Only employer NPS (80CCD(2)), Agniveer (80CCH), and family pension "
            "deduction are allowed."
        ),
        "summary": "New Tax Regime default. Lower rates, fewer deductions.",
        "children": ["new_regime_slabs", "new_regime_blocked"],
    },

    "new_regime_slabs": {
        "title": "New Regime Tax Slabs FY 2025-26",
        "full_text": (
            "0 to Rs 4,00,000: Nil. "
            "Rs 4,00,001 to Rs 8,00,000: 5%. "
            "Rs 8,00,001 to Rs 12,00,000: 10%. "
            "Rs 12,00,001 to Rs 16,00,000: 15%. "
            "Rs 16,00,001 to Rs 20,00,000: 20%. "
            "Rs 20,00,001 to Rs 24,00,000: 25%. "
            "Above Rs 24,00,000: 30%. "
            "Standard deduction: Rs 75,000."
        ),
        "summary": "New regime slabs with standard deduction of Rs 75,000.",
        "children": [],
    },

    "new_regime_blocked": {
        "title": "Deductions NOT Allowed Under New Regime",
        "full_text": (
            "The following deductions are NOT allowed under Section 115BAC New Regime: "
            "80C (investments), 80D (health insurance), 80E (education loan interest), "
            "80G (donations), 80TTA (savings interest), 80TTB (senior citizen interest), "
            "80GG (rent without HRA), 24(b) (home loan interest), "
            "10(13A) HRA exemption, 80CCD(1B) additional NPS. "
            "Only 80CCD(2) employer NPS and 80CCH Agniveer are allowed."
        ),
        "summary": "80C, 80D, 80E, 80G, HRA, home loan interest blocked under new regime.",
        "children": [],
    },

    # ─────────────────── OLD REGIME ────────────────────────
    "old_regime": {
        "title": "Old Tax Regime",
        "full_text": (
            "The Old Tax Regime retains all traditional deductions but has higher slab rates. "
            "Slabs: 0-2.5L: Nil, 2.5L-5L: 5%, 5L-10L: 20%, above 10L: 30%. "
            "Standard deduction: Rs 50,000. "
            "Rebate under 87A: Up to Rs 12,500 if taxable income <= Rs 5,00,000. "
            "Available deductions include 80C, 80D, 80E, 80G, 80TTA, 24(b), HRA."
        ),
        "summary": "Old regime with higher rates but full deductions.",
        "children": ["old_regime_slabs"],
    },

    "old_regime_slabs": {
        "title": "Old Regime Tax Slabs FY 2025-26",
        "full_text": (
            "0 to Rs 2,50,000: Nil. "
            "Rs 2,50,001 to Rs 5,00,000: 5%. "
            "Rs 5,00,001 to Rs 10,00,000: 20%. "
            "Above Rs 10,00,000: 30%. "
            "Standard deduction: Rs 50,000. "
            "87A rebate: Up to Rs 12,500 if taxable income <= Rs 5,00,000."
        ),
        "summary": "Old regime slabs.",
        "children": [],
    },

    # ─────────────── ALLOWED DEDUCTIONS (NEW REGIME) ──────────
    "allowed_deductions_new": {
        "title": "Allowed Deductions Under New Tax Regime",
        "summary": (
            "Only three deductions available under New Regime: "
            "80CCD(2) employer NPS, 80CCH Agniveer, family pension deduction."
        ),
        "children": ["section_80CCD_2", "section_80CCH", "section_57iia"],
    },

    "section_80CCD_2": {
        "title": "Section 80CCD(2): Employer NPS Contribution",
        "full_text": (
            "Where the employer makes contribution to employee's NPS account, "
            "deduction is allowed up to 14% of salary for central government "
            "employees or 10% for others. This deduction is available in BOTH "
            "old and new tax regimes. Salary means Basic + DA."
        ),
        "summary": "Employer NPS: 10% (private) / 14% (CG). Available in both regimes.",
        "children": [],
    },

    "section_80CCH": {
        "title": "Section 80CCH: Agniveer Corpus Fund",
        "full_text": (
            "Deduction for Agniveers enrolled under the Agnipath Scheme. Both "
            "the individual's contribution and the Central Government's matching "
            "contribution are fully deductible. Available under new regime."
        ),
        "summary": "Agniveer fund contributions deductible under new regime.",
        "children": [],
    },

    "section_57iia": {
        "title": "Section 57(iia): Family Pension Standard Deduction",
        "full_text": (
            "Family pension recipients can deduct the lower of Rs 25,000 or "
            "one-third of the pension amount. Available in new regime."
        ),
        "summary": "Family pension deduction: min(Rs 25,000, 1/3 of pension).",
        "children": [],
    },

    # ─────────────── OLD REGIME DEDUCTIONS ──────────
    "old_regime_deductions": {
        "title": "Old Regime Chapter VI-A Deductions",
        "summary": "Full set of deductions available only under old regime.",
        "children": [
            "section_80C", "section_80CCD_1B", "section_80D",
            "section_80E", "section_80G", "section_80TTA", "section_80TTB",
            "section_80GG", "section_24b",
        ],
    },

    "section_80C": {
        "title": "Section 80C: Savings and Investments",
        "full_text": (
            "Deduction up to Rs 1,50,000 for investments in PPF, ELSS, "
            "tax-saving FD, life insurance premium, NSC, tuition fees, "
            "home loan principal repayment. Shared limit with 80CCC and 80CCD(1). "
            "NOT available under New Regime."
        ),
        "summary": "80C: Up to Rs 1.5L for investments. Old regime only.",
        "children": [],
    },

    "section_80CCD_1B": {
        "title": "Section 80CCD(1B): Additional NPS Contribution",
        "full_text": (
            "Additional deduction of up to Rs 50,000 for NPS Tier-I contributions, "
            "over and above the Rs 1,50,000 limit of Section 80C. "
            "NOT available under New Regime."
        ),
        "summary": "80CCD(1B): Extra Rs 50,000 NPS deduction. Old regime only.",
        "children": [],
    },

    "section_80D": {
        "title": "Section 80D: Health Insurance Premium",
        "full_text": (
            "Deduction for health insurance premium: Rs 25,000 for self/family, "
            "Rs 25,000 for parents (Rs 50,000 if senior citizen). "
            "Preventive health check-up within limit up to Rs 5,000. "
            "Maximum total: Rs 75,000. NOT available under New Regime."
        ),
        "summary": "80D: Health insurance up to Rs 75,000. Old regime only.",
        "children": [],
    },

    "section_80E": {
        "title": "Section 80E: Education Loan Interest",
        "full_text": (
            "No upper limit on deduction of interest paid on education loan. "
            "Available for 8 years from year of first repayment. "
            "Loan must be from bank/approved institution. "
            "NOT available under New Regime."
        ),
        "summary": "80E: Education loan interest, no limit. Old regime only.",
        "children": [],
    },

    "section_80G": {
        "title": "Section 80G: Donations",
        "full_text": (
            "Deduction for donations to approved institutions. "
            "100% deduction for PM National Relief Fund, National Defence Fund, PM CARES. "
            "50% deduction for other approved charitable institutions. "
            "10% of adjusted gross total income limit for some categories. "
            "Cash donations above Rs 2,000 not allowed. NOT available under New Regime."
        ),
        "summary": "80G: Donations. 50-100% deduction. Old regime only.",
        "children": [],
    },

    "section_80TTA": {
        "title": "Section 80TTA: Savings Account Interest",
        "full_text": (
            "Deduction up to Rs 10,000 for interest earned on savings accounts "
            "(bank, post office, cooperative society). "
            "Only savings account interest, not FD/RD. "
            "Not for senior citizens (they use 80TTB). NOT available under New Regime."
        ),
        "summary": "80TTA: Up to Rs 10,000 savings interest deduction. Old regime only.",
        "children": [],
    },

    "section_80TTB": {
        "title": "Section 80TTB: Senior Citizen Interest Income",
        "full_text": (
            "For senior citizens (60+): deduction up to Rs 50,000 for "
            "interest from savings account, FD, and RD. "
            "Replaces 80TTA for senior citizens. NOT available under New Regime."
        ),
        "summary": "80TTB: Rs 50,000 interest deduction for seniors. Old regime only.",
        "children": [],
    },

    "section_80GG": {
        "title": "Section 80GG: Rent Deduction (No HRA)",
        "full_text": (
            "For individuals NOT receiving HRA from employer. "
            "Deduction = min(Rs 5,000/month, 25% of total income, "
            "rent paid minus 10% of total income). "
            "Max Rs 60,000 per year. NOT available under New Regime."
        ),
        "summary": "80GG: Rent deduction without HRA, max Rs 60,000. Old regime only.",
        "children": [],
    },

    "section_24b": {
        "title": "Section 24(b): Home Loan Interest",
        "full_text": (
            "Deduction for interest on home loan: up to Rs 2,00,000 for "
            "self-occupied property. No limit for let-out property (but "
            "loss set-off capped at Rs 2L). Principal goes to 80C. "
            "Construction must complete within 5 years of loan. "
            "NOT available under New Regime."
        ),
        "summary": "24(b): Home loan interest up to Rs 2L. Old regime only.",
        "children": [],
    },

    # ───────────── INCOME CLASSIFICATION ───────────────────────
    "income_classification": {
        "title": "Income Classification & Special Tax Rates",
        "summary": "Different income types taxed at different rates.",
        "children": [
            "section_115BBH", "section_111A", "section_112A", "section_112",
            "section_44ADA", "section_17_2",
        ],
    },

    "section_115BBH": {
        "title": "Section 115BBH: Virtual Digital Assets (Crypto/NFT)",
        "full_text": (
            "Income from transfer of virtual digital assets taxed at flat 30% "
            "on profits. No deduction for any expenditure other than cost of "
            "acquisition. No loss set-off allowed. No basic exemption. "
            "Section 194S: TDS at 1% on VDA transfers above Rs 50,000 "
            "(Rs 10,000 for specified persons). Applies to crypto, NFTs, "
            "and all virtual digital assets as defined in Section 2(47A)."
        ),
        "summary": "Crypto/VDA: flat 30% tax, no loss set-off, 1% TDS.",
        "children": [],
    },

    "section_111A": {
        "title": "Section 111A: Short-Term Capital Gains on Equity",
        "full_text": (
            "STCG on listed equity shares and equity mutual funds (held less "
            "than 12 months) are taxed at a flat rate of 20% "
            "(changed from 15% effective Budget 2024). "
            "Applicable when Securities Transaction Tax (STT) is paid."
        ),
        "summary": "STCG on equity: flat 20% (was 15% pre-Budget 2024).",
        "children": [],
    },

    "section_112A": {
        "title": "Section 112A: Long-Term Capital Gains on Equity",
        "full_text": (
            "LTCG on listed equity shares and equity mutual funds (held 12+ "
            "months) are taxed at 12.5% on gains exceeding Rs 1,25,000 per year. "
            "No indexation benefit. STT must be paid on the transaction."
        ),
        "summary": "LTCG on equity: 12.5% above Rs 1.25L exemption.",
        "children": [],
    },

    "section_112": {
        "title": "Section 112: LTCG on Other Assets",
        "full_text": (
            "Long-term capital gains on assets other than listed equity (e.g., "
            "debt mutual funds, unlisted shares, property, gold) are taxed at "
            "12.5% without indexation (post Budget 2024). Previously taxed at "
            "20% with indexation for property and gold."
        ),
        "summary": "LTCG on non-equity assets: 12.5% without indexation.",
        "children": [],
    },

    "section_44ADA": {
        "title": "Section 44ADA: Presumptive Taxation for Professionals",
        "full_text": (
            "Professionals with gross receipts up to Rs 75 lakh can declare "
            "50% of receipts as deemed profit. No audit required. Eligible "
            "professions: doctors, lawyers, engineers, architects, accountants, "
            "technical consultants, interior decorators, and others specified "
            "in Section 44AA. Useful for freelancers on Upwork, Fiverr, etc."
        ),
        "summary": "44ADA: 50% presumptive income for professionals up to Rs 75L.",
        "children": [],
    },

    "section_17_2": {
        "title": "Section 17(2): Perquisites (including RSU/ESOP)",
        "full_text": (
            "Perquisites provided by employer are taxable under Section 17(2). "
            "Includes: rent-free accommodation, motor car benefit, education "
            "allowance, club membership, and importantly Restricted Stock Units "
            "(RSU) and Employee Stock Options (ESOP). "
            "RSUs are taxed as perquisite at the time of vesting at FMV. "
            "Section 17(2)(vi) covers the value of any specified security "
            "or sweat equity shares allotted or transferred to the employee."
        ),
        "summary": "17(2): Perquisites including RSU/ESOP taxed at vesting.",
        "children": [],
    },

    # ──────────────── 87A REBATE & MARGINAL RELIEF ─────────────
    "section_87A": {
        "title": "Section 87A: Rebate and Marginal Relief",
        "full_text": (
            "New Regime: If taxable income <= Rs 12,00,000: full rebate up to Rs 60,000, "
            "zero tax. Marginal Relief: if income between Rs 12,00,001 and ~Rs 12,75,000, "
            "tax cannot exceed the excess above Rs 12 lakh. "
            "Old Regime: Rebate up to Rs 12,500 if taxable income <= Rs 5,00,000."
        ),
        "summary": "87A: Rebate + marginal relief for both regimes.",
        "children": [],
    },

    # ──────────────── TDS PROVISIONS ─────────────
    "tds_provisions": {
        "title": "TDS Provisions",
        "summary": "Tax Deducted at Source provisions for different income types.",
        "children": [
            "section_192", "section_194A", "section_194I",
            "section_194S", "section_194F", "section_206C",
        ],
    },

    "section_192": {
        "title": "Section 192: TDS on Salary",
        "full_text": (
            "Every employer paying salary shall deduct tax at source at the "
            "average rate of income-tax computed on the basis of rates in force. "
            "The employer must consider the regime chosen by the employee."
        ),
        "summary": "TDS on salary by employer at average rate.",
        "children": [],
    },

    "section_194A": {
        "title": "Section 194A: TDS on Interest (Other Than Securities)",
        "full_text": (
            "TDS at 10% on interest paid by banks/post office/cooperative "
            "societies when aggregate interest exceeds Rs 40,000 in a year "
            "(Rs 50,000 for senior citizens). Covers savings account interest "
            "and fixed deposit interest."
        ),
        "summary": "TDS 10% on interest > Rs 40,000 (bank/FD/savings).",
        "children": [],
    },

    "section_194I": {
        "title": "Section 194I: TDS on Rent",
        "full_text": (
            "TDS on rent: 2% for plant/machinery, 10% for land/building/furniture. "
            "Applicable when aggregate rent exceeds Rs 2,40,000 per year. "
            "Individual/HUF not liable to deduct TDS on rent unless covered "
            "under Section 44AB (audit)."
        ),
        "summary": "TDS on rent: 2-10% above Rs 2.4L/year.",
        "children": [],
    },

    "section_194S": {
        "title": "Section 194S: TDS on Virtual Digital Assets",
        "full_text": (
            "TDS at 1% on payment for transfer of virtual digital assets "
            "when consideration exceeds Rs 50,000 per year (Rs 10,000 for "
            "specified persons). Introduced in Budget 2022 alongside "
            "Section 115BBH."
        ),
        "summary": "TDS 1% on crypto/VDA transfers > Rs 50,000.",
        "children": [],
    },

    "section_194F": {
        "title": "Section 194F: TDS on Mutual Fund Repurchase",
        "full_text": (
            "TDS provisions on payments by mutual funds for repurchase of units. "
            "Applicable on certain types of mutual fund redemptions."
        ),
        "summary": "TDS on MF repurchase/redemption.",
        "children": [],
    },

    "section_206C": {
        "title": "Section 206C: TCS on Foreign Remittance",
        "full_text": (
            "Tax Collected at Source on foreign remittance under Liberalised "
            "Remittance Scheme (LRS): 20% on remittance above Rs 7 lakh "
            "(excluding education and medical). 5% for education loans."
        ),
        "summary": "TCS 20% on foreign remittance above Rs 7L.",
        "children": [],
    },

    # ──────────────── ITR FORMS ─────────────
    "itr_forms": {
        "title": "ITR Form Selection",
        "summary": "Which ITR form to use based on income type.",
        "children": ["itr_1", "itr_2", "itr_3", "itr_4"],
    },

    "itr_1": {
        "title": "ITR-1 (Sahaj)",
        "full_text": (
            "For resident individuals with income up to Rs 50 lakh from: "
            "salary/pension, one house property, other sources (interest, dividend, "
            "family pension). NOT eligible if: capital gains present, more than "
            "one house property, foreign income, total income > 50L, "
            "agricultural income > Rs 5,000."
        ),
        "summary": "ITR-1: Simple salary + interest. No capital gains.",
        "children": [],
    },

    "itr_2": {
        "title": "ITR-2",
        "full_text": (
            "For individuals/HUFs not having income from business or profession. "
            "Covers: salary, multiple house properties, capital gains (equity, "
            "debt, property, crypto/VDA), foreign income, income > 50L. "
            "Use when capital gains or crypto are present."
        ),
        "summary": "ITR-2: Salary + capital gains + crypto. No business income.",
        "children": [],
    },

    "itr_3": {
        "title": "ITR-3",
        "full_text": (
            "For individuals/HUFs having income from business or profession "
            "along with salary, capital gains, etc. Covers all income types."
        ),
        "summary": "ITR-3: Business/professional income + all other types.",
        "children": [],
    },

    "itr_4": {
        "title": "ITR-4 (Sugam)",
        "full_text": (
            "For presumptive income under 44AD, 44ADA, or 44AE. "
            "Total income up to Rs 50 lakh. Simplified form for small "
            "businesses and professionals. NOT eligible if capital gains present."
        ),
        "summary": "ITR-4: Presumptive income (44AD/44ADA). No capital gains.",
        "children": [],
    },

    # ──────────────── HRA PROVISIONS ─────────────
    "hra_provisions": {
        "title": "HRA Exemption Rules",
        "summary": "House Rent Allowance exemption under Section 10(13A).",
        "children": ["section_10_13A"],
    },

    "section_10_13A": {
        "title": "Section 10(13A): HRA Exemption",
        "full_text": (
            "HRA exemption = minimum of: "
            "(1) Actual HRA received from employer, "
            "(2) 50% of basic salary for metro cities (Delhi, Mumbai, Kolkata, Chennai) "
            "or 40% for non-metro, "
            "(3) Rent paid minus 10% of basic salary. "
            "Conditions: rent receipts required, PAN of landlord if rent > Rs 1L/year. "
            "Only available under Old Regime."
        ),
        "summary": "HRA exemption: min(HRA, 50%/40% basic, rent-10% basic). Old regime only.",
        "children": [],
    },
}


class PageIndexRetriever:
    """Tree-walk retriever for structured legal section lookup."""

    def __init__(self, tree: dict | None = None):
        """Initialize with the page index tree.

        Args:
            tree: Custom tree dict. Defaults to PAGE_INDEX_TREE.
        """
        self.tree = tree or PAGE_INDEX_TREE
        # Build a flat index for keyword search
        self._flat_index = self._build_flat_index()

    def _build_flat_index(self) -> list[dict]:
        """Build a flat list of all nodes for keyword matching."""
        index = []
        for node_id, node in self.tree.items():
            if node_id == "root":
                continue
            index.append({
                "id": node_id,
                "title": node.get("title", ""),
                "summary": node.get("summary", ""),
                "full_text": node.get("full_text", ""),
                "children": node.get("children", []),
            })
        return index

    def retrieve(self, query: str, top_k: int = 1) -> dict[str, Any]:
        """Retrieve the most relevant section for a query.

        Args:
            query: Search query (e.g., "Section 80CCD(2) employer NPS")

        Returns:
            {
                "node_id": str,
                "title": str,
                "retrieved_text": str,
                "relevance_score": float,
                "children": list[str],
            }
        """
        query_lower = query.lower()

        # Step 1: Try exact section match
        section_match = self._match_section_ref(query)
        if section_match:
            return section_match

        # Step 2: Keyword scoring across all nodes
        scored = []
        for node in self._flat_index:
            score = self._score_node(query_lower, node)
            if score > 0:
                scored.append((score, node))

        if not scored:
            return {
                "node_id": "root",
                "title": self.tree["root"]["title"],
                "retrieved_text": self.tree["root"]["summary"],
                "relevance_score": 0.0,
                "children": self.tree["root"]["children"],
            }

        scored.sort(key=lambda x: x[0], reverse=True)

        if top_k == 1:
            best_score, best_node = scored[0]
            return {
                "node_id": best_node["id"],
                "title": best_node["title"],
                "retrieved_text": best_node.get("full_text") or best_node.get("summary", ""),
                "relevance_score": min(1.0, best_score / 10.0),
                "children": best_node.get("children", []),
            }
        else:
            results = []
            for score, node in scored[:top_k]:
                results.append({
                    "node_id": node["id"],
                    "title": node["title"],
                    "retrieved_text": node.get("full_text") or node.get("summary", ""),
                    "relevance_score": min(1.0, score / 10.0),
                    "children": node.get("children", []),
                })
            return results

    def retrieve_multi(self, query: str, top_k: int = 3) -> list[dict]:
        """Retrieve multiple relevant sections."""
        result = self.retrieve(query, top_k=top_k)
        if isinstance(result, list):
            return result
        return [result]

    def _match_section_ref(self, query: str) -> dict | None:
        """Try to match a specific section reference in the query."""
        # Match patterns like "Section 80C", "80CCD(2)", "115BBH", "44ADA"
        patterns = [
            (r'(?:section\s*)?80CCD\s*[\(_]?\s*2\s*\)?', 'section_80CCD_2'),
            (r'(?:section\s*)?80CCD\s*[\(_]?\s*1B\s*\)?', 'section_80CCD_1B'),
            (r'(?:section\s*)?80CCH', 'section_80CCH'),
            (r'(?:section\s*)?115BBH', 'section_115BBH'),
            (r'(?:section\s*)?115BAC', 'section_115BAC'),
            (r'(?:section\s*)?111A', 'section_111A'),
            (r'(?:section\s*)?112A', 'section_112A'),
            (r'(?:section\s*)?112\b', 'section_112'),
            (r'(?:section\s*)?44ADA', 'section_44ADA'),
            (r'(?:section\s*)?87A', 'section_87A'),
            (r'(?:section\s*)?80C\b', 'section_80C'),
            (r'(?:section\s*)?80D\b', 'section_80D'),
            (r'(?:section\s*)?80E\b', 'section_80E'),
            (r'(?:section\s*)?80G\b', 'section_80G'),
            (r'(?:section\s*)?80TTA\b', 'section_80TTA'),
            (r'(?:section\s*)?80TTB\b', 'section_80TTB'),
            (r'(?:section\s*)?80GG\b', 'section_80GG'),
            (r'(?:section\s*)?24\s*\(?b\)?', 'section_24b'),
            (r'(?:section\s*)?192\b', 'section_192'),
            (r'(?:section\s*)?194A\b', 'section_194A'),
            (r'(?:section\s*)?194I\b', 'section_194I'),
            (r'(?:section\s*)?194S\b', 'section_194S'),
            (r'(?:section\s*)?194F\b', 'section_194F'),
            (r'(?:section\s*)?206C\b', 'section_206C'),
            (r'(?:section\s*)?17\s*\(?2\)?', 'section_17_2'),
            (r'(?:section\s*)?10\s*\(?13A\)?', 'section_10_13A'),
            (r'\bITR[\-\s]*1\b', 'itr_1'),
            (r'\bITR[\-\s]*2\b', 'itr_2'),
            (r'\bITR[\-\s]*3\b', 'itr_3'),
            (r'\bITR[\-\s]*4\b', 'itr_4'),
        ]

        for pattern, node_id in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                node = self.tree.get(node_id)
                if node:
                    return {
                        "node_id": node_id,
                        "title": node["title"],
                        "retrieved_text": node.get("full_text") or node.get("summary", ""),
                        "relevance_score": 1.0,
                        "children": node.get("children", []),
                    }
        return None

    def _score_node(self, query_lower: str, node: dict) -> float:
        """Score a node against a query using keyword matching."""
        score = 0.0
        node_text = (
            node.get("title", "") + " " +
            node.get("summary", "") + " " +
            node.get("full_text", "")
        ).lower()

        # Tokenize query
        query_terms = re.findall(r'\b\w+\b', query_lower)

        for term in query_terms:
            if len(term) < 3:
                continue
            if term in node_text:
                score += 1.0
                # Bonus for title match
                if term in node.get("title", "").lower():
                    score += 2.0

        return score

    def get_node(self, node_id: str) -> dict | None:
        """Get a specific node by ID."""
        node = self.tree.get(node_id)
        if not node:
            return None
        return {
            "node_id": node_id,
            "title": node.get("title", ""),
            "retrieved_text": node.get("full_text") or node.get("summary", ""),
            "children": node.get("children", []),
        }

    def get_node_count(self) -> int:
        """Return the total number of nodes in the tree."""
        return len(self.tree)
