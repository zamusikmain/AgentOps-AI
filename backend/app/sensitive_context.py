"""Fail closed on configured credentials in external SDK payloads; never log matches."""
import re
PATTERN=re.compile(r'AIza[\w-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|Bearer\s+[\w.-]{12,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',re.I)
def contains_secret(settings,text):
    values=(settings.gemini_api_key.get_secret_value(),settings.api_token.get_secret_value())
    return bool(PATTERN.search(text) or any(value and len(value)>=12 and value in text for value in values))
