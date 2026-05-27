# FinITR-AI v3 — Future Plan & Improvement Roadmap

> Internal planning doc. **Not** thesis content. Purpose: rank the candidate
> add-ons by how much they actually change the project, so we know what is a
> genuine game-changer versus nice-to-have polish.

## How to read this

- **Game-changer?** — Does it change the project's *core value or story*, or is it
  incremental? Judged for the **long-term product** (TrackPay direction), not just the viva.
- **Effort** — S (hours), M (1–2 days), L (a week+).
- **Risk** — chance it breaks the working, already-evaluated system / fails in a live demo.
- **1-day viable?** — Can a *safe, defensible* version ship in the one extra day before viva?
- **Before → After** — concrete change for your understanding.

Current baseline (what exists today): multi-agent verify/veto loop, deterministic
FY25-26 engine, transaction classifier (94.2% macro F1), notice predictor,
Form16/26AS/AIS parsers, **static** regulatory corpus (`PAGE_INDEX_TREE` in
`tools/retriever.py`), CA brief export (no approve loop), single-statement input,
fully offline.

---

## Priority 0 — Genuine game-changers (long-term)

### P0.1 — Self-updating regulatory RAG
- **Game-changer?** YES (the single biggest one for a real product).
- **Effort:** L · **Risk:** High · **1-day viable?** NO (a 1-day version is a brittle scraper that can fail live).
- **Why it matters:** Every tax tool has a built-in expiry date — when the Budget changes slabs/rules, a hard-coded corpus goes stale and needs a developer to rebuild. A pipeline that refreshes its own regulatory store (scrape CBDT circulars → embed → vector store) stays correct across assessment years with zero manual intervention.
- **Before:** Corpus frozen at FY 2025-26. Next Budget = manual code edit + redeploy. Product "dies" yearly.
- **After:** Corpus refreshes itself from official sources. Product stays evergreen across years. Differentiator no competitor (ClearTax/Quicko) advertises.
- **Caveat:** Slightly tensions the "fully offline" claim (it fetches public *rules*, not user data — must be framed carefully). Needs robust scraping + a "last verified on" provenance stamp so we never silently trust a bad scrape.

### P0.2 — Direct e-filing / ITD JSON hand-off
- **Game-changer?** YES (turns an *advisor* into a *filer*).
- **Effort:** L · **Risk:** High (external API, auth, compliance) · **1-day viable?** NO.
- **Why it matters:** Right now we produce a correct return; the user still files it elsewhere. One-click "file this" closes the loop and is the difference between a project and a product people pay for.
- **Before:** Output is ITR JSON the user uploads to the portal manually.
- **After:** Generate + validate + submit (or push to the offline utility) in one flow. End-to-end ownership of the filing.
- **Caveat:** Regulatory/auth surface is large; correctly out of scope for now. Flagship long-term bet.

---

## Priority 1 — High-value, lower risk

### P1.1 — Anomaly / duplicate transaction detector  ⭐ only safe 1-day build
- **Game-changer?** MODERATE (strong user-facing value, not a story-changer).
- **Effort:** S · **Risk:** Low · **1-day viable?** YES.
- **Why it matters:** Deterministic checks (z-score outliers, round-amount flags, duplicate `(amount, desc, date)` tuples) catch data-entry and statement errors *before* they reach the return. Pure rules — no LLM, can't hallucinate. Complements (does not overlap) the notice predictor: anomaly = "this entry looks wrong," notice = "this return looks risky."
- **Before:** Suspicious/duplicate entries pass through silently into reconciliation.
- **After:** Flagged entries surfaced to the user (severity-tiered), a new results subsection, a tangible demo feature. ~100 testable lines.
- **Note:** This is the *one* item worth building in the extra day if you want something new to demo.

### P1.2 — Controlled head-to-head benchmark vs. the two prototypes
- **Game-changer?** MODERATE for the *thesis/academic* credibility (not the product).
- **Effort:** M–L · **Risk:** Low (eval-only, doesn't touch the system) · **1-day viable?** Partial (can't reimplement their systems; can run our system on their reported task framing).
- **Why it matters:** Today the lit-survey comparison is claim-vs-claim (their numbers vs ours, different datasets). A same-dataset comparison turns it into a rigorous result.
- **Before:** "We report 94.2% F1, they report 91.2% precision" — not directly comparable.
- **After:** Both evaluated on one held-out set → a defensible, apples-to-apples table.
- **Caveat:** Fully fair version needs reimplementing their pipelines (infeasible in a day). A partial version (our system on a shared task spec) is honest if labeled as such.

---

## Priority 2 — Nice-to-have / adoption polish

### P2.1 — Human-in-the-loop CA review loop  (⚠ metric is a trap)
- **Game-changer?** MODERATE for *product trust/monetization* (CA marketplace angle); LOW for the viva.
- **Effort:** M (UI) · **Risk:** Low–Med · **1-day viable?** UI yes, metric NO.
- **Why it matters:** We already emit a CA brief (`outputs/ca_brief_generator.py`). An explicit approve/override step adds an accountability checkpoint and a future revenue surface (paid CA verification).
- **Before:** CA brief is a one-way export.
- **After:** Reviewer can approve/override line items; overrides feed back as corrections.
- **⚠ Integrity warning:** A "% CA-accepted" metric (like the 87% in Auto ITR) requires **real CA review data we do not have**. Reporting one would mean fabricating a number — **forbidden**. Build the loop, do NOT invent the metric.

### P2.2 — Multi-bank consolidation + encrypted-PDF ingestion
- **Game-changer?** NO (incremental usability).
- **Effort:** M · **Risk:** Low · **1-day viable?** Partial.
- **Why it matters:** Real users have multiple accounts and password-protected statements; supporting both widens the addressable user base.
- **Before:** One statement at a time; plain PDFs only.
- **After:** Merge N statements into one reconciled view; handle encrypted PDFs.

---

## Summary ranking

| # | Feature | Game-changer? | Effort | Risk | 1-day viable? |
|---|---------|---------------|--------|------|---------------|
| P0.1 | Self-updating regulatory RAG | **Yes (top)** | L | High | No |
| P0.2 | Direct e-filing hand-off | **Yes** | L | High | No |
| P1.1 | Anomaly/duplicate detector | Moderate | S | Low | **Yes** ⭐ |
| P1.2 | Controlled head-to-head benchmark | Moderate (thesis) | M–L | Low | Partial |
| P2.1 | CA review loop (no fabricated metric) | Moderate (product) | M | Low–Med | UI only |
| P2.2 | Multi-bank + encrypted PDF | No | M | Low | Partial |

## Recommendation for the one extra day

The system is already differentiated by the things that matter (verify/veto loop,
measured faithfulness, offline, notice prediction). The biggest game-changers
(P0.1, P0.2) are **too risky to rush** and belong to the post-viva product roadmap.

- **If you want a new demo feature:** build **P1.1 (anomaly detector)** — the only low-risk, deterministic, same-day win.
- **Otherwise, higher-value use of the day:** harden tests, rebuild the thesis PDF, and personally read/voice the prose for Turnitin safety.
