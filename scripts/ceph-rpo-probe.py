#!/usr/bin/env python3
"""Write and verify an acknowledged RADOS sample in the disposable Ceph lab."""

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone

import rados


POOL = "lab-objects"
COUNT = 100


def payload(sample_id: str, number: int) -> bytes:
    return f"{sample_id}:{number:03d}\n".encode()


def key(sample_id: str, number: int) -> str:
    return f"rpo-drill-{sample_id}-{number:03d}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "probe", "verify"))
    parser.add_argument("--sample-id")
    args = parser.parse_args()
    sample_id = args.sample_id or uuid.uuid4().hex
    if args.mode != "seed" and not args.sample_id:
        parser.error("--sample-id is required for probe and verify")

    with rados.Rados(conffile="/etc/ceph/ceph.conf") as cluster:
        with cluster.open_ioctx(POOL) as ioctx:
            if args.mode == "seed":
                for number in range(1, COUNT + 1):
                    ioctx.write_full(key(sample_id, number), payload(sample_id, number))
                result = {"mode": args.mode, "acknowledged": COUNT}
            else:
                numbers = range(1, 2) if args.mode == "probe" else range(1, COUNT + 1)
                missing = []
                mismatched = []
                for number in numbers:
                    try:
                        actual = ioctx.read(key(sample_id, number))
                    except rados.ObjectNotFound:
                        missing.append(number)
                        continue
                    if actual != payload(sample_id, number):
                        mismatched.append(number)
                result = {
                    "mode": args.mode,
                    "checked": len(numbers),
                    "missing": missing,
                    "mismatched": mismatched,
                }
                if missing or mismatched:
                    result["ok"] = False
                    print(json.dumps(result, sort_keys=True))
                    raise SystemExit(1)
                result["ok"] = True

    result["sample_id"] = sample_id
    result["payload_sha256"] = hashlib.sha256(
        b"".join(payload(sample_id, number) for number in range(1, COUNT + 1))
    ).hexdigest()
    result["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
