!
Check where the model name is hardcoded in your project:
bash# Find all places phi3:mini or model name is set
grep -r "phi3" FinV3/ --include="*.py" -l
grep -r "ollama_model" FinV3/ --include="*.py" -l
Update each file found. The main ones are likely:
agents/orchestrator.py
python# Change this:
def __init__(self, ollama_model: str = "phi3:mini", ...):

# To this:
def __init__(self, ollama_model: str = "qwen2.5:7b", ...):
frontend/app.py (if it has a model selector)
python# Change default model to qwen2.5:7b
Or set it once via environment variable so you only change one place:
bash# Add this to your .env file or set in terminal
echo "OLLAMA_MODEL=qwen2.5:7b" >> .env
Then in orchestrator.py:
pythonimport os
def __init__(self, ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b"), ...):