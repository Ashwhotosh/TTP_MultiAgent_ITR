"""
transaction_classifier_v2.py -- Real-world transaction classification pipeline.

Three stages:
    1. Description normalization (rule-based, fast)
    2. Pattern pre-classifier (high-precision rules for unambiguous cases)
    3. Multilingual ML classifier (kNN on multilingual MiniLM embeddings)
    4. LLM fallback for low-confidence cases (only ~5-10% of transactions)

Handles:
    - Noisy bank statement formats (WDL TFR, UTR refs, transaction IDs)
    - Hinglish vendor names (Aman Juicewala, Sharma Sweet Mart)
    - 12-category taxonomy with tax_relevance flags
    - Confidence scoring for fallback decisions
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from parsers.description_normalizer import DescriptionNormalizer


CLASSIFIER_PATH = Path("models/transaction_classifier_v2.pkl")
METRICS_PATH = Path("models/transaction_classifier_v2_metrics.json")

# Label -> ITR schedule mapping
LABEL_INFO = {
    "SALARY_INCOME":         {"schedule": "Schedule Salary", "tax_relevance": "income", "risk_weight": 0},
    "FREELANCE_INCOME":      {"schedule": "Schedule BP / OS", "tax_relevance": "income", "risk_weight": 25},
    "CRYPTO_TRANSACTION":    {"schedule": "Schedule VDA",    "tax_relevance": "income", "risk_weight": 30},
    "CAPITAL_MARKET":        {"schedule": "Schedule CG",     "tax_relevance": "income", "risk_weight": 20},
    "INTEREST_INCOME":       {"schedule": "Schedule OS",     "tax_relevance": "income", "risk_weight": 10},
    "DIVIDEND_INCOME":       {"schedule": "Schedule OS",     "tax_relevance": "income", "risk_weight": 10},
    "RENT_PAID":             {"schedule": "HRA/80GG",        "tax_relevance": "deduction_opportunity", "risk_weight": 0},
    "INSURANCE_PREMIUM":     {"schedule": "80C/80D",         "tax_relevance": "deduction_opportunity", "risk_weight": 0},
    "LOAN_EMI":              {"schedule": "24(b)/80C",       "tax_relevance": "deduction_opportunity", "risk_weight": 0},
    "INVESTMENT_TAX_SAVING": {"schedule": "80C/80CCD",       "tax_relevance": "deduction_opportunity", "risk_weight": 0},
    "REGULAR_EXPENSE":       {"schedule": "N/A",             "tax_relevance": "none", "risk_weight": 0},
    "TRANSFER":              {"schedule": "N/A",             "tax_relevance": "none", "risk_weight": 0},
}

# Stage 2: Pattern Pre-Classifier (HIGH PRECISION rules)
# Triggered only when nearly certain; handles unambiguous 70% of transactions fast.
PATTERN_RULES = [
    # Salary
    (re.compile(r"\bSALARY\b|\bSAL\s*CR\b|\bMONTHLY\s*PAY\b", re.IGNORECASE), "SALARY_INCOME", 0.95),

    # Crypto exchanges -- exact known names
    (re.compile(
        r"\b(WAZIRX|COINDCX|COINSWITCH|ZEBPAY|BITBNS|MUDREX|PI42|GIOTTUS|UNOCOIN"
        r"|KUCOIN|BINANCE|BUYUCOIN|VAULD|CRYPTOPRO)\b",
        re.IGNORECASE,
    ), "CRYPTO_TRANSACTION", 0.95),
    (re.compile(r"\bCRYPTO\b|\bBITCOIN\b|\bETHEREUM\b|\bUSDT\b|\bBTC\s*(BUY|SELL)\b", re.IGNORECASE), "CRYPTO_TRANSACTION", 0.85),

    # Brokers / capital markets
    (re.compile(
        r"\b(ZERODHA|GROWW|UPSTOX|ANGEL\s*BROKING|ICICI\s*DIRECT|HDFC\s*SEC"
        r"|KOTAK\s*SEC|MOTILAL|5PAISA|KITE)\b",
        re.IGNORECASE,
    ), "CAPITAL_MARKET", 0.95),
    (re.compile(r"\b(MUTUAL\s*FUND|MF\s*REDEMPTION|SIP\s*PURCHASE|ELSS\s*REDEEM)\b", re.IGNORECASE), "CAPITAL_MARKET", 0.85),

    # Foreign remitters (freelance)
    (re.compile(
        r"\b(UPWORK|FIVERR|TOPTAL|WISE|PAYPAL|PAYONEER|REMITLY|STRIPE\s*PAY|FREELANCER\s*COM)\b",
        re.IGNORECASE,
    ), "FREELANCE_INCOME", 0.95),
    (re.compile(r"\bUSD\s*(REMITTANCE|WIRE)\b|\bFOREIGN\s*REMITTANCE\b", re.IGNORECASE), "FREELANCE_INCOME", 0.85),

    # Interest
    (re.compile(
        r"\bFD\s*INT\b|\bSAVINGS\s*INT\b|\b(FIXED\s*DEPOSIT|RECURRING\s*DEPOSIT)\s*INTEREST\b|\bINT\s*CR\b",
        re.IGNORECASE,
    ), "INTEREST_INCOME", 0.95),

    # Dividend
    (re.compile(r"\bDIVIDEND\b", re.IGNORECASE), "DIVIDEND_INCOME", 0.90),

    # Loan EMI
    (re.compile(
        r"\b(HOUSING\s*LOAN|HOME\s*LOAN|CAR\s*LOAN|AUTO\s*LOAN|EDUCATION\s*LOAN|TWO\s*WHEELER\s*LOAN)\s*EMI\b"
        r"|\bEMI\b.*\bLOAN\b|\bLOAN\b.*\bEMI\b",
        re.IGNORECASE,
    ), "LOAN_EMI", 0.95),

    # Insurance
    (re.compile(
        r"\b(LIC|HDFC\s*LIFE|STAR\s*HEALTH|ICICI\s*PRU|MAX\s*BUPA|TATA\s*AIG|BAJAJ\s*ALLIANZ"
        r"|RELIANCE\s*GENERAL|NIVA\s*BUPA)\b.*\b(PREMIUM|POLICY)\b",
        re.IGNORECASE,
    ), "INSURANCE_PREMIUM", 0.95),
    (re.compile(r"\bINSURANCE\s*PREMIUM\b|\bPOLICY\s*PAYMENT\b", re.IGNORECASE), "INSURANCE_PREMIUM", 0.85),

    # Tax-saving investments
    (re.compile(
        r"\b(PPF|NPS\s*TRUST|VOLUNTARY\s*NPS|ELSS\s*SIP|SUKANYA\s*SAMRIDHI|NSC\b|TAX\s*SAVER\s*FD)\b",
        re.IGNORECASE,
    ), "INVESTMENT_TAX_SAVING", 0.95),

    # Rent
    (re.compile(
        r"\bRENT\b.*\b(LANDLORD|HOUSE|FLAT|PROPERTY|APARTMENT|PG|RESIDENCY|NIWAS)\b"
        r"|\bLANDLORD\b|\bHOUSE\s*RENT\b|\bFLAT\s*RENT\b",
        re.IGNORECASE,
    ), "RENT_PAID", 0.90),

    # Major consumer brands -- food, shopping, streaming, delivery (high precision, low tax-relevance)
    (re.compile(
        r"\b(ZOMATO|SWIGGY|DUNZO|AMZN\s*MKTP|MYNTRA|NYKAA|AJIO|MEESHO|FIRSTCRY|TATACLIQ"
        r"|BIGBASKET|BLINKIT|ZEPTO|INSTAMART|JIOMART|DMART"
        r"|UBER|RAPIDO|IRCTC|NETFLIX|SPOTIFY|DISNEY|HOTSTAR|BOOKMYSHOW|DOMINOS|MCDONALDS|KFC|SUBWAY"
        r"|AIRTEL|JIOFIBER|BESCOM|MSEB|MAHANAGAR\s*GAS)\b",
        re.IGNORECASE,
    ), "REGULAR_EXPENSE", 0.85),

    # ATM/Cash withdrawals
    (re.compile(r"\bATM\s*WD?L\b|\bCASH\s*WD?L\b|\bATM\s*WITHDRAWAL\b", re.IGNORECASE), "TRANSFER", 0.95),
]


_SHARED_EMBEDDERS: dict = {}


class RealWorldTransactionClassifier:
    """Production-grade transaction classifier for Indian bank statements."""

    DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, model_name: str = DEFAULT_MODEL, k: int = 5,
                 confidence_threshold: float = 0.65):
        self.model_name = model_name
        self.k = k
        self.confidence_threshold = confidence_threshold
        self.normalizer = DescriptionNormalizer()
        self._embedder = None
        self._train_embeddings = None
        self._train_labels = None

    @property
    def embedder(self):
        global _SHARED_EMBEDDERS
        if self._embedder is None:
            if self.model_name in _SHARED_EMBEDDERS:
                self._embedder = _SHARED_EMBEDDERS[self.model_name]
            else:
                from sentence_transformers import SentenceTransformer
                print(f"[Classifier] Loading {self.model_name}...")
                self._embedder = SentenceTransformer(self.model_name)
                _SHARED_EMBEDDERS[self.model_name] = self._embedder
        return self._embedder

    # ── Training ──

    def train(self, csv_path: str = "data/training/transaction_labels_v2.csv") -> dict:
        import pandas as pd
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score

        df = pd.read_csv(csv_path)
        df = df.dropna(subset=["description", "label"])
        print(f"[Classifier] Loaded {len(df)} labeled transactions")
        print("\n[Classifier] Label distribution:")
        for label, count in df["label"].value_counts().items():
            print(f"   {label}: {count}")

        print("\n[Classifier] Normalizing descriptions...")
        df["cleaned"] = df["description"].apply(
            lambda d: self.normalizer.normalize(d).cleaned
        )

        train_df, test_df = train_test_split(
            df, test_size=0.20, stratify=df["label"], random_state=42
        )

        print(f"[Classifier] Embedding {len(train_df)} training samples...")
        train_embeddings = self.embedder.encode(
            train_df["cleaned"].tolist(),
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        self._train_embeddings = train_embeddings
        self._train_labels = train_df["label"].tolist()

        print(f"[Classifier] Evaluating on {len(test_df)} test samples...")
        results = []
        for _, row in test_df.iterrows():
            pred = self.classify(row["description"])
            results.append({
                "true_label": row["label"],
                "predicted_label": pred["label"],
                "confidence": pred["confidence"],
                "stage": pred["stage"],
            })

        true_labels = [r["true_label"] for r in results]
        pred_labels = [r["predicted_label"] for r in results]
        accuracy = accuracy_score(true_labels, pred_labels)
        per_category = classification_report(true_labels, pred_labels, output_dict=True, zero_division=0)
        stage_counts = Counter(r["stage"] for r in results)

        Path("models").mkdir(parents=True, exist_ok=True)
        with open(CLASSIFIER_PATH, "wb") as f:
            pickle.dump({
                "train_embeddings": train_embeddings,
                "train_labels": self._train_labels,
                "k": self.k,
                "model_name": self.model_name,
                "confidence_threshold": self.confidence_threshold,
            }, f)

        metrics = {
            "model": "RealWorldTransactionClassifier",
            "embedder": self.model_name,
            "k": self.k,
            "confidence_threshold": self.confidence_threshold,
            "n_train": len(train_df),
            "n_test": len(test_df),
            "test_accuracy": round(accuracy, 4),
            "per_category": per_category,
            "stage_usage": dict(stage_counts),
            "labels": sorted(set(self._train_labels)),
        }
        METRICS_PATH.write_text(json.dumps(metrics, indent=2))

        print(f"\n[Classifier] === Training Results ===")
        print(f"  Overall Accuracy: {accuracy:.4f}")
        print(f"\n  Per-Category F1:")
        for label in sorted(LABEL_INFO.keys()):
            if label in per_category:
                f1 = per_category[label].get("f1-score", 0)
                support = per_category[label].get("support", 0)
                print(f"    {label:25s}: F1={f1:.3f} (n={support})")
        print(f"\n  Stage Usage:")
        for stage, count in stage_counts.items():
            pct = count / len(results) * 100
            print(f"    {stage}: {count} ({pct:.1f}%)")
        print(f"\n[Classifier] Model saved -> {CLASSIFIER_PATH}")

        return metrics

    # ── Inference ──

    def classify(self, description: str, direction_hint: str | None = None) -> dict:
        """
        Classify a transaction through the 3-stage pipeline.

        Returns dict with: label, confidence, stage, schedule, tax_relevance,
        risk_weight, transaction_method, direction, cleaned, extracted_merchant.
        """
        normalized = self.normalizer.normalize(description, direction_hint)
        cleaned = normalized.cleaned

        # Stage 2: Pattern pre-classifier (fast, high precision)
        for pattern, label, conf in PATTERN_RULES:
            if pattern.search(cleaned) or pattern.search(description):
                return self._build_result(description, cleaned, label, conf, "pattern", normalized)

        # Stage 3: ML classifier (kNN on embeddings)
        if self._train_embeddings is None:
            self.load()

        ml_result = self._classify_ml(cleaned)

        if ml_result["confidence"] >= self.confidence_threshold:
            return self._build_result(
                description, cleaned, ml_result["label"],
                ml_result["confidence"], "ml", normalized,
                extras={"top_k_matches": ml_result["top_k_matches"]},
            )

        # Stage 4: LLM fallback for ambiguous cases
        llm_result = self._llm_fallback(description, cleaned)
        if llm_result:
            return self._build_result(
                description, cleaned, llm_result["label"],
                llm_result["confidence"], "llm_fallback", normalized,
            )

        # Use ML result even at low confidence
        return self._build_result(
            description, cleaned, ml_result["label"],
            ml_result["confidence"], "ml_low_conf", normalized,
        )

    def _classify_ml(self, cleaned: str) -> dict:
        """kNN classification using cosine similarity on embeddings."""
        query_emb = self.embedder.encode([cleaned], convert_to_numpy=True)[0]
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
        train_norm = self._train_embeddings / (
            np.linalg.norm(self._train_embeddings, axis=1, keepdims=True) + 1e-9
        )
        similarities = train_norm @ query_norm

        top_k_idx = np.argsort(similarities)[-self.k:][::-1]
        top_k_labels = [self._train_labels[i] for i in top_k_idx]
        top_k_sims = [float(similarities[i]) for i in top_k_idx]

        label_counts = Counter(top_k_labels)
        predicted = label_counts.most_common(1)[0][0]
        matching_sims = [s for l, s in zip(top_k_labels, top_k_sims) if l == predicted]
        confidence = float(np.mean(matching_sims))

        return {
            "label": predicted,
            "confidence": round(confidence, 4),
            "top_k_matches": [
                {"label": l, "similarity": round(s, 4)}
                for l, s in zip(top_k_labels, top_k_sims)
            ],
        }

    def _llm_fallback(self, description: str, cleaned: str) -> dict | None:
        """LLM fallback for ambiguous cases. Returns None if Ollama unavailable."""
        try:
            from tools.ollama_client import chat as llm_chat
            prompt = (
                f'Classify this Indian bank transaction into ONE category.\n\n'
                f'Transaction: "{description}"\n'
                f'Cleaned: "{cleaned}"\n\n'
                f'Categories:\n'
                f'- SALARY_INCOME: Employer salary credit\n'
                f'- FREELANCE_INCOME: Foreign remittance, Upwork, consulting\n'
                f'- CRYPTO_TRANSACTION: Any crypto exchange\n'
                f'- CAPITAL_MARKET: Equity/MF trading\n'
                f'- INTEREST_INCOME: FD/Savings interest\n'
                f'- DIVIDEND_INCOME: Company dividends\n'
                f'- RENT_PAID: Monthly rent to landlord\n'
                f'- INSURANCE_PREMIUM: LIC/Health insurance premium\n'
                f'- LOAN_EMI: Home/Car/Education loan EMI\n'
                f'- INVESTMENT_TAX_SAVING: PPF/NPS/ELSS contributions\n'
                f'- REGULAR_EXPENSE: Food, shopping, utilities (Hinglish vendors too)\n'
                f'- TRANSFER: P2P, ATM, internal transfers\n\n'
                f'Respond ONLY in JSON: {{"label": "CATEGORY", "confidence": 0.0-1.0}}'
            )
            content = llm_chat(
                prompt=prompt,
                temperature=0.1
            )
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
                if result.get("label") in LABEL_INFO:
                    return result
        except Exception:
            pass
        return None

    def _build_result(self, description: str, cleaned: str, label: str,
                      confidence: float, stage: str, normalized,
                      extras: dict | None = None) -> dict:
        info = LABEL_INFO.get(label, {})
        result = {
            "description": description,
            "cleaned": cleaned,
            "label": label,
            "confidence": round(confidence, 4),
            "stage": stage,
            "schedule": info.get("schedule", "Unknown"),
            "tax_relevance": info.get("tax_relevance", "none"),
            "risk_weight": info.get("risk_weight", 0),
            "transaction_method": normalized.transaction_method,
            "direction": normalized.direction,
            "extracted_merchant": normalized.extracted_merchant,
        }
        if extras:
            result.update(extras)
        return result

    def classify_batch(self, descriptions: list[str],
                       direction_hints: list[str] | None = None) -> list[dict]:
        if direction_hints is None:
            direction_hints = [None] * len(descriptions)
        return [self.classify(d, h) for d, h in zip(descriptions, direction_hints)]

    def load(self):
        if not CLASSIFIER_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {CLASSIFIER_PATH}. "
                "Run: python -m models.transaction_classifier_v2 --train"
            )
        with open(CLASSIFIER_PATH, "rb") as f:
            data = pickle.load(f)
        self._train_embeddings = data["train_embeddings"]
        self._train_labels = data["train_labels"]
        self.k = data.get("k", 5)
        self.confidence_threshold = data.get("confidence_threshold", 0.65)


# ── CLI ──

def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--train", action="store_true")
    group.add_argument("--classify", type=str, metavar="DESC")
    group.add_argument("--batch", type=str, metavar="CSV")
    group.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    clf = RealWorldTransactionClassifier()

    if args.train:
        clf.train()

    elif args.classify:
        result = clf.classify(args.classify)
        print(json.dumps(result, indent=2))

    elif args.batch:
        import pandas as pd
        df = pd.read_csv(args.batch)
        for desc in df["description"].tolist():
            r = clf.classify(desc)
            print(f"{r['label']:25s} ({r['confidence']:.3f}) [{r['stage']:8s}]  {desc[:80]}")

    elif args.demo:
        demos = [
            "WDL TFR UPI/DR/48188486544/ZOMATO/UTIB/ETERNAL/paym009769258663 AT 11669 SHIVAJI NAGAR NASIK",
            "UPI/DR/AMAN JUICEWALA/SHOP NO 4/MIRA ROAD",
            "UPI/DR/SHARMA SWEET MART/PUNE",
            "WDL TFR NEFT-SALARY-INFOSYS BPM LTD-MAR25-UTR123456",
            "UPI/DR/MUDREX/CRYPTO INVESTMENT/REF789",
            "ACH/DR/HDFC HOUSING LOAN EMI MAR25/CUST1234",
            "UPI/CR/UPWORK GLOBAL INC USD WIRE INWARD",
            "UPI/DR/KAKA HALWAI/PUNE CAMP",
            "WDL TFR NEFT-RENT-PRIYA SHARMA LANDLORD-UTR123456",
            "INT CR HDFC SAVINGS Q4/2025",
            "UPI/DR/MAA TARA CYCLE STORES",
        ]
        for desc in demos:
            r = clf.classify(desc)
            print(f"\nIN:  {desc}")
            print(f"  -> {r['label']} (conf={r['confidence']:.3f}, stage={r['stage']})")
            print(f"  Cleaned: {r['cleaned']}")
            print(f"  Tax relevance: {r['tax_relevance']} | Schedule: {r['schedule']}")


if __name__ == "__main__":
    main()
