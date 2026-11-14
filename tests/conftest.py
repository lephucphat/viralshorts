import os
import sys

# Make the repo root importable so tests can import the app modules directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests always run the app in self-host (BYOK) mode. app.py freezes
# BILLING_ENABLED at import time and load_dotenv never overrides an existing
# variable, so this must be set here — before any test module imports app — or
# the suite's behavior would depend on the developer's personal .env.
os.environ["BILLING_ENABLED"] = "0"
# Same reasoning for outgoing mail: a developer's real SMTP settings would make signup
# require email verification (and withhold free credits), and could send real mail.
os.environ["SMTP_HOST"] = ""
# And for the dubbing engine and the TTS provider order.
os.environ["DUBBING_ENGINE"] = "local"
os.environ.pop("DUB_TTS", None)
