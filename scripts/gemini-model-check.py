"""One metadata request only; does not generate content or reveal provider errors."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.config import Settings
from google import genai
from google.genai import types, errors

settings = Settings()
model = 'gemini-3.5-flash-lite'
report = {'model': model, 'generation_requests': 0}
client = genai.Client(api_key=settings.gemini_api_key.get_secret_value(),
    http_options=types.HttpOptions(timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)))
try:
    info = client.models.get(model=model)
    report.update(http_status=200, available='generateContent' in (info.supported_actions or []), name=info.name)
except errors.APIError as exc:
    report.update(http_status=exc.code, available=False, error='model_metadata_request_failed')
except Exception:
    report.update(http_status=None, available=False, error='network_or_client_error')
finally:
    client.close()
(root / 'docs/gemini-model-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
