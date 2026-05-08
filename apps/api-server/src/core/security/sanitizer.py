def sanitize_user_text(value: str) -> str:
    sanitized = value.replace("```", "").replace("<tool_call>", "").replace("</tool_call>", "")
    return sanitized.strip()
