#!/usr/bin/env python3
"""Measure observed guest-failure recovery from the KVM host.

Run only after the replicated service and VIP have passed their health checks.
The script deliberately destroys one named lab VM and reports actual timings.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def probe(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200 and b"shared volume online" in response.read()
    except (OSError, urllib.error.URLError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="ha1")
    parser.add_argument("--url", default="http://192.168.122.130/")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    if not all(probe(args.url, 1.0) for _ in range(3)):
        print("VIP did not pass three baseline probes; no VM was stopped", file=sys.stderr)
        return 2

    started_utc = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    destroy = subprocess.run(
        ["sudo", "virsh", "-c", "qemu:///system", "destroy", args.domain],
        text=True,
        capture_output=True,
        check=False,
    )
    destroy_end = time.monotonic()
    if destroy.returncode:
        print(destroy.stderr.strip(), file=sys.stderr)
        return 3

    samples = []
    first_failure = None
    recovered = None
    deadline = start + args.timeout
    while time.monotonic() < deadline:
        sample_start = time.monotonic()
        ok = probe(args.url, 0.75)
        offset = round(sample_start - start, 3)
        samples.append({"seconds_after_destroy_start": offset, "ok": ok})
        if not ok and first_failure is None:
            first_failure = sample_start
        if ok and first_failure is not None:
            recovered = sample_start
            break
        time.sleep(0.2)

    result = {
        "started_utc": started_utc,
        "failed_domain": args.domain,
        "probe_url": args.url,
        "probe_interval_seconds": 0.2,
        "probe_timeout_seconds": 0.75,
        "virsh_destroy_duration_seconds": round(destroy_end - start, 3),
        "first_failed_probe_after_destroy_start_seconds": (
            round(first_failure - start, 3) if first_failure else None
        ),
        "first_recovered_probe_after_destroy_start_seconds": (
            round(recovered - start, 3) if recovered else None
        ),
        "observed_outage_seconds": (
            round(recovered - first_failure, 3) if recovered and first_failure else None
        ),
        "sample_count": len(samples),
        "samples": samples,
    }
    print(json.dumps(result, indent=2))
    return 0 if recovered else 4


if __name__ == "__main__":
    raise SystemExit(main())
