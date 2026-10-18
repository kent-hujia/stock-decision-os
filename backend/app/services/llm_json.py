import json
import re


def parse_llm_json(message):
    """Return the JSON value in a Claude reply, ignoring ```json fences or text around it."""
    text = next(b.text for b in message.content if b.type == "text").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("["), text.find("{")) if i != -1]
        if not starts:
            raise
        start = min(starts)
        end = max(text.rfind("]"), text.rfind("}")) + 1
        return json.loads(text[start:end])
