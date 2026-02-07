# utils/json_repair.py
import re

def repair_json(text: str) -> str:
    """
    Do simple repairs: remove markdown fences, trailing commas, unquoted keys.
    This is a lightweight pre-clean for LLM outputs.
    """
    if not text:
        return text
    t = text.replace("```json", "").replace("```", "").strip()
    # isolate first JSON array/object
    if "[" in t and "]" in t and t.strip().startswith("["):
        t = t[t.find("["):t.rfind("]") + 1]
    # trailing commas
    t = re.sub(r",(\s*[\]}])", r"\1", t)
    # quote keys if missing
    t = re.sub(r'(\{|,)\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*:', r'\1 "\2":', t)
    return t
