"""One-time Google login. Opens a browser, asks for calendar read only, saves the token.
Run: uv run --group auth python scripts/google_auth.py  (weekly in Testing)"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app.scopes import ALLOWED_SCOPES  # noqa: E402

SECRETS = os.environ.get("GOOGLE_CLIENT_SECRETS_PATH", "./secrets/client_secret.json")
TOKEN = Path(os.environ.get("GOOGLE_TOKEN_PATH", "./secrets/google_token.json"))
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

assert set(SCOPES) <= set(ALLOWED_SCOPES)
creds = InstalledAppFlow.from_client_secrets_file(SECRETS, SCOPES).run_local_server(port=0)
TOKEN.write_text(json.dumps({"refresh_token": creds.refresh_token, "access_token": creds.token}))
TOKEN.chmod(0o600)
print(f"saved {TOKEN}")
