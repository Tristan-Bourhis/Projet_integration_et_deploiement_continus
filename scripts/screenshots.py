"""Capture dans Chromium les rapports HTML contenant les sorties réelles.

Outil de documentation facultatif : pip install playwright ; playwright install chromium.
Exécuter d'abord scripts/demo_failure.py.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

output = Path("docs/captures")
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=1)
    for source in sorted(Path("artifacts/demo").glob("[0-9][0-9].html")):
        page.goto(source.resolve().as_uri())
        page.screenshot(path=str(output / f"{source.stem}.png"), full_page=True)
    browser.close()
