"""
evaluation/metrics.py -- Evaluation Metrics for IndianTaxBench.
"""
from typing import Any, List, Dict, Set

def compute_tax_accuracy(predicted: float, expected: float) -> float:
    """Compute tax liability accuracy score between 0 and 1.
    1.0 is exact match, degrades as relative error increases.
    """
    if predicted == expected:
        return 1.0
    if expected == 0:
        # If expected is 0 and predicted is non-zero, calculate degradation based on size of prediction
        return max(0.0, 1.0 - (abs(predicted) / 50000.0))
    
    relative_error = abs(predicted - expected) / expected
    return max(0.0, 1.0 - relative_error)

def compute_itr_form_accuracy(predicted: str, expected: str) -> float:
    """1.0 if exact match, else 0.0."""
    if not predicted or not expected:
        return 0.0
    return 1.0 if str(predicted).strip().upper() == str(expected).strip().upper() else 0.0

def compute_risk_accuracy(predicted: str, expected: str) -> float:
    """1.0 if exact match, 0.5 if off by 1 level, else 0.0."""
    levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    p = str(predicted).strip().upper()
    e = str(expected).strip().upper()
    
    # Normalize inputs in case they are different
    p = "CRITICAL" if "CRIT" in p else ("HIGH" if "HIGH" in p else ("MEDIUM" if "MED" in p else "LOW"))
    e = "CRITICAL" if "CRIT" in e else ("HIGH" if "HIGH" in e else ("MEDIUM" if "MED" in e else "LOW"))
    
    p_val = levels.get(p, 0)
    e_val = levels.get(e, 0)
    
    diff = abs(p_val - e_val)
    if diff == 0:
        return 1.0
    elif diff == 1:
        return 0.5
    else:
        return 0.0

def compute_schedule_f1(predicted: List[str], expected: List[str]) -> dict:
    """Compute Precision, Recall, and F1 for schedule mapping.

    Returns a dict so callers can surface each component separately.
    High precision + low recall  → model is conservative (misses schedules).
    Low precision + high recall  → model over-predicts (adds spurious schedules).
    """
    p_set = {str(s).strip().upper() for s in predicted if s}
    e_set = {str(s).strip().upper() for s in expected if s}

    if not p_set and not e_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not p_set or not e_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    intersection = p_set & e_set
    precision = len(intersection) / len(p_set)
    recall = len(intersection) / len(e_set)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}

def evaluate_case(pred: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, float]:
    """Compute all metrics for a single case.
    
    pred: predicted dict with:
        - tax_liability (float)
        - itr_form (str)
        - risk_level (str)
        - schedules (list[str])
        - blocked_claims (list[dict])
        - verified_claims (list[dict])
        - latency (float)
    gt: ground truth case dict
    """
    expected = gt.get("expected", {})
    
    tax_acc = compute_tax_accuracy(pred.get("tax_liability", 0.0), expected.get("tax_liability", 0.0))
    itr_acc = compute_itr_form_accuracy(pred.get("itr_form", ""), expected.get("itr_form", ""))
    risk_acc = compute_risk_accuracy(pred.get("risk_level", "LOW"), expected.get("risk_level", "LOW"))
    sched = compute_schedule_f1(pred.get("schedules", []), expected.get("schedules_required", []))
    sched_f1 = sched["f1"]
    sched_precision = sched["precision"]
    sched_recall = sched["recall"]
    
    # Hallucination check:
    # If the case is new regime and has deductions like 80C claimed, or if CriticAgent blocked claims
    hallucinated = 0.0
    if gt.get("input", {}).get("regime") == "new":
        # Check if 80C, 80D, HRA are in deductions
        deductions = pred.get("deductions", {})
        blocked_sects = {"80C", "80D", "HRA", "LTA", "24B", "80CCD_1B", "80TTA"}
        for sect in blocked_sects:
            if deductions.get(sect, 0.0) > 0:
                hallucinated = 1.0
    
    # Or if CriticAgent blocked any claims, count as hallucination rate (since it indicates a hallucination was caught)
    if len(pred.get("blocked_claims", [])) > 0:
        hallucinated = 1.0
        
    # Faithfulness Rate:
    # % of checked claims that are faithful
    total_claims = len(pred.get("verified_claims", [])) + len(pred.get("blocked_claims", []))
    faithfulness = 1.0
    if total_claims > 0:
        faithfulness = len(pred.get("verified_claims", [])) / total_claims
        
    return {
        "tax_accuracy": tax_acc,
        "itr_form_accuracy": itr_acc,
        "risk_accuracy": risk_acc,
        "schedule_precision": sched_precision,
        "schedule_recall": sched_recall,
        "schedule_f1": sched_f1,
        "hallucination_rate": hallucinated,
        "faithfulness_rate": faithfulness,
        "latency_sec": pred.get("latency", 0.0)
    }

def aggregate_metrics(results: List[Dict[str, float]]) -> Dict[str, float]:
    """Compute average metrics across a list of case results."""
    if not results:
        return {}
    
    count = len(results)
    totals = {}
    for res in results:
        for k, v in res.items():
            totals[k] = totals.get(k, 0.0) + v
            
    return {k: round(v / count, 4) for k, v in totals.items()}
