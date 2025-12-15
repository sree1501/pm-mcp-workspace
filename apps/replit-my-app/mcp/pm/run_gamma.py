import os
import time
import requests
import sys

# --- Config ---
GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
if not GAMMA_API_KEY:
    print("❌ GAMMA_API_KEY is not set. Add it to ~/.zshrc and retry.")
    sys.exit(1)

HEADERS = {
    "X-API-KEY": GAMMA_API_KEY,
    "Content-Type": "application/json",
}

BASE_URL = "https://public-api.gamma.app/v1.0"

# --- Input ---
title = input().strip()
if not title:
    print("❌ Title cannot be empty")
    sys.exit(1)

print("\nPaste the deck content (end with CTRL+D):\n")
content = ""
try:
    while True:
        content += input() + "\n"
except EOFError:
    pass

if not content.strip():
    print("❌ Deck content cannot be empty")
    sys.exit(1)

# --- Payload ---
payload = {
    "inputText": f"# {title}\n\n{content}",
    "exportAs": "pptx",
    "textMode": "generate",
    "textOptions": {
        "amount": "brief",
        "language": "en"
    }
}

# --- Create generation ---
print("\n🚀 Creating Gamma deck...")
r = requests.post(f"{BASE_URL}/generations", headers=HEADERS, json=payload)

if r.status_code >= 400:
    print("❌ Gamma error:", r.status_code)
    print(r.text)
    sys.exit(1)

gen = r.json()
gen_id = gen.get("generationId")

if not gen_id:
    print("❌ Missing generationId in response")
    print(gen)
    sys.exit(1)

print("⏳ Generation ID:", gen_id)

# --- Poll for completion ---
for _ in range(60):
    time.sleep(5)
    status = requests.get(
        f"{BASE_URL}/generations/{gen_id}",
        headers=HEADERS
    ).json()

    if status.get("status") == "completed":
        print("\n✅ DONE")
        print("📊 Gamma link:", status.get("gammaUrl"))
        print("📥 PPTX link:", status.get("exportUrl"))
        sys.exit(0)

    if status.get("status") in ("failed", "error"):
        print("❌ Gamma failed")
        print(status)
        sys.exit(1)

print("❌ Timed out waiting for Gamma")
