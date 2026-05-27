# trainfix_plan.md
# Fix Ollama API Error + Pull Model + Run All Training
# For AI coding agents: implement every task in order, run verification after each.

## Root Cause
The error `❌ qwen2.5:7b pulled → 'name'` means the ollama Python library
returned a response where models have a different key structure than expected.
Newer versions of the ollama library use `m['model']` or return Model objects
instead of plain dicts. Also, qwen2.5:7b has not been pulled yet.

Two things to fix:
1. Pull qwen2.5:7b via terminal command
2. Fix check_project.py to handle both old and new ollama library API formats

---

## Task 1: Pull qwen2.5:7b (Terminal — run manually, not via code)

Run this in your terminal and wait for it to finish (~4.7GB download):

```
ollama pull qwen2.5:7b
```

While it downloads, proceed with Tasks 2 and 3 (code fixes).
Verify after download:
```
ollama list
```
Expected output should include a line with `qwen2.5:7b`.

---

## Task 2: Fix check_project.py — ollama API compatibility

**File to edit**: `check_project.py`

Find the `check_ollama` function (around line 55):

```python
def check_ollama():
    import ollama
    models = ollama.list()
    names = [m['name'] for m in models.get('models', [])]
    has_qwen = any('qwen2.5:7b' in n for n in names)
    has_phi3 = any('phi3' in n for n in names)
    status = f"Models: {names}"
    if not has_qwen:
        raise Exception(f"qwen2.5:7b not found. Run: ollama pull qwen2.5:7b. Found: {names}")
    return status
```

Replace it with this version that handles all ollama library versions:

```python
def check_ollama():
    import ollama

    response = ollama.list()

    # Handle different ollama library versions
    # v0.1.x: response is dict with 'models' key containing list of dicts with 'name'
    # v0.2.x+: response is object with 'models' attribute containing Model objects
    # v0.3.x+: models have 'model' field instead of 'name'

    raw_models = []

    # Try dict-style access first
    if hasattr(response, 'get'):
        raw_models = response.get('models', [])
    # Try attribute access (newer versions return objects)
    elif hasattr(response, 'models'):
        raw_models = response.models
    else:
        raw_models = list(response) if response else []

    # Extract model name from whatever format we got
    names = []
    for m in raw_models:
        name = None
        if isinstance(m, dict):
            # Try 'name' first (old API), then 'model' (new API)
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
    has_phi3 = any('phi3' in n.lower() for n in names)

    status = f"Models found: {names}"

    if not has_qwen:
        raise Exception(
            f"qwen2.5:7b not found. "
            f"Run in terminal: ollama pull qwen2.5:7b\n"
            f"Currently available: {names}"
        )
    return status
```

Also find `check_llm_inference` function and update the ollama.chat call to
handle both old and new API styles:

```python
def check_llm_inference():
    import ollama

    # Find correct model name (handle :latest suffix)
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
```

**Verification**:
```bash
python -c "import ollama; r = ollama.list(); print(type(r)); print(r)"
```
This shows you the raw response format so you can confirm the fix works.

---

## Task 3: Fix ollama calls in agents and tools project-wide

The same ollama API version mismatch may exist in other project files.
Search for all ollama.chat() calls and ensure they handle both response formats.

**Files to check**:
```bash
grep -r "ollama" . --include="*.py" -l
```

For each file that uses ollama, find any code that does:
```python
response['message']['content']   # dict-style (old)
```

And replace with a helper function. Create this utility file:

**File to create**: `tools/ollama_client.py`

```python
"""
ollama_client.py — Thin wrapper around ollama library.
Handles API differences across ollama library versions (0.1.x / 0.2.x / 0.3.x+).
Import this instead of calling ollama directly.
"""
from __future__ import annotations
import os


def get_model_name() -> str:
    """Return the configured Ollama model name."""
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def chat(prompt: str, system: str | None = None,
         model: str | None = None, temperature: float = 0.3,
         json_mode: bool = False) -> str:
    """
    Send a chat message to Ollama. Returns response text as string.
    Handles all ollama library version differences.

    Args:
        prompt: User message
        system: Optional system message
        model: Model name (defaults to OLLAMA_MODEL env var or qwen2.5:7b)
        temperature: Sampling temperature
        json_mode: If True, adds JSON instruction to system prompt

    Returns:
        Response text as plain string
    """
    import ollama as _ollama

    model = model or get_model_name()

    messages = []
    if system:
        if json_mode:
            system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No explanation, no markdown."
        messages.append({'role': 'system', 'content': system})
    elif json_mode:
        messages.append({
            'role': 'system',
            'content': 'Respond ONLY with valid JSON. No explanation, no markdown backticks.'
        })

    messages.append({'role': 'user', 'content': prompt})

    try:
        response = _ollama.chat(
            model=model,
            messages=messages,
            options={'temperature': temperature}
        )

        # Handle dict response (older library)
        if isinstance(response, dict):
            return response['message']['content'].strip()

        # Handle object response (newer library)
        if hasattr(response, 'message'):
            msg = response.message
            if isinstance(msg, dict):
                return msg['content'].strip()
            return msg.content.strip()

        return str(response).strip()

    except _ollama.ResponseError as e:
        raise RuntimeError(f"Ollama error (model={model}): {e}")
    except Exception as e:
        if "not found" in str(e).lower() or "no such model" in str(e).lower():
            raise RuntimeError(
                f"Model '{model}' not found. Run: ollama pull {model}"
            )
        raise


def list_models() -> list[str]:
    """Return list of available model names."""
    import ollama as _ollama
    try:
        response = _ollama.list()
        raw = getattr(response, 'models', None)
        if raw is None and hasattr(response, 'get'):
            raw = response.get('models', [])
        if not raw:
            return []

        names = []
        for m in raw:
            name = None
            if isinstance(m, dict):
                name = m.get('name') or m.get('model')
            else:
                name = getattr(m, 'name', None) or getattr(m, 'model', None)
            if name:
                names.append(str(name))
        return names
    except Exception:
        return []


def is_available(model: str | None = None) -> bool:
    """Check if a specific model (or default) is available."""
    target = model or get_model_name()
    return any(target in m for m in list_models())
```

Now update any agent files that call ollama directly. Find them:
```bash
grep -r "ollama.chat\|import ollama" . --include="*.py" -l | grep -v "ollama_client\|check_project\|train_all"
```

For each file found, replace direct ollama calls with:
```python
from tools.ollama_client import chat as llm_chat

# Instead of:
# response = ollama.chat(model="qwen2.5:7b", messages=[...])
# content = response['message']['content']

# Use:
content = llm_chat(prompt=user_message, system=system_message)
```

---

## Task 4: Fix orchestrator model name

**File**: `agents/orchestrator.py`

Find the `__init__` method. Change the default model:

```python
# Old (may have phi3:mini or wrong default)
def __init__(self, ollama_model: str = "phi3:mini", ...):

# New
import os
def __init__(self, ollama_model: str = None, ...):
    if ollama_model is None:
        from tools.ollama_client import get_model_name
        ollama_model = get_model_name()
    self.ollama_model = ollama_model
    ...
```

Find any other place in orchestrator.py that hardcodes `phi3:mini` and replace
with `self.ollama_model`.

---

## Task 5: Run training (after qwen2.5:7b finishes downloading)

Confirm model is pulled first:
```bash
ollama list
```
Must show `qwen2.5:7b` in the list before proceeding.

Then run training:
```bash
python train_all.py
```

Expected output sequence:
```
===========================================================
  Step 1/3: Generating transaction training data
===========================================================
Generated 400 labeled transactions → data/training/transaction_labels_v2.csv

===========================================================
  Step 2/3: Training Notice Predictor (Gradient Boosting)
===========================================================
[NoticePredictor] Loaded 100 cases
[NoticePredictor] Test AUC: 0.8x
✅ Done: Step 2/3

===========================================================
  Step 3/3: Training Transaction Classifier (Multilingual kNN)
===========================================================
[Classifier] Loading sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2...
  (First run: downloads ~450MB model — takes 3-5 min on good connection)
[Classifier] Test Accuracy: 0.9x
✅ Done: Step 3/3

✅ All models trained successfully!
```

If Step 3 fails with download timeout, run this first then retry:
```bash
python -c "
from sentence_transformers import SentenceTransformer
print('Downloading multilingual model...')
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
print('Done')
"
python train_all.py
```

---

## Task 6: Verify everything after training

```bash
python check_project.py
```

All 14+ items must show ✅. Specific ones to confirm:

| Check | Expected |
|-------|----------|
| qwen2.5:7b pulled | ✅ Models found: ['qwen2.5:7b', 'phi3:mini'] |
| LLM inference | ✅ Response: {"status":"ok"} |
| Notice Predictor .pkl | ✅ Trained ✓ \| AUC=0.8x+ |
| Transaction Classifier .pkl | ✅ Trained ✓ \| Accuracy=0.9x+ |
| All agents import | ✅ All 5 agents import OK |
| Orchestrator runs | ✅ Runs OK |

If any item still fails, check the exact error message and fix before moving on.

---

## Task 7: Run classifier demo to verify real-world handling

```bash
python -m models.transaction_classifier_v2 --demo
```

Verify these specific cases are correct:

| Input | Expected label | Expected tax_relevance |
|-------|---------------|----------------------|
| WDL TFR UPI/DR/.../ZOMATO/... | REGULAR_EXPENSE | none |
| UPI/DR/AMAN JUICEWALA/... | REGULAR_EXPENSE | none |
| NEFT-SALARY-INFOSYS... | SALARY_INCOME | salary |
| UPI/DR/MUDREX/CRYPTO... | CRYPTO_TRANSACTION | VDA |
| NEFT/CR/UPWORK GLOBAL INC... | FREELANCE_INCOME | foreign_remittance |
| ACH/DR/HDFC HOUSING LOAN EMI | LOAN_EMI | deduction_24b_80C |

If Hinglish vendors like "AMAN JUICEWALA" are classified as CRYPTO or FREELANCE,
the training data generation failed. Fix:
```bash
# Regenerate and retrain
python scripts/generate_training_data.py
python -m models.transaction_classifier_v2 --train
```

---

## Task 8: Test full pipeline with PDF Form 16

Generate test PDFs first (if not already done):
```bash
python scripts/generate_test_form16_pdf.py
```

Run Arjun full pipeline:
```bash
python -m agents.orchestrator \
    --bank data/synthetic/sample_bank_statement.csv \
    --ais  data/synthetic/sample_ais.json \
    --form16 data/real/test_form16_arjun.pdf \
    --output outputs/arjun_full_test.json
```

Run Vikram full pipeline (harder case — 180 transactions):
```bash
python -m agents.orchestrator \
    --bank data/synthetic/vikram_bank_statement.csv \
    --ais  data/synthetic/vikram_ais.json \
    --form16 data/real/test_form16_vikram.pdf \
    --output outputs/vikram_full_test.json
```

Verify outputs:
```bash
python -c "
import json

print('=== ARJUN TEST ===')
r = json.load(open('outputs/arjun_full_test.json'))
p = r.get('notice_prediction') or {}
print(f'  Risk Level:     {r.get(\"risk_score\", {}).get(\"risk_level\", \"N/A\")}')
print(f'  Notice Prob:    {p.get(\"notice_probability\", \"N/A\")}')
print(f'  Notice Tier:    {p.get(\"risk_tier\", \"N/A\")}')
print(f'  Anomalies:      {len(r.get(\"anomalies\", []))}')
print(f'  Schedules:      {len(r.get(\"schedule_mapping\", []))}')
print(f'  Iterations:     {r.get(\"iterations\", 0)}')

print()
print('=== VIKRAM TEST ===')
r = json.load(open('outputs/vikram_full_test.json'))
p = r.get('notice_prediction') or {}
print(f'  Risk Level:     {r.get(\"risk_score\", {}).get(\"risk_level\", \"N/A\")}')
print(f'  Notice Prob:    {p.get(\"notice_probability\", \"N/A\")}')
print(f'  Notice Tier:    {p.get(\"risk_tier\", \"N/A\")}')
print(f'  Anomalies:      {len(r.get(\"anomalies\", []))}')
print(f'  Schedules:      {len(r.get(\"schedule_mapping\", []))}')
print(f'  Transactions:   {r.get(\"documents\", {}).get(\"bank_transactions\", 0)}')
"
```

Expected results:

| Metric | Arjun | Vikram |
|--------|-------|--------|
| Risk Level | HIGH or CRITICAL | CRITICAL |
| Notice Probability | > 0.55 | > 0.75 |
| Anomalies flagged | ≥ 3 | ≥ 5 |
| Iterations | ≥ 1 | ≥ 1 |

---

## Task 9: Launch Streamlit and verify UI

```bash
streamlit run frontend/app.py
```

In the browser:
1. Upload `data/real/test_form16_vikram.pdf` in the sidebar
2. Upload `data/synthetic/vikram_ais.json`
3. Upload `data/synthetic/vikram_bank_statement.csv`
4. Click "Run Pipeline"
5. Verify Dashboard tab shows:
   - Notice Probability metric card (5th card)
   - ML Notice Prediction Analysis expander with feature importance chart
   - Risk gauge showing HIGH or CRITICAL
   - Reconciliation table with color-coded rows

---

## Acceptance Criteria — Project is ready when:

- [ ] `python check_project.py` → 0 failures, all green
- [ ] `ollama list` shows `qwen2.5:7b`
- [ ] `models/notice_predictor.pkl` exists, AUC ≥ 0.80
- [ ] `models/transaction_classifier_v2.pkl` exists, Accuracy ≥ 0.88
- [ ] Demo shows AMAN JUICEWALA → REGULAR_EXPENSE
- [ ] Demo shows WAZIRX → CRYPTO_TRANSACTION
- [ ] Vikram pipeline produces notice_probability > 0.75
- [ ] Arjun pipeline produces notice_probability > 0.50
- [ ] Streamlit dashboard shows notice prediction with feature chart
- [ ] Both PDF Form 16 files generated and parseable

---

## Common Errors and Fixes

**Error**: `ollama._types.ResponseError: model 'qwen2.5:7b' not found`
**Fix**: `ollama pull qwen2.5:7b` — model not downloaded yet

**Error**: `ModuleNotFoundError: No module named 'sklearn'`
**Fix**: `pip install scikit-learn`

**Error**: `ModuleNotFoundError: No module named 'sentence_transformers'`
**Fix**: `pip install sentence-transformers`

**Error**: Training data CSV not found
**Fix**: `python scripts/generate_training_data.py`

**Error**: `KeyError: 'name'` in ollama calls anywhere
**Fix**: The ollama_client.py wrapper (Task 3) fixes this everywhere.
Ensure all agent files use `from tools.ollama_client import chat as llm_chat`
instead of calling `ollama.chat()` directly.

**Error**: `AttributeError: 'ListResponse' object has no attribute 'get'`
**Fix**: Same as above — ollama library version mismatch. Task 2 and 3 fix this.

**Error**: Transaction classifier accuracy < 0.80
**Fix**: The multilingual model may not have downloaded fully.
Delete `models/transaction_classifier_v2.pkl` and re-run training.

**Error**: PDF parser returns all zeros for salary
**Fix**: The test PDFs have standard CBDT formatting. If your regex isn't matching,
run `python -c "import pdfplumber; [print(p.extract_text()) for p in pdfplumber.open('data/real/test_form16_arjun.pdf').pages]"`
and adjust the regex patterns in `parsers/form16_pdf_parser.py` PATTERNS list
to match the actual label text in the output.
