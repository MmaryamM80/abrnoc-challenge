#!/usr/bin/env python3
"""Write and sync a unique 100-record sample on a Gluster client mount."""

import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


MOUNT = Path('/mnt/ha')
if subprocess.run(['mountpoint', '-q', str(MOUNT)], check=False).returncode:
    raise SystemExit('Gluster volume is not mounted; sample was not written')

sample_id = uuid.uuid4().hex
path = MOUNT / f'rpo-drill-{sample_id}.txt'
records = [f'{sample_id}:{number:03d}\n' for number in range(1, 101)]
payload = ''.join(records).encode()
with path.open('xb') as sample:
    sample.write(payload)
    sample.flush()
    os.fsync(sample.fileno())

dir_fd = os.open(MOUNT, os.O_RDONLY)
try:
    os.fsync(dir_fd)
finally:
    os.close(dir_fd)

print(json.dumps({
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'path': str(path),
    'record_count': len(records),
    'sha256': hashlib.sha256(payload).hexdigest(),
    'sync': 'file and containing directory fsync completed',
}))
