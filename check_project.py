"""
check_project.py — FinITR-AI v3 Full Diagnostic
Run from FinV3/ root: python check_project.py
Checks every component and tells you exactly what's working.
"""
import sys
import os
from pathlib import Path

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"
results = []

def check(label, fn):
    try:
        msg = fn()
        results.append((PASS, label, msg or ""))
        print(f"{PASS} {label}: {msg or 'OK'}")
    except Exception as e:
        results.append((FAIL, label, str(e)[:120]))
        print(f"{FAIL} {label}: {str(e)[:120]}")

print("\n" + "="*60)
print("  FinITR-AI v3 — Project Diagnostic")
print("="*60 + "\n")

# == 1. Python version ==
check("Python version",
    lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} {'OK' if sys.version_info >= (3,10) else 'need 3.10+'}")

# ── 2. Dependencies ──
def check_dep(pkg, import_name=None):
    import importlib
    mod = importlib.import_module(import_name or pkg)
    version = getattr(mod, '__version__', 'unknown')
    return f"v{version}"

check("scikit-learn",       lambda: check_dep("sklearn"))
check("sentence-transformers", lambda: check_dep("sentence_transformers"))
check("chromadb",           lambda: check_dep("chromadb"))
check("pdfplumber",         lambda: check_dep("pdfplumber"))
check("ollama",             lambda: check_dep("ollama"))
check("pandas",             lambda: check_dep("pandas"))
check("plotly",             lambda: check_dep("plotly"))
check("streamlit",          lambda: check_dep("streamlit"))
check("reportlab",          lambda: check_dep("reportlab"))
check("numpy",              lambda: check_dep("numpy"))
check("fastapi",            lambda: check_dep("fastapi"))

# ── 3. Ollama ──
def check_ollama():
    import ollama

    response = ollama.list()

    # Handle different ollama library versions
    raw_models = []
    if hasattr(response, 'get'):
        raw_models = response.get('models', [])
    elif hasattr(response, 'models'):
        raw_models = response.models
    else:
        raw_models = list(response) if response else []

    # Extract model name
    names = []
    for m in raw_models:
        name = None
        if isinstance(m, dict):
            name = m.get('name') or m.get('model') or str(m)
        elif hasattr(m, 'name'):
            name = m.name
        elif hasattr(m, 'model'):
            name = m.model
        else:
            name = str(m)
        if name:
            names.append(name)

    has_qwen = any('qwen2.5' in n.lower() for n in names)
    status = f"Models found: {names}"

    if not has_qwen:
        raise Exception(
            f"qwen2.5:7b not found. "
            f"Run in terminal: ollama pull qwen2.5:7b\n"
            f"Currently available: {names}"
        )
    return status

check("Ollama running", lambda: __import__('ollama').list() and "running")
check("qwen2.5:7b pulled", check_ollama)

# ── 4. Ollama inference ──
def check_llm_inference():
    import ollama

    # Find correct model name
    response = ollama.list()
    raw_models = getattr(response, 'models', None) or response.get('models', [])
    model_name = "qwen2.5:7b"
    for m in raw_models:
        n = getattr(m, 'name', None) or getattr(m, 'model', None) or m.get('name', '') or m.get('model', '')
        if 'qwen2.5' in str(n).lower():
            model_name = n
            break

    r = ollama.chat(
        model=model_name,
        messages=[{'role': 'user', 'content': 'Reply only with: {"status":"ok"}'}],
        options={'temperature': 0}
    )

    # Handle both dict and object response
    if isinstance(r, dict):
        content = r['message']['content']
    else:
        content = r.message.content

    if 'ok' in content.lower():
        return f"Model={model_name} | Response: {content[:40]}"
    raise Exception(f"Unexpected LLM response: {content[:80]}")

check("LLM inference (qwen2.5:7b)", check_llm_inference)

# ── 5. Training data ──
def check_training_data():
    import pandas as pd
    path = Path("data/training/transaction_labels_v2.csv")
    if not path.exists():
        raise Exception("Not found. Run: python scripts/generate_training_data.py")
    df = pd.read_csv(path)
    labels = df['label'].nunique()
    return f"{len(df)} rows, {labels} categories"

check("Transaction training data", check_training_data)

# ── 6. ML Models trained ──
def check_notice_model():
    pkl = Path("models/notice_predictor.pkl")
    metrics = Path("models/notice_predictor_metrics.json")
    if not pkl.exists():
        raise Exception("NOT TRAINED. Run: python -m models.notice_predictor --train")
    import json
    if metrics.exists():
        m = json.loads(metrics.read_text())
        auc = m.get('test_auc', 0)
        return f"Trained OK | AUC={auc:.4f}"
    return f"Trained OK (no metrics file)"

def check_classifier_model():
    pkl = Path("models/transaction_classifier_v2.pkl")
    metrics = Path("models/transaction_classifier_v2_metrics.json")
    if not pkl.exists():
        # Try old v1 path
        pkl_v1 = Path("models/transaction_classifier.pkl")
        if not pkl_v1.exists():
            raise Exception("NOT TRAINED. Run: python -m models.transaction_classifier_v2 --train")
        return "v1 trained (consider retraining with v2)"
    import json
    if metrics.exists():
        m = json.loads(metrics.read_text())
        acc = m.get('test_accuracy', 0)
        return f"Trained OK | Accuracy={acc:.4f}"
    return "Trained OK (no metrics file)"

check("Notice Predictor model (.pkl)", check_notice_model)
check("Transaction Classifier model (.pkl)", check_classifier_model)

# ── 7. Models load and predict ──
def check_notice_inference():
    from models.notice_predictor import predict
    fake_report = {
        'risk_score': {'total_score': 75, 'undeclared_amount': 200000},
        'anomalies': [{'flag_type': 'CRYPTO_TRANSACTION'}, {'flag_type': 'FREELANCE_INCOME'}],
        'reconciliation': {'ledger': [
            {'match_status': 'ais_only', 'itr_schedule': 'Schedule VDA', 'delta': 50000},
        ]}
    }
    result = predict(fake_report)
    prob = result['notice_probability']
    return f"Probability={prob:.2%} | Tier={result['risk_tier']}"

def check_classifier_inference():
    try:
        from models.transaction_classifier_v2 import RealWorldTransactionClassifier
        clf = RealWorldTransactionClassifier()
        clf.load()
    except:
        from models.transaction_classifier import TransactionClassifier
        clf = TransactionClassifier()
        clf.load()
    result = clf.classify("UPI/DR/WAZIRX/CRYPTO PURCHASE")
    label = result['label']
    conf = result['confidence']
    if label not in ('CRYPTO_TRANSACTION', 'crypto_vda'):
        raise Exception(f"Wrong label: {label} (expected CRYPTO/crypto_vda)")
    return f"Label={label} | Conf={conf:.3f}"

check("Notice Predictor inference", check_notice_inference)
check("Transaction Classifier inference", check_classifier_inference)

# ── 8. Parsers ──
def check_ais_parser():
    from parsers.ais_parser import AISParser
    path = "data/synthetic/sample_ais.json"
    if not Path(path).exists():
        path = "data/synthetic/vikram_ais.json"
    result = AISParser().parse(path)
    entries = len(result.get('sft_entries', []))
    return f"{entries} SFT entries parsed"

def check_csv_parser():
    from parsers.csv_parser import CSVParser
    path = "data/synthetic/sample_bank_statement.csv"
    if not Path(path).exists():
        path = "data/synthetic/vikram_bank_statement.csv"
    result = CSVParser().parse(path)
    return f"{len(result)} transactions parsed"

def check_form16_parser():
    from parsers.form16_parser import Form16Parser
    path = "data/synthetic/sample_form16.json"
    if not Path(path).exists():
        path = "data/synthetic/vikram_form16.json"
    result = Form16Parser().parse(path)
    salary = result.get('gross_salary', 0)
    return f"Gross salary: Rs. {salary:,.0f}"

check("AIS Parser", check_ais_parser)
check("CSV Bank Statement Parser", check_csv_parser)
check("Form 16 JSON Parser", check_form16_parser)

# == 9. PDF Parser ==
def check_pdf_parser():
    from parsers.form16_pdf_parser import Form16PDFParser
    # Just check it imports correctly
    p = Form16PDFParser()
    pdfs = list(Path("data").rglob("*.pdf"))
    if not pdfs:
        return "Imported OK | No test PDF yet (will generate one)"
    result = p.parse(pdfs[0])
    return f"Parsed {pdfs[0].name} | Salary: Rs. {result.get('gross_salary',0):,.0f}"

check("Form 16 PDF Parser (import)", check_pdf_parser)

# ── 10. Schedules ──
def check_schedule_cg():
    from schedules.schedule_cg import ScheduleCGBuilder
    s = ScheduleCGBuilder()
    return "Imported OK"

def check_schedule_vda():
    from schedules.schedule_vda import ScheduleVDABuilder
    s = ScheduleVDABuilder()
    return "Imported OK"

check("Schedule CG Builder", check_schedule_cg)
check("Schedule VDA Builder", check_schedule_vda)

# ── 11. Agents ──
def check_agents():
    from agents.orchestrator import Orchestrator
    from agents.auditor_agent import AuditorAgent
    from agents.optimizer_agent import OptimizerAgent
    from agents.compliance_agent import ComplianceAgent
    from agents.critic_agent import CriticAgent
    return "All 5 agents import OK"

check("All agents import", check_agents)

# ── 12. Orchestrator quick run ──
def check_orchestrator():
    from agents.orchestrator import Orchestrator
    orch = Orchestrator(verbose=False)
    # Run with minimal data (no files)
    report = orch.run(gross_income=1500000)
    keys = list(report.keys())
    return f"Runs OK | Keys: {keys[:4]}"

check("Orchestrator runs (minimal)", check_orchestrator)

# ── 13. Synthetic data files ──
def check_synthetic_files():
    files = [
        "data/synthetic/sample_bank_statement.csv",
        "data/synthetic/sample_ais.json",
        "data/synthetic/sample_form16.json",
        "data/synthetic/vikram_bank_statement.csv",
        "data/synthetic/vikram_ais.json",
        "data/synthetic/vikram_form16.json",
    ]
    missing = [f for f in files if not Path(f).exists()]
    found = len(files) - len(missing)
    if missing:
        raise Exception(f"Missing: {missing}")
    return f"All {found} synthetic files found"

check("Synthetic test data files", check_synthetic_files)

# ── 14. Benchmark cases ──
def check_benchmark():
    cases = list(Path("benchmarks/indian_tax_bench/cases").glob("tc_*.json"))
    if len(cases) < 10:
        raise Exception(f"Only {len(cases)} cases found (expected 100)")
    return f"{len(cases)} benchmark cases"

check("IndianTaxBench cases", check_benchmark)

# ── Summary ──
print("\n" + "="*60)
print("  SUMMARY")
print("="*60)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
print(f"  {PASS} Passed: {passed}")
print(f"  {FAIL} Failed: {failed}")

if failed > 0:
    print(f"\n  Fix these first:")
    for icon, label, msg in results:
        if icon == FAIL:
            print(f"  {FAIL} {label}")
            print(f"      -> {msg}")

print()
if failed == 0:
    print("  [SUCCESS] Project fully operational! Run the full pipeline next.")
    print("  python -m agents.orchestrator --bank data/synthetic/vikram_bank_statement.csv \\")
    print("    --ais data/synthetic/vikram_ais.json \\")
    print("    --form16 data/synthetic/vikram_form16.json \\")
    print("    --output outputs/vikram_test.json")
else:
    print("  Fix the ❌ items above then re-run this script.")