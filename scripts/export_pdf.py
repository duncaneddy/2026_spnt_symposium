# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright", "pillow"]
# ///
"""Export the deck to a PDF, one page per slide.

Serves deck/ on a free local port, opens each slide in the installed Google Chrome (headless,
1920 x 1080, reduced motion so every slide lands on its final state), reveals every click step
and captures the slide as one page. A continuation slide that directly follows the slide it
builds on replaces that slide's page; a continuation shown again later in the deck is skipped,
so the PDF has one page per numbered slide. The Backup divider and every slide after it are
left out. Pages are images, so text in the PDF is not selectable.

Run:
  uv run scripts/export_pdf.py [--out path.pdf]
"""

import argparse
import io
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "deck"
DEFAULT_OUT = ROOT / "practical-astrodynamics-spnt-2026.pdf"
SIZE = {"width": 1920, "height": 1080}
SETTLE_MS = 2600
BACKUP_LABEL = "Backup"

SECTIONS_JS = """() => [...document.querySelectorAll('section.slide')].map(s => ({
  label: s.dataset.label, clone: s.dataset.clone || null,
}))"""
STEPS_JS = """i => Math.max(0, ...[...document.querySelectorAll('section.slide')[i]
  .querySelectorAll('[data-step]')].map(e => +e.dataset.step))"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def pages_to_capture(sections: list[dict]) -> list[int]:
    """Section indices that become pages, up to the Backup divider: a continuation replaces the
    slide it follows directly, and a continuation of an earlier slide is dropped."""
    keep = []
    for i, sec in enumerate(sections):
        if sec["label"] == BACKUP_LABEL:
            break
        if sec["clone"] is None:
            keep.append(i)
        elif keep and sections[keep[-1]]["label"] == sec["clone"] and keep[-1] == i - 1:
            keep[-1] = i
    return keep


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = parser.parse_args().out

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(DECK)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/"

    images = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_context(viewport=SIZE, reduced_motion="reduce").new_page()
        page.goto(base)
        page.wait_for_load_state("networkidle")
        sections = page.evaluate(SECTIONS_JS)
        for i in pages_to_capture(sections):
            page.goto(f"{base}?slide={i + 1}#{i + 1}")
            page.wait_for_load_state("networkidle")
            page.evaluate("() => document.fonts.ready")
            page.wait_for_timeout(600)
            for _ in range(page.evaluate(STEPS_JS, i)):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(150)
            page.wait_for_timeout(SETTLE_MS)
            assert page.evaluate("() => location.hash") == f"#{i + 1}", f"left slide {sections[i]['label']}"
            images.append(Image.open(io.BytesIO(page.screenshot(type="jpeg", quality=90))).convert("RGB"))
            print(f"{len(images):3d}  {sections[i]['label']}")
        browser.close()
    server.shutdown()

    out.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out, save_all=True, append_images=images[1:], resolution=144.0)
    print(f"wrote {out} ({len(images)} pages, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
