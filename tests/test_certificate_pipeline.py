from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.certificate.comparator import compare_fields, normalize_fields  # noqa: E402


def test_alias_normalization_and_match():
    ocr = normalize_fields({
        "certificate_number": "ABC-123",
        "name": "Jane Doe",
        "organization": "Example University",
        "date_of_issue": "01/02/2026",
    })
    web = {
        "certificate_id": "ABC-123",
        "recipient_name": "Jane Doe",
        "issuer": "Example University",
        "issued_date": "2026-02-01",
    }
    result = compare_fields(ocr, web)
    assert result["status"] == "MATCH"


def test_mismatch_is_deterministic():
    result = compare_fields(
        {"certificate_id": "ABC", "recipient_name": "Jane Doe", "issuer": "U", "issued_date": "2026-01-01"},
        {"certificate_id": "XYZ", "recipient_name": "Jane Doe", "issuer": "U", "issued_date": "2026-01-01"},
    )
    assert result["status"] == "MISMATCH"
    assert result["fields"]["certificate_id"]["status"] == "MISMATCH"


def test_scraping_happens_in_runner_process(tmp_path):
    html = """<html><title>Verify</title><body>
    <table>
      <tr><th>Certificate Number</th><td>ABC-123</td></tr>
      <tr><th>Name</th><td>Jane Doe</td></tr>
      <tr><th>Issuer</th><td>Example University</td></tr>
      <tr><th>Issued Date</th><td>2026-02-01</td></tr>
    </table></body></html>"""
    page = tmp_path / "verify.html"
    page.write_text(html, encoding="utf-8")
    # Start a tiny local server so the sandbox runner performs the HTTP request itself.
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    old = os.getcwd()
    os.chdir(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/verify.html"
        runner = ROOT / "sandbox" / "runner.py"
        proc = subprocess.run(
            [sys.executable, str(runner)],
            cwd=ROOT / "sandbox",
            input=json.dumps({"tool": "scrape_certificate", "arguments": {"url": url}}),
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        assert data["ok"] is True
        assert data["result"]["fields"]["certificate_id"] == "ABC-123"
    finally:
        server.shutdown()
        os.chdir(old)
