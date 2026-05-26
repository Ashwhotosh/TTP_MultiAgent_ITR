"""Test Task 1.7: AuditorAgent"""
from parsers.csv_parser import CSVParser
from parsers.ais_parser import AISParser
from parsers.form16_parser import Form16Parser
from agents.base import AgentContext
from agents.auditor_agent import AuditorAgent

# Parse documents
bank_txns = CSVParser().parse('data/synthetic/sample_bank_statement.csv')
ais_data = AISParser().parse('data/synthetic/sample_ais.json')
f16_data = Form16Parser().parse('data/synthetic/sample_form16.json')

# Build context
ctx = AgentContext(
    bank_transactions=bank_txns,
    ais_data=ais_data,
    form16_data=f16_data,
    gross_income=f16_data['gross_salary'],
    basic_salary=f16_data['basic_salary'],
)

# Run AuditorAgent
auditor = AuditorAgent()
result = auditor.run(ctx)

print(f"Status: {result.status}")
print(f"Reconciliation items: {len(ctx.reconciliation.get('ledger', []))}")
print(f"Anomalies: {len(ctx.anomalies)}")
print(f"Risk score: {ctx.risk_score.get('total_score', 'N/A')}")
print(f"Risk level: {ctx.risk_score.get('risk_level', 'N/A')}")
print(f"Interview questions: {len(ctx.interview_questions)}")

# Show ledger
print("\n--- Unified Ledger ---")
for item in ctx.reconciliation.get('ledger', []):
    print(f"  {item['match_status']:10s} | {item['itr_schedule']:20s} | "
          f"F16={item['amount_form16']:>10,.0f} | AIS={item['amount_ais']:>10,.0f} | "
          f"Bank={item['amount_bank']:>10,.0f} | {item['item'][:40]}")

# Show anomalies
print("\n--- Anomalies ---")
for a in ctx.anomalies:
    print(f"  {a['flag_type']:25s} | Rs {a['amount']:>10,.0f} | AIS={a['in_ais']} | {a['description'][:40]}")

# Show risk breakdown
print(f"\n--- Risk Score: {ctx.risk_score['total_score']} ({ctx.risk_score['risk_level']}) ---")
for b in ctx.risk_score.get('breakdown', []):
    print(f"  +{b['weight']:2d} | {b['item'][:60]}")

# Assertions
assert result.status == "success"
assert len(ctx.reconciliation.get('ledger', [])) > 0
assert len(ctx.anomalies) > 0
assert ctx.risk_score['total_score'] >= 50, f"Risk should be >= 50, got {ctx.risk_score['total_score']}"
assert ctx.risk_score['risk_level'] in ('HIGH', 'CRITICAL')
assert len(ctx.interview_questions) > 0

print("\nAuditorAgent OK - PASS")
