"""
Local Column Lineage Explorer launcher.

This is the closest local equivalent to dbt Explorer-style column lineage:
1) extract lineage from dbt artifacts
2) render interactive HTML
3) serve it on a local web URL
"""

from __future__ import annotations

import argparse
import http.server
import socketserver
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINEAGE_DIR = Path(__file__).resolve().parent
TARGET_DIR = PROJECT_ROOT / "target"
REPORT_PATH = TARGET_DIR / "lineage_report.html"


def run_step(script_name: str) -> None:
    script_path = LINEAGE_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed: {script_name}")


def build_report() -> None:
    if not (TARGET_DIR / "manifest.json").exists():
        raise FileNotFoundError(
            "target/manifest.json not found. Run dbt first (e.g. dbt build/docs generate)."
        )
    run_step("extract_dbt_lineage.py")
    run_step("render_lineage_html.py")


def serve_report(port: int) -> None:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(f"{REPORT_PATH} not found.")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(TARGET_DIR), **kwargs)

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"Lineage Explorer running at http://127.0.0.1:{port}/lineage_report.html")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local lineage explorer.")
    parser.add_argument("--port", type=int, default=8787, help="Local server port")
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only generate report, do not start server",
    )
    args = parser.parse_args()

    build_report()
    print(f"Generated: {REPORT_PATH}")

    if not args.build_only:
        serve_report(args.port)


if __name__ == "__main__":
    main()
