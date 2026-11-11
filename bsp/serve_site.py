# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Look at the public website on your own computer.

    python -m bsp.serve_site            # http://127.0.0.1:8765
    python -m bsp.serve_site --port 9000

Like `python -m http.server -d site`, but it tells the browser to check for a
newer copy of every file each time, so after `python -m bsp.export_site` a
plain refresh shows the new site (no stale page or script from an earlier
export). Only this computer can reach it (127.0.0.1). Ctrl+C stops it.
"""

from __future__ import annotations

import argparse
import functools
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class NoStaleHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Revalidate every time (unchanged files still come back as a quick 304).
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):      # keep the console quiet
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="Serve the public website (site/) on this computer.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    if not (SITE / "index.html").exists():
        raise SystemExit(f"No website in {SITE} yet. Run: python -m bsp.export_site")
    handler = functools.partial(NoStaleHandler, directory=str(SITE))
    server = ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Website at {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
