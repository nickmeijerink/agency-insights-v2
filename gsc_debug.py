"""
GSC debug-script: test de Search Console fetch direct, zonder Claude of Slack.

Gebruik:
    export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... }'
    python gsc_debug.py
"""
from __future__ import annotations

import json
import os
import sys

key = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
if not key:
    print("❌  GOOGLE_SERVICE_ACCOUNT_JSON is niet gezet.")
    print("    export GOOGLE_SERVICE_ACCOUNT_JSON='<inhoud van service-account.json>'")
    sys.exit(1)

# Importeer pas nadat we weten dat de credentials beschikbaar zijn
import gsc  # noqa: E402

SITE_URL = "https://brainpink.nl/"

print(f"Testing GSC fetch voor: {SITE_URL}\n")
try:
    data = gsc.fetch(SITE_URL)
    print("✅  GSC fetch geslaagd!\n")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as exc:
    print(f"❌  GSC fetch mislukt: {exc}")
    print()
    print("Controleer:")
    print("  1. Klopt de site_url exact met wat in Search Console staat?")
    print("     (bijv. 'https://brainpink.nl/' vs 'sc-domain:brainpink.nl')")
    print("  2. Is het serviceaccount toegevoegd als gebruiker in GSC?")
    print("     (GSC → Instellingen → Gebruikers en machtigingen)")
    sys.exit(1)
