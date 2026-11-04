# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Start the packaged Motor Pool: serve on a free port on this computer only,
open the default browser, and keep the console window as the off switch."""

from __future__ import annotations

import os
import sys
import threading
import traceback
import webbrowser


def main():
    os.environ.setdefault("MOTORPOOL_DIST", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    try:
        from waitress import create_server

        from . import dist
        from .app import APP_NAME, create_app
        ab = dist.about()
        print(f"{APP_NAME} v{ab['version']}" + (f"  (data {ab['data_date']})" if ab["data_date"] else ""))
        problems = dist.check_bundle()
        if problems:
            print()
            print("WARNING: some of Motor Pool's files are missing:")
            for p in problems:
                print("  - " + p)
            print("The zip was probably not fully extracted, or antivirus removed files.")
            print("Close this window, delete the Motor Pool folder, right-click the zip,")
            print("choose Extract All, wait until it finishes, then start MotorPool.exe again.")
            print("Starting anyway; some units may be missing.")
            print()
        print("Loading units, this takes a few seconds...")
        app = create_app()
        server = create_server(app, host="127.0.0.1", port=0, threads=6)
        url = f"http://127.0.0.1:{server.effective_port}/"
        print()
        print(f"{APP_NAME} is running at {url}")
        print("Your browser should open by itself; if not, paste that address into it.")
        print()
        print("Close this window to quit.")
        if not os.environ.get("MOTORPOOL_NO_BROWSER"):     # set by automated tests
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        server.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
        print()
        print("Motor Pool couldn't start. Please send the text above with your feedback.")
        try:
            input("Press Enter to close this window.")
        except EOFError:
            pass
        sys.exit(1)
