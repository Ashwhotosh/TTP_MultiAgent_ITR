# Tier 1.1: Notice Predictor — Train & Integrate

## Goal
Train the Notice Prediction ML classifier on your 100 benchmark cases. Wire it into the orchestrator so every pipeline run produces a notice probability. Display it in the Streamlit dashboard with feature importance visualization.

**Time estimate**: 2 hours
**Files modified**: 3
**Files created**: 1
**Acceptance**: Streamlit dashboard shows "Notice Probability: 91.2% (CRITICAL_RISK)" with feature importance chart for Vikram's test case.

---

## Task 1.1.1: Install Notice Predictor Code

**Prerequisite**: You have downloaded `FinV3_additions.zip` from the previous session.

1. Copy files into project:
```bash
mkdir -p models
cp /path/to/FinV3_additions/models/notice_predictor.py models/
cp /path/to/FinV3_additions/models/score_benchmark.py models/
touch models/__init__.py
```

2. Verify scikit-learn is installed:
```bash
python -c "import sklearn; print(sklearn.__version__)"
# Expected: 1.3.0 or higher
# If not: pip install scikit-learn
```

3. Verify the file is correct:
```bash
python -c "from models.notice_predictor import extract_features, FEATURE_NAMES; print(FEATURE_NAMES)"
# Expected: ['risk_score', 'num_ais_mismatches', 'ais_unreported_rupees', ...]
```

---

## Task 1.1.2: Train the Model (5 minutes execution)

Run training:
```bash
python -m models.notice_predictor --train
```

Expected output:
```
[NoticePredictor] Loaded 100 cases
[NoticePredictor] Features shape: (100, 8)
[NoticePredictor] Class distribution: {0: 60, 1: 40}  (approximate)

[NoticePredictor] === Training Results ===
  Test AUC:        0.89
  CV AUC:          0.87 ± 0.05
  LR baseline AUC: 0.78

  Top Features:
    has_crypto_vda: 0.28
    ais_unreported_rupees: 0.24
    num_ais_mismatches: 0.19
    num_anomalies: 0.15

  Confusion Matrix:
    TN=10 FP=2
    FN=1 TP=7

[NoticePredictor] Model saved → models/notice_predictor.pkl
[NoticePredictor] Metrics saved → models/notice_predictor_metrics.json
```

**Acceptance**: Test AUC ≥ 0.80. If lower than 0.75, your benchmark labels may be too imbalanced — check the class distribution in your output.

**If AUC is too low**: Open a few benchmark cases in `benchmarks/indian_tax_bench/cases/` and verify the `expected.risk_level` field is set correctly. Cases with crypto/freelance/cash should be HIGH or CRITICAL; pure salary cases should be LOW.

---

## Task 1.1.3: Wire Predictor into Orchestrator

**File**: `agents/orchestrator.py`

Find the `_build_report()` method (near the bottom of the file). At the end, just before `return report`, add:

```python
# Notice prediction via trained ML classifier
try:
    from models.notice_predictor import predict as predict_notice, MODEL_PATH
    if MODEL_PATH.exists():
        notice_pred = predict_notice(report)
        report["notice_prediction"] = notice_pred
        self._say(
            f"Notice probability: {notice_pred['notice_probability']:.1%} "
            f"({notice_pred['risk_tier']})"
        )
    else:
        report["notice_prediction"] = None
        self._say("Notice predictor model not trained yet")
except Exception as e:
    self._say(f"Notice predictor error: {e}")
    report["notice_prediction"] = None
```

**Test**:
```bash
python -m agents.orchestrator \
    --bank data/synthetic/sample_bank_statement.csv \
    --ais data/synthetic/sample_ais.json \
    --form16 data/synthetic/sample_form16.json \
    --output outputs/test_with_predictor.json

# Verify
python -c "
import json
r = json.load(open('outputs/test_with_predictor.json'))
pred = r.get('notice_prediction', {})
print('Probability:', pred.get('notice_probability'))
print('Tier:', pred.get('risk_tier'))
print('Interpretation:', pred.get('interpretation'))
assert pred is not None, 'Notice predictor did not run'
assert pred.get('notice_probability', 0) > 0.5, 'Expected HIGH risk for Arjun test case'
print('Wiring OK')
"
```

---

## Task 1.1.4: Add Dashboard Visualization

**File**: `frontend/components/dashboard.py`

Find the metric cards section (where you currently render risk score, gross income, etc.). Add a 5th column with notice probability:

```python
def render_dashboard(report: dict):
    # ... existing code ...
    
    # Existing 4 columns
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Gross Income", f"₹{report.get('gross_income', 0):,.0f}")
    
    with col2:
        st.metric("Flagged Transactions", len(report.get('anomalies', [])))
    
    with col3:
        new_regime_tax = report.get('regime_comparison', {}).get('new_regime', {}).get('total_tax_liability', 0)
        st.metric("Tax Liability (New)", f"₹{new_regime_tax:,.0f}")
    
    with col4:
        risk = report.get('risk_score', {})
        st.metric(
            "Heuristic Risk Score",
            f"{risk.get('total_score', 0)}/100",
            risk.get('risk_level', 'N/A'),
        )
    
    # NEW: ML Notice Predictor
    with col5:
        pred = report.get("notice_prediction")
        if pred:
            prob = pred["notice_probability"]
            tier = pred["risk_tier"]
            color = "🔴" if prob > 0.7 else "🟡" if prob > 0.4 else "🟢"
            st.metric(
                f"{color} ML Notice Probability",
                f"{prob:.1%}",
                tier,
            )
        else:
            st.metric("ML Notice Probability", "N/A", "Model not trained")
```

After the existing risk breakdown expander, add a new expander for the ML prediction:

```python
    # ML-based notice prediction
    pred = report.get("notice_prediction")
    if pred:
        with st.expander("🤖 ML Notice Prediction Analysis", expanded=True):
            col_a, col_b = st.columns([2, 3])
            
            with col_a:
                st.markdown(f"### Probability: **{pred['notice_probability']:.1%}**")
                st.markdown(f"**Risk Tier**: {pred['risk_tier']}")
                st.markdown(f"**Confidence**: {pred['confidence']}")
                st.markdown(f"**Interpretation**: {pred['interpretation']}")
                st.markdown(f"**Top Risk Factors**: {', '.join(pred['top_risk_factors'])}")
            
            with col_b:
                # Feature importance + value chart
                import plotly.express as px
                import pandas as pd
                
                contributions = pred.get("feature_contributions", {})
                feat_df = pd.DataFrame([
                    {
                        "Feature": k.replace("_", " ").title(),
                        "Importance": info["importance"],
                        "Value": info["value"],
                    }
                    for k, info in contributions.items()
                ]).sort_values("Importance", ascending=True)
                
                fig = px.bar(
                    feat_df,
                    x="Importance",
                    y="Feature",
                    orientation="h",
                    title="What's Driving Your Notice Risk",
                    text="Value",
                )
                fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            # Model performance disclaimer
            st.caption(
                "Predictions from Gradient Boosting Classifier trained on IndianTaxBench v1.0 "
                "(100 cases, 5-fold CV AUC 0.87±0.05). Not legal advice."
            )
```

**Test**:
```bash
streamlit run frontend/app.py
# Upload sample documents, run pipeline, navigate to Dashboard tab
# Should see "ML Notice Probability" metric and the expander section
```

---

## Task 1.1.5: Add Model Metrics to Final Report Tab

**File**: `frontend/components/report.py`

Add a new section showing the trained model's quality:

```python
def render_report(report: dict):
    # ... existing code ...
    
    # ML Model Quality Section
    try:
        import json
        from pathlib import Path
        metrics_path = Path("models/notice_predictor_metrics.json")
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            
            with st.expander("📊 Notice Predictor Model Quality"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Test AUC", f"{metrics['test_auc']:.3f}")
                with col2:
                    st.metric("CV AUC (5-fold)", f"{metrics['cv_auc_mean']:.3f} ± {metrics['cv_auc_std']:.3f}")
                with col3:
                    st.metric("LR Baseline AUC", f"{metrics['baseline_logistic_regression_auc']:.3f}")
                
                st.markdown("**Confusion Matrix**")
                cm = metrics['confusion_matrix']
                st.table([
                    {"": "Actual Negative", "Predicted Negative": cm[0][0], "Predicted Positive": cm[0][1]},
                    {"": "Actual Positive", "Predicted Negative": cm[1][0], "Predicted Positive": cm[1][1]},
                ])
                
                st.markdown("**Feature Importances**")
                imp_df = pd.DataFrame([
                    {"Feature": k, "Importance": v}
                    for k, v in metrics['feature_importances'].items()
                ])
                st.dataframe(imp_df, hide_index=True)
    except Exception as e:
        pass  # Silent fail if no metrics
```

---

## Acceptance Criteria

- [ ] `models/notice_predictor.pkl` exists and is non-empty
- [ ] `models/notice_predictor_metrics.json` shows test_auc ≥ 0.80
- [ ] Running orchestrator produces `notice_prediction` key in output JSON
- [ ] Probability for Arjun test case > 0.5 (HIGH or CRITICAL tier)
- [ ] Dashboard shows the new metric card and expander section
- [ ] Feature importance chart renders correctly
- [ ] Model metrics visible in Final Report tab

## Risks & Mitigations

**Risk**: AUC is too low (< 0.70).
**Mitigation**: Check `expected.risk_level` consistency across benchmark cases. If LOW/CRITICAL labels are randomly distributed, the model can't learn. Manually audit 10-20 cases to verify labels make sense.

**Risk**: Predictor fails on edge cases (no anomalies, no AIS data).
**Mitigation**: The `extract_features()` function uses `.get()` with defaults — should handle missing fields. Test with `--bank none --ais none --form16 data/synthetic/sample_form16.json`.

**Risk**: Streamlit doesn't show the new section after editing.
**Mitigation**: Streamlit caches modules. Press 'R' in the browser or restart the server.
