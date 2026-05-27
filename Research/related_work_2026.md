# Related Work — 2026 arXiv papers to cite / position against

> Pulled from arXiv (verified titles, authors, IDs). These are the recent works
> that overlap with FinITR-AI's core ideas. Citing them in the Literature Survey
> pre-empts the "your verification/grounding idea isn't new" novelty objection.
> Our defensible novelty = the **India-ITR-specific assembly + notice prediction +
> offline**, not the verification technique itself.

---

## 1. Synedrion — agentic tax-prep software (ICSE 2026)
- **Title:** An LLM Agentic Approach for Legal-Critical Software: A Case Study for Tax Prep Software
- **Authors:** Sina Gogani-Khiabani, Ashutosh Trivedi, Diptikalyan Saha, Saeid Tizpaz-Niari
- **arXiv:** 2509.13471 — https://arxiv.org/abs/2509.13471
- **Date / venue:** Submitted Sep 2025, revised Mar 2026; ICSE 2026
- **What it does:** Multi-agent LLM framework that translates U.S. tax statutes into executable code and validates it with (higher-order) metamorphic testing.
- **Relevance to us:** Closest *multi-agent + tax* peer at a top venue, but a **different problem** (generates/tests tax *software*, U.S.-focused) — not end-to-end filing. Cite to show our problem framing (Indian filing assistant) is distinct, and that agentic tax systems are a taken-seriously research direction.

## 2. VeNRA — neuro-symbolic financial reasoning (deterministic ledger + hallucination detector)
- **Title:** Neuro-Symbolic Financial Reasoning via Deterministic Fact Ledgers and Adversarial Low-Latency Hallucination Detector
- **Author:** Pedram Agand
- **arXiv:** 2603.04663 — https://arxiv.org/abs/2603.04663
- **Date:** Mar 2026
- **What it does:** Combines deterministic fact ledgers with a specialized error-detection model to eliminate hallucinations in financial reasoning where plain RAG fails.
- **Relevance to us:** **The most important one.** Conceptually closest to our *deterministic engine + Critic veto* design. MUST be cited and differentiated, or a reviewer will say our verification idea is already published. Our distinction: domain-specialised multi-agent assembly for Indian ITR with an actual filing output, not a general financial-reasoning detector.

## 3. Fine-grained knowledge verification for financial RAG
- **Title:** Mitigating Hallucination in Financial Retrieval-Augmented Generation via Fine-Grained Knowledge Verification
- **Authors:** Taoye Yin, Haoyuan Hu, Yaxin Fan, Xinhao Chen, Xinya Wu, Kai Deng, Kezun Zhang, Feng Wang
- **arXiv:** 2602.05723 — https://arxiv.org/abs/2602.05723
- **Date:** Feb 2026
- **What it does:** RL framework that decomposes financial answers into atomic knowledge units and verifies each unit to cut hallucinations in financial RAG while keeping informativeness.
- **Relevance to us:** Directly parallels our RAG-grounding + claim-level verification. Cite as the contemporary financial-RAG-verification baseline; our Critic does claim-level checking too, but wired into a *vetoing re-run loop* over a tax engine rather than as an RL fine-tuning objective.

## 4. Tool Receipts / NabaOS — practical agent hallucination detection
- **Title:** Tool Receipts, Not Zero-Knowledge Proofs: Practical Hallucination Detection for AI Agents
- **Author:** Abhinaba Basu
- **arXiv:** 2603.10060 — https://arxiv.org/abs/2603.10060
- **Date:** Mar 2026
- **What it does:** Lightweight framework using HMAC-signed "tool receipts" + epistemic classification to detect agent hallucinations in real time (reports 94.2% coverage, low latency).
- **Relevance to us:** Verifying that an agent *actually invoked* its tools rather than fabricating the result — relevant to our claim that arithmetic is always deferred to the calculator tool. Cite as related agent-verification work; lighter touch than #2 and #3.

---

## Ready-to-paste LaTeX bibitems (continue numbering after ref14)

> Drop into `Thesis_MP/3.Thesis_Text/09_bibliography.tex` **only if** you add the
> corresponding `\cite{}` calls in the Literature Survey. Keys ref15–ref18.

```latex
\bibitem{ref15}
Gogani-Khiabani, S., Trivedi, A., Saha, D., \& Tizpaz-Niari, S. (2026).
\textit{An LLM Agentic Approach for Legal-Critical Software: A Case Study for
Tax Prep Software}. 2026 IEEE/ACM 48th International Conference on Software
Engineering (ICSE). arXiv:2509.13471.

\bibitem{ref16}
Agand, P. (2026). \textit{Neuro-Symbolic Financial Reasoning via Deterministic
Fact Ledgers and Adversarial Low-Latency Hallucination Detector}.
arXiv:2603.04663.

\bibitem{ref17}
Yin, T., Hu, H., Fan, Y., Chen, X., Wu, X., Deng, K., Zhang, K., \& Wang, F.
(2026). \textit{Mitigating Hallucination in Financial Retrieval-Augmented
Generation via Fine-Grained Knowledge Verification}. arXiv:2602.05723.

\bibitem{ref18}
Basu, A. (2026). \textit{Tool Receipts, Not Zero-Knowledge Proofs: Practical
Hallucination Detection for AI Agents}. arXiv:2603.10060.
```

---

## Other relevant (non-arXiv) sources found
- **Personal AI-Tax Advisor (India Specific)** — IJCRT, paper IJCRT2510716. https://www.ijcrt.org/papers/IJCRT2510716.pdf (another low-tier India ITR-AI peer)
- **EZTax — AI-based AIS reconciliation for AY 2026-27** (commercial) — shows AIS reconciliation is already a shipped commercial feature, so it is not itself a novelty claim.

> Note: arXiv preprints are not peer-reviewed (except #1, ICSE 2026). For a formal
> submission, prefer citing published versions where they exist and verify each ID
> on arxiv.org before final submission.
