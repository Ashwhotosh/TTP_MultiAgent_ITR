"""End-to-end test for Week 1"""
import json
import os
import subprocess

print("Running Orchestrator...")
cmd = [
    ".\\venv\\Scripts\\python.exe", "-m", "agents.orchestrator",
    "--bank", "data/synthetic/sample_bank_statement.csv",
    "--ais", "data/synthetic/sample_ais.json",
    "--form16", "data/synthetic/sample_form16.json",
    "--output", "outputs/week1_test.json"
]

os.makedirs("outputs", exist_ok=True)
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print("Orchestrator failed!")
    print(result.stdout)
    print(result.stderr)
    exit(1)

print("Orchestrator finished successfully. Verifying output...")

r = json.load(open('outputs/week1_test.json'))
print(f"Reconciliation items: {len(r.get('reconciliation', {}).get('ledger', []))}")
print(f"Anomalies: {len(r.get('anomalies', []))}")
print(f"Risk score: {r.get('risk_score', {}).get('total_score', 'N/A')}")
print(f"Risk level: {r.get('risk_score', {}).get('risk_level', 'N/A')}")

# Expected: risk_score should be HIGH because of crypto, freelance, and FD interest not in Form16
assert r.get("risk_score", {}).get("risk_level") in ("HIGH", "CRITICAL")
print("\nEnd-to-end Week 1 test OK - PASS")
