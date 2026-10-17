"""Probe for the e2e fixture harness: start the API with FakeBackend on a free port and a temp
data dir, upload the fixture PDF, poll until ready, print segment count and first 3 segments."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "api"
PDF = (
    API
    / "tests/fixtures/pdfs"
    / (sys.argv[1] if len(sys.argv) > 1 else "academic_01_seahelm_audio.pdf")
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def get(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def upload(base: str, path: Path) -> dict[str, object]:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        f"{base}/documents",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        print("upload status", r.status)
        return json.loads(r.read())


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    data_dir = tempfile.mkdtemp(prefix="hn-e2e-")
    env = {**os.environ, "HEARNARRO_TTS_BACKEND": "fake"}
    cmd = [
        str(API / ".venv/bin/python"),
        "-m",
        "hearnarro",
        "serve",
        "--data-dir",
        data_dir,
    ]
    proc = subprocess.Popen([*cmd, "--port", str(port)], cwd=API, env=env)
    print("api pid", proc.pid, "port", port, "data_dir", data_dir)
    try:
        for _ in range(100):
            try:
                get(f"{base}/documents")
                break
            except OSError:
                time.sleep(0.2)
        t0 = time.monotonic()
        doc = upload(base, PDF)
        print("upload body", doc)
        while True:
            d = get(f"{base}/documents/{doc['id']}")
            assert isinstance(d, dict)
            if d["status"] in ("ready", "failed"):
                break
            time.sleep(0.25)
        print("final status", d["status"], f"after {time.monotonic() - t0:.1f}s")
        print("summary keys", sorted(d))
        print("sections", len(d.get("sections") or []), (d.get("sections") or [])[:3])
        seg = get(f"{base}/documents/{doc['id']}/segments?from=0&limit=500")
        assert isinstance(seg, dict)
        print("total", seg["total"], "next_from", seg["next_from"])
        bodies = [s for s in seg["segments"] if s["type"] == "body"]
        print("body segments", len(bodies))
        for s in seg["segments"][:3]:
            print(json.dumps(s, ensure_ascii=False))
        print("voices", get(f"{base}/voices"))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        print("api stopped, returncode", proc.returncode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
