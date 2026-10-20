#!/usr/bin/env python3
"""Measure one nested-guest Ceph failure sample over SSH.

The sample exercises loss of ceph1 while ceph2 and ceph3 continue on the
same outer KVM host. It does not measure physical-host failure tolerance.
"""

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


OUTER = "ansible@104.194.148.88"
SURVIVOR = "ansible@192.168.122.125"
PROBE = "/usr/local/bin/ceph-rpo-probe"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_ssh(host: str, *args: str, timeout: int = 45) -> str:
    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    if host == SURVIVOR:
        command += ["-J", OUTER]
    command += [host, *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-1000:]}")
    return result.stdout.strip()


def run_probe(mode: str, sample_id: str | None = None) -> dict:
    arguments = ["sudo", "python3", PROBE, mode]
    if sample_id:
        arguments += ["--sample-id", sample_id]
    return json.loads(run_ssh(SURVIVOR, *arguments).splitlines()[-1])


def guest_state() -> str:
    return run_ssh(OUTER, "sudo", "virsh", "-c", "qemu:///system", "domstate", "ceph1").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence: dict = {
        "scope": "nested KVM guest failure on one outer VM",
        "failed_guest": "ceph1",
        "surviving_guest": "ceph2",
        "controller": "SSH controller",
        "created_utc": utc_now(),
        "probe_interval_seconds": 1,
    }
    failure_attempted = False
    try:
        pre_status = json.loads(run_ssh(SURVIVOR, "sudo", "ceph", "-s", "--format", "json"))
        assert pre_status["health"]["status"] == "HEALTH_OK", pre_status["health"]
        assert pre_status["monmap"]["num_mons"] == 3, pre_status["monmap"]
        assert pre_status["osdmap"]["num_up_osds"] == 3, pre_status["osdmap"]
        evidence["pre_failure_health"] = pre_status["health"]["status"]
        seed = run_probe("seed")
        sample_id = seed["sample_id"]
        evidence["seed"] = seed
        evidence["pre_failure_verify"] = run_probe("verify", sample_id)

        # Start timing before the shutdown command to conservatively include
        # SSH and virsh command latency in the measured recovery bound.
        start = time.monotonic()
        evidence["failure_command_started_utc"] = utc_now()
        failure_attempted = True
        run_ssh(OUTER, "sudo", "virsh", "-c", "qemu:///system", "destroy", "ceph1")
        evidence["failure_command_finished_utc"] = utc_now()
        evidence["failure_command_duration_seconds"] = round(time.monotonic() - start, 3)

        attempts = []
        deadline = start + 300
        while time.monotonic() < deadline:
            try:
                probe = run_probe("probe", sample_id)
                attempts.append({"elapsed_seconds": round(time.monotonic() - start, 3), "ok": probe["ok"]})
                if probe["ok"]:
                    evidence["first_success_seconds"] = attempts[-1]["elapsed_seconds"]
                    break
            except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
                attempts.append({"elapsed_seconds": round(time.monotonic() - start, 3), "error": str(exc)[:500]})
            time.sleep(1)
        else:
            raise TimeoutError("No successful surviving-guest read within 300 seconds")
        evidence["probe_attempts"] = attempts
        evidence["during_failure_verify"] = run_probe("verify", sample_id)
        evidence["during_failure_health"] = json.loads(
            run_ssh(SURVIVOR, "sudo", "ceph", "-s", "--format", "json")
        )["health"]["status"]
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if failure_attempted:
            try:
                if guest_state() != "running":
                    run_ssh(OUTER, "sudo", "virsh", "-c", "qemu:///system", "start", "ceph1")
                    evidence["guest_restarted_utc"] = utc_now()
                else:
                    evidence["guest_already_running_utc"] = utc_now()
            except Exception as exc:
                evidence["restart_error"] = f"{type(exc).__name__}: {exc}"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
