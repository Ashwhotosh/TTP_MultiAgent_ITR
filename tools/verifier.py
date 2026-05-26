"""
verifier.py -- NLI-based faithfulness verifier.

Uses a cross-encoder model (DeBERTa-v3-small or similar) to verify whether
a generated claim is entailed by a given evidence passage. This catches
hallucinations in LLM-generated tax advice.

Labels:
    ENTAILMENT    -> claim is supported by evidence (FAITHFUL)
    CONTRADICTION -> claim is directly contradicted (HALLUCINATED)
    NEUTRAL       -> insufficient evidence (UNVERIFIED)
"""
from __future__ import annotations

from typing import Any


_SHARED_NLI_MODELS: dict = {}


class FaithfulnessVerifier:
    """NLI cross-encoder for claim verification."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-xsmall"):
        """Initialize the NLI model.

        Args:
            model_name: HuggingFace model name for NLI.
                        Defaults to a small but accurate model.
        """
        self.model_name = model_name
        self._model = None
        self._labels = ["CONTRADICTION", "ENTAILMENT", "NEUTRAL"]

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        global _SHARED_NLI_MODELS
        if self._model is None:
            if self.model_name in _SHARED_NLI_MODELS:
                self._model = _SHARED_NLI_MODELS[self.model_name]
            else:
                try:
                    from sentence_transformers import CrossEncoder
                    self._model = CrossEncoder(self.model_name)
                    _SHARED_NLI_MODELS[self.model_name] = self._model
                except Exception as e:
                    print(f"[VERIFIER] Warning: Could not load NLI model: {e}")
                    print("[VERIFIER] Falling back to keyword-based verification")
                    self._model = "FALLBACK"

    def verify(self, claim: str, evidence: str) -> dict[str, Any]:
        """Verify whether a claim is faithful to the evidence.

        Args:
            claim: The statement to verify (e.g., "Section 80CCD(2) allows
                   employer NPS deduction up to 14% of basic salary.")
            evidence: The source text to check against (e.g., retrieved
                      section text from PageIndex or corpus).

        Returns:
            {
                "claim": str,
                "evidence_snippet": str,
                "label": "FAITHFUL" | "HALLUCINATED" | "UNVERIFIED",
                "score": float,      # 0-1 confidence
                "raw_scores": dict,  # per-label scores
            }
        """
        self._load_model()

        if self._model == "FALLBACK":
            return self._fallback_verify(claim, evidence)

        try:
            # Cross-encoder expects (premise, hypothesis) = (evidence, claim)
            scores = self._model.predict([(evidence, claim)])

            # scores shape: (1, 3) -> [contradiction, entailment, neutral]
            if hasattr(scores, 'tolist'):
                score_list = scores.tolist()
            else:
                score_list = list(scores)

            # Handle both 1D and 2D output
            if isinstance(score_list[0], list):
                score_list = score_list[0]

            raw_scores = {
                label: round(float(s), 4)
                for label, s in zip(self._labels, score_list)
            }

            # Determine label
            max_label = max(raw_scores, key=raw_scores.get)
            max_score = raw_scores[max_label]

            label_map = {
                "ENTAILMENT": "FAITHFUL",
                "CONTRADICTION": "HALLUCINATED",
                "NEUTRAL": "UNVERIFIED",
            }

            return {
                "claim": claim,
                "evidence_snippet": evidence[:200] + "..." if len(evidence) > 200 else evidence,
                "label": label_map.get(max_label, "UNVERIFIED"),
                "score": max_score,
                "raw_scores": raw_scores,
            }

        except Exception as e:
            return {
                "claim": claim,
                "evidence_snippet": evidence[:200],
                "label": "UNVERIFIED",
                "score": 0.0,
                "raw_scores": {},
                "error": str(e),
            }

    def _fallback_verify(self, claim: str, evidence: str) -> dict[str, Any]:
        """Keyword-based fallback when NLI model is unavailable.

        Checks how many key terms from the claim appear in the evidence.
        """
        claim_lower = claim.lower()
        evidence_lower = evidence.lower()

        # Extract key terms (numbers, section references, percentages)
        import re
        claim_terms = set(re.findall(r'\b(?:\d+%?|section\s+\w+|rs\.?\s*[\d,]+)\b',
                                      claim_lower))
        if not claim_terms:
            # Fallback to word overlap
            claim_words = set(claim_lower.split())
            evidence_words = set(evidence_lower.split())
            overlap = len(claim_words & evidence_words) / max(len(claim_words), 1)
            label = "FAITHFUL" if overlap > 0.5 else "UNVERIFIED"
            return {
                "claim": claim,
                "evidence_snippet": evidence[:200],
                "label": label,
                "score": round(overlap, 4),
                "raw_scores": {"word_overlap": round(overlap, 4)},
                "method": "fallback_word_overlap",
            }

        matched = sum(1 for t in claim_terms if t in evidence_lower)
        score = matched / len(claim_terms) if claim_terms else 0

        if score >= 0.7:
            label = "FAITHFUL"
        else:
            label = "UNVERIFIED"

        return {
            "claim": claim,
            "evidence_snippet": evidence[:200],
            "label": label,
            "score": round(score, 4),
            "raw_scores": {"term_match": round(score, 4)},
            "method": "fallback_term_match",
        }

    def batch_verify(self, claims_evidence: list[tuple[str, str]]
                     ) -> list[dict[str, Any]]:
        """Verify multiple (claim, evidence) pairs.

        Args:
            claims_evidence: List of (claim, evidence) tuples.

        Returns:
            List of verification results.
        """
        return [self.verify(claim, evidence) for claim, evidence in claims_evidence]
