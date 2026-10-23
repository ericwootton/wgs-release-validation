#!/usr/bin/env python3
"""Submit the workflow to a GA4GH WES 1.0 server, wait for it, and save the run log and outputs.

    wes_run.py --server http://localhost:8000/api/ga4gh/wes/v1 \
        --workflow-url http://127.0.0.1:8081/wdl/main.wdl --params _wes/fixture.wes.json --out _wes/fixture

Standard library only. Writes <out>/run_log.json (GET /runs/{id}), <out>/wes_run.json (the same
without server paths, safe to commit), and copies the small outputs (metrics.json, metrics.md)
into <out> when the server's paths are readable from here, which is the case for a server on this
machine. See docs/ga4gh.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

TERMINAL = {"COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"}
COPY = {"metrics_json": "metrics.json", "metrics_md": "metrics.md"}


def multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    """Encode form fields as multipart/form-data, which WES 1.0 requires for POST /runs."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')
    body = "".join(parts) + f"--{boundary}--\r\n"
    return body.encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def call(url: str, data: bytes | None = None, content_type: str | None = None, tries: int = 1) -> Any:
    """One request. GETs can be retried (tries > 1) on network errors, which a long run will meet."""
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    if content_type:
        req.add_header("Content-Type", content_type)
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise SystemExit(f"error: {req.method} {url} returned {e.code}: {body}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == tries:
                raise SystemExit(f"error: {req.method} {url} failed after {tries} tries: {e}") from None
            print(f"  {e}; retrying", flush=True)
            time.sleep(min(60, 5 * attempt))
    raise AssertionError("unreachable")


def submit(server: str, workflow_url: str, params: dict[str, Any], label: str) -> str:
    body, ctype = multipart(
        {
            "workflow_url": workflow_url,
            "workflow_type": "WDL",
            "workflow_type_version": "1.0",
            "workflow_params": json.dumps(params),
            "tags": json.dumps({"label": label}),
        }
    )
    return str(call(f"{server}/runs", body, ctype)["run_id"])


def wait(server: str, run_id: str, poll: float, timeout: float) -> str:
    start = time.monotonic()
    state = ""
    while time.monotonic() - start < timeout:
        # Just after a submit, Cromwell can answer without a state before the run is registered.
        new = str(call(f"{server}/runs/{run_id}/status", tries=5).get("state", "UNKNOWN"))
        if new != state:
            print(f"{time.monotonic() - start:7.0f} s  {new}", flush=True)
            state = new
        if state in TERMINAL:
            return state
        time.sleep(poll)
    raise SystemExit(f"error: run {run_id} still {state} after {timeout:.0f} s")


def save_outputs(run_log: dict[str, Any], out: Path) -> list[str]:
    """Copy the outputs named in COPY into out. Copies from an earlier run are removed first, so a
    file that cannot be read this time is missing rather than stale."""
    for stale in COPY.values():
        (out / stale).unlink(missing_ok=True)
    copied = []
    for key, value in (run_log.get("outputs") or {}).items():
        name = COPY.get(key.rsplit(".", 1)[-1])
        if name and isinstance(value, str) and Path(value).is_file():
            shutil.copyfile(value, out / name)
            copied.append(name)
    return copied


def summarise(run_log: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
    """The parts of a run log worth committing: no server paths, no inputs."""
    log = run_log.get("run_log") or {}
    tasks = run_log.get("task_logs") or []
    return {
        "run_id": run_log.get("run_id"),
        "state": run_log.get("state"),
        "wes_versions": info.get("supported_wes_versions"),
        "engine": info.get("workflow_engine_versions"),
        "start_time": log.get("start_time"),
        "end_time": log.get("end_time"),
        "tasks": sorted({str(t.get("name")) for t in tasks}),
        "task_exit_codes": sorted({t.get("exit_code") for t in tasks}, key=str),
        "outputs": sorted((run_log.get("outputs") or {}).keys()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", required=True, help="WES base URL, ending in /ga4gh/wes/v1")
    ap.add_argument("--workflow-url", required=True, help="URL of the main WDL; imports resolve relative to it")
    ap.add_argument("--params", type=Path, required=True, help="inputs JSON (scripts/cloud_inputs.py --target wes)")
    ap.add_argument("--run-id", help="follow a run already submitted instead of submitting a new one")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="wes")
    ap.add_argument("--poll", type=float, default=10.0)
    ap.add_argument("--timeout", type=float, default=3600.0)
    args = ap.parse_args(argv)

    server = args.server.rstrip("/")
    info = call(f"{server}/service-info")
    print(f"WES {', '.join(info.get('supported_wes_versions', []))}, engines {info.get('workflow_engine_versions')}")
    if args.run_id:
        run_id = args.run_id
    else:
        params = json.loads(args.params.read_text(encoding="utf-8"))
        run_id = submit(server, args.workflow_url, params, args.label)
        print(f"run {run_id} submitted")
    state = wait(server, run_id, args.poll, args.timeout)

    args.out.mkdir(parents=True, exist_ok=True)
    run_log = call(f"{server}/runs/{run_id}", tries=5)
    (args.out / "run_log.json").write_text(json.dumps(run_log, indent=2) + "\n", encoding="utf-8")
    summary = summarise(run_log, info)
    (args.out / "wes_run.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    copied = save_outputs(run_log, args.out)
    print(f"{state}; run log and {', '.join(copied) or 'no outputs'} in {args.out}")
    if state != "COMPLETE":
        return 1
    missing = sorted(set(COPY.values()) - set(copied))
    if missing:
        print(f"error: {', '.join(missing)} not readable from here; copy them from the server", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
