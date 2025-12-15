from mcp.server.fastmcp import FastMCP
import os, re, time, subprocess
import requests

mcp = FastMCP("Sree PM Assistant")

# -------------------------
# Helpers
# -------------------------
def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if not m:
                    continue
                key, raw_val = m.group(1), m.group(2).strip()
                if (raw_val.startswith('"') and raw_val.endswith('"')) or (raw_val.startswith("'") and raw_val.endswith("'")):
                    val = raw_val[1:-1]
                else:
                    val = raw_val
                os.environ.setdefault(key, val)
    except Exception:
        return

_load_env_file(os.path.expanduser("~/.pm-mcp.env"))

# -------------------------
# Gamma Tool
# -------------------------
GAMMA_BASE = "https://public-api.gamma.app/v1.0"

def _gamma_headers():
    key = os.getenv("GAMMA_API_KEY")
    if not key:
        raise RuntimeError('GAMMA_API_KEY is not set. Put it in ~/.pm-mcp.env as: export GAMMA_API_KEY="..."')
    return {"X-API-KEY": key, "Content-Type": "application/json"}

@mcp.tool()
def gamma_generate_pptx(
    title: str,
    deck_text: str,
    text_amount: str = "brief",
    language: str = "en",
    additional_instructions: str = ""
) -> str:
    if not title.strip():
        return "ERROR: title is empty"
    if not deck_text.strip():
        return "ERROR: deck_text is empty"

    payload = {
        "inputText": f"# {title}\n\n{deck_text}",
        "exportAs": "pptx",
        "textMode": "generate",
        "textOptions": {"amount": text_amount, "language": language},
    }
    if additional_instructions.strip():
        payload["additionalInstructions"] = additional_instructions.strip()

    r = requests.post(f"{GAMMA_BASE}/generations", headers=_gamma_headers(), json=payload, timeout=60)
    if r.status_code >= 400:
        return f"ERROR: Gamma create {r.status_code}: {r.text}"

    gen = r.json()
    gen_id = gen.get("generationId")
    if not gen_id:
        return f"ERROR: Missing generationId: {gen}"

    for _ in range(60):
        time.sleep(5)
        gr = requests.get(f"{GAMMA_BASE}/generations/{gen_id}", headers=_gamma_headers(), timeout=60)
        if gr.status_code >= 400:
            return f"ERROR: Gamma poll {gr.status_code}: {gr.text}"
        g = gr.json()
        if g.get("status") == "completed":
            return f"OK\nGamma: {g.get('gammaUrl')}\nPPTX: {g.get('exportUrl')}\nID: {gen_id}"
        if g.get("status") in ("failed", "error"):
            return f"ERROR: Gamma failed: {g}"

    return f"ERROR: Timed out. ID: {gen_id}"

# -------------------------
# Skyworks Phase 1 Tool
# -------------------------
SKYWORK_SLIDES_URL = "https://skywork.ai/agent/en/slides"

def _sky_prompt(title: str, deck_text: str, audience: str, detail: str, language: str) -> str:
    audience = (audience or "exec").strip().lower()
    detail = (detail or "brief").strip().lower()

    if audience == "engineering":
        tone = ("Write for engineering. Be specific and detailed. Include assumptions, dependencies, "
                "interfaces/APIs, edge cases, risks, and acceptance criteria. Avoid marketing language.")
    elif audience == "sales":
        tone = ("Write for sales. Emphasize customer pain, value, differentiators, competitive positioning, "
                "objection handling, and proof points. Make it easy to present.")
    else:
        tone = ("Write for executives. Be concise and outcome-oriented. Focus on strategy, tradeoffs, "
                "and 3–5 key takeaways. Avoid buzzwords.")

    if detail == "detailed":
        detail_hint = "Target 10–12 slides. Include speaker notes and 1 slide of risks/assumptions."
    elif detail == "medium":
        detail_hint = "Target 8–10 slides. Keep bullets tight; add short speaker notes on key slides."
    else:
        detail_hint = "Target 6–8 slides. Minimal text per slide; crisp bullets."

    return f"""Create a slide deck.

Title: {title}
Language: {language}
Audience: {audience}
Detail level: {detail}

Style guidance:
- {tone}
- {detail_hint}
- Use clear slide titles, short bullets, and consistent terminology.
- If you make claims, add placeholders for proof points rather than inventing numbers.

Source outline (convert into a polished deck):
{deck_text}
"""

@mcp.tool()
def skywork_prepare_slides(
    title: str,
    deck_text: str,
    audience: str = "exec",
    detail: str = "brief",
    language: str = "en",
    open_browser: bool = True
) -> str:
    if not title.strip():
        return "ERROR: title is empty"
    if not deck_text.strip():
        return "ERROR: deck_text is empty"

    prompt = _sky_prompt(title, deck_text, audience, detail, language)

    if open_browser:
        # Force Chrome Default profile (so you stay logged in)
        subprocess.run(
            ["open", "-a", "Google Chrome", "--args", "--profile-directory=Default", SKYWORK_SLIDES_URL],
            check=False
        )

    return "OK\nSkyworks Slides: " + SKYWORK_SLIDES_URL + "\n\n" + prompt
"""
# -------------------------
# Skyworks Phase 2 Tool (Playwright UI automation)
# -------------------------
@mcp.tool()
async def skywork_run_slides_phase2(
    title: str,
    deck_text: str,
    audience: str = "exec",
    detail: str = "brief",
    language: str = "en"
) -> str:
    prompt = _sky_prompt(title, deck_text, audience, detail, language)

    from pathlib import Path as _Path
    from playwright.async_api import async_playwright

    user_data_dir = str(_Path.home() / ".skywork_pw_profile")

    async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chrome",
            args=[
                "--disable-session-crashed-bubble",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-gpu",
            ]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(SKYWORK_SLIDES_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1200)

        # Find an input box and paste prompt
        filled = False
        try:
            locator = page.get_by_placeholder(re.compile("Enter a topic|Enter.*topic|upload a file", re.I))
            await locator.first.click(timeout=3000)
            await locator.first.fill(prompt, timeout=3000)
            filled = True
        except Exception:
            pass

        if not filled:
            try:
                ta = page.locator("textarea").first
                await ta.click(timeout=3000)
                await ta.fill(prompt, timeout=3000)
                filled = True
            except Exception:
                pass

        if not filled:
            try:
                ce = page.locator("[contenteditable='true']").first
                await ce.click(timeout=3000)
                await ce.fill(prompt, timeout=3000)
                filled = True
            except Exception:
                pass

        if not filled:
            await context.close()
            return "ERROR: Could not find an input box. If you see a login page, log in once in this window and rerun."

        # Click likely send/generate button; fallback Enter
        clicked = False
        candidates = [
            "button:has-text('Generate')",
            "button:has-text('Create')",
            "button[aria-label*='Send' i]",
            "button[aria-label*='Generate' i]",
            "button[aria-label*='Create' i]",
        ]
        for sel in candidates:
            try:
                btn = page.locator(sel).first
                await btn.click(timeout=2000)
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            try:
                await page.keyboard.press("Enter")
                clicked = True
            except Exception:
                pass

        await page.wait_for_timeout(1500)
        await context.close()

        if clicked:
            return "OK: Skyworks opened in Chrome. Prompt copied to clipboard + submitted."
return "ERROR: Could not trigger Generate/Send; tell me the exact button text you see."
"""


# -------------------------
# Skyworks Phase 2 (Native Chrome automation; uses existing logged-in session)
# -------------------------
def _copy_to_clipboard(text: str) -> None:
    import subprocess
    if not isinstance(text, str) or not text:
        raise ValueError('Clipboard text is empty')
    proc = subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)

@mcp.tool()
def skywork_run_slides_phase2_native(
    title: str,
    deck_text: str,
    audience: str = "exec",
    detail: str = "brief",
    language: str = "en"
) -> str:
    prompt = _sky_prompt(title, deck_text, audience, detail, language)

    # Save prompt to a file (always available even if clipboard/paste fails)
    from pathlib import Path
    out = Path.home() / "pm-mcp_last_skyworks_prompt.txt"
    out.write_text(prompt, encoding="utf-8")

    # Copy to clipboard (no Accessibility permission needed)
    import subprocess
    subprocess.run(["pbcopy"], input=prompt.encode("utf-8"), check=False)

    # Open Skyworks in normal Chrome session
    import subprocess as sp
    sp.run(["open", "-a", "Google Chrome", SKYWORK_SLIDES_URL], check=False)

    return f"OK: Opened Skyworks. Prompt copied to clipboard and saved to {out}"


    import subprocess, time
    subprocess.run(["open", "-a", "Google Chrome", SKYWORK_SLIDES_URL], check=False)
    time.sleep(1.2)

    applescript = """
tell application "Google Chrome" to activate
delay 0.4
tell application "System Events"
    keystroke "v" using command down
    delay 0.3
    key code 36
end tell
"""

    subprocess.run(["osascript", "-e", applescript], check=False)

    return "OK: Skyworks opened in Chrome. Prompt pasted + submitted. Check the browser tab."
def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
