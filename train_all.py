"""
train_all.py — Orchestrates all training steps for FinITR-AI v3.
Runs:
1. scripts/generate_training_data.py
2. models/notice_predictor.py --train
3. models/transaction_classifier_v2.py --train
"""
import sys
import subprocess
import os

def run_cmd(args):
    result = subprocess.run([sys.executable] + args)
    if result.returncode != 0:
        print(f"Error running command: {' '.join(args)}")
        sys.exit(result.returncode)

def main():
    # Set non-interactive matplotlib backend just in case
    os.environ["MPLBACKEND"] = "Agg"
    
    print("\n===========================================================")
    print("  Step 1/3: Generating transaction training data")
    print("===========================================================")
    run_cmd(["scripts/generate_training_data.py"])
    
    print("\n===========================================================")
    print("  Step 2/3: Training Notice Predictor (Gradient Boosting)")
    print("===========================================================")
    run_cmd(["-m", "models.notice_predictor", "--train"])
    print("[OK] Done: Step 2/3")
    
    print("\n===========================================================")
    print("  Step 3/3: Training Transaction Classifier (Multilingual kNN)")
    print("===========================================================")
    run_cmd(["-m", "models.transaction_classifier_v2", "--train"])
    print("[OK] Done: Step 3/3")
    
    print("\n[OK] All models trained successfully!")

if __name__ == "__main__":
    main()
