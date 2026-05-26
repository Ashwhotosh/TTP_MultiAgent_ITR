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
