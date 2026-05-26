"""
run_final_checks.py — Consolidated final checks for ITR project.
"""
import json
from pathlib import Path

checks = {
    'Deduction Gap Analyzer':        Path('tools/deduction_gap_analyzer.py').exists(),
    'Streamlit deduction_gap.py':    Path('frontend/components/deduction_gap.py').exists(),
    'PDF form16 generator script':   Path('scripts/generate_test_form16_pdf.py').exists(),
    'Arjun Form 16 PDF':             Path('data/real/test_form16_arjun.pdf').exists(),
    'Vikram Form 16 PDF':            Path('data/real/test_form16_vikram.pdf').exists(),
    'Vikram output has gaps': (
        lambda: len(json.loads(
            Path('outputs/vikram_gap_test.json').read_text()
        ).get('deduction_gaps',{}).get('gaps',[])) > 0
        if Path('outputs/vikram_gap_test.json').exists() else False
    )(),
    'Holdout cases (>=20)': (
        len(list(Path('benchmarks/indian_tax_bench/holdout').glob('*.json'))) >= 20
        if Path('benchmarks/indian_tax_bench/holdout').exists() else False
    ),
    'Ablation results saved':        Path('evaluation/results/ablation_results.json').exists(),
    'Comparison chart generated':    Path('evaluation/results/chart_model_comparison.png').exists(),
    'Ablation chart generated':      Path('evaluation/results/chart_ablation.png').exists(),
    'Notice predictor chart':        Path('evaluation/results/chart_notice_predictor.png').exists(),
    'Notice predictor pkl':          Path('models/notice_predictor.pkl').exists(),
    'Transaction classifier pkl':    Path('models/transaction_classifier_v2.pkl').exists(),
}

print('=== Final Verification ===')
passed = failed = 0
for name, ok in checks.items():
    print(f'{"OK" if ok else "MISS"}  {name}')
    if ok: passed += 1
    else:  failed += 1

print(f'\n{passed}/{passed+failed} checks passed')
if failed == 0:
    print('Project is A-grade ready. Write the report.')
else:
    print('Complete the MISS items above before writing the report.')
