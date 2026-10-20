# Incident response: 300 VMs, storage latency then network loss

## First 15 minutes

| Time | Action |
| --- | --- |
| 0–2 min | Declare SEV1; assign incident commander, storage lead, network lead, and communications lead. Record onset time, affected hosts/VMs, and a shared timeline. Freeze deploys, migrations, snapshots, and nonessential maintenance. |
| 2–5 min | Test reachability from two independent networks and the out-of-band console. Check switch ports, host power, BMC, kernel console, Prometheus `up`, and Ceph/RAID state. Determine whether this is one host, one rack, or the control plane. |
| 5–10 min | If console works, collect `journalctl -k`, `dmesg`, `nvme smart-log`, `cat /proc/mdstat`, `ceph health detail` (if Ceph), `virsh list --all`, `ip -s link`, and `ss -s`. Use read-only checks first. Compare the first storage error to the first network drop. |
| 10–15 min | Contain: stop new VM placement and writes to damaged local storage; fence a host before restarting its guests elsewhere; shift traffic only to healthy capacity. Publish an initial status update with impact, confirmed facts, action, and next update time. |

## Distinguish the fault

* **Disk or controller:** NVMe timeouts, reset failures, disappeared namespace, media errors, degraded RAID, dm-thin I/O errors. These preceding network symptoms point to storage as the initiating failure.
* **Network:** Physical link down, switch errors, RX/TX drops, path-specific loss while console and local storage remain healthy. Compare BMC and independent probe paths.
* **Compute or memory:** CPU saturation, OOM kills, hung tasks, host panic, or hypervisor errors without earlier storage faults. Determine whether these are secondary to blocked I/O.
* **Monitoring only:** Exporters fail while guest reachability and host console remain healthy. Verify independently before escalating a host outage.

## Reboot decision

Do not reboot merely because SSH stops responding: it destroys volatile evidence and may restart guests against corrupt or read-only storage. Reboot only after the host has been fenced or isolated from shared storage, storage/data owners agree on recovery, evidence is captured where possible, and a known-good recovery path exists. Use BMC/console to attempt a controlled shutdown; use hard reset only when the host is irrecoverably hung and fencing is confirmed. Never rebuild a RAID or discard thin-pool metadata blindly.

## Recovery and closure

Replace the failing device or controller path; validate SMART/NVMe health, RAID or Ceph redundancy, thin-pool metadata, and filesystem integrity before resuming writes. Restore or restart VMs in priority order on healthy storage; check guest filesystems and application health, not just `virsh running`. Re-enable placement gradually, confirm latency and packet loss are back to baseline, and watch for recurrence. Reconcile missing writes against backup/application logs. Communicate at least every 15 minutes during SEV1 and provide a post-incident timeline, impact, root-cause confidence, and tracked prevention work.

### Restoring a 300-VM fleet

1. Export the expected inventory and last known placement from the control plane; reconcile it with `virsh list --all` and storage volume ownership. Do not infer that all 300 guests were affected merely because one host disappeared.
2. Prove the original host is fenced and cannot write to shared disks. Confirm storage quorum and replica health, network paths, and spare CPU/RAM/IOPS before admitting guests on surviving hosts. If any of these fail, hold restarts and move to backup/DR recovery with the storage owner.
3. Define a priority list with service owners: control-plane and network dependencies first, then customer services by criticality and dependency order. Reserve capacity for the highest-priority guests; use small batches instead of starting 300 guests simultaneously, which would amplify storage I/O and network load.
4. For each batch, attach each disk to exactly one guest, start the guest, verify guest-agent or console state, filesystem and application checks, and customer-facing probes. Record successes, failures, and any guests requiring restore or manual repair. Pause the next batch if storage latency, packet loss, or error rates rise.
5. Reconcile the final expected and running inventory, including guests intentionally left down. Compare application logs, transaction offsets, and backup snapshots for lost or duplicated writes. Hand each exception to an owner and publish the remaining impact.

### Communication checkpoints

At declaration, send an internal SEV1 page with the first affected host, observed impact, and incident roles. Within the first 15 minutes, publish a customer status note that separates confirmed impact from suspected cause and gives the next update time. Update internal responders and customers at least every 15 minutes while impact continues; include affected scope, recovery progress by batch, and known workarounds. After service recovery, publish a final status note, then a separate post-incident report once the root cause and prevention actions are verified. Avoid promising an RTO before fencing, storage health, and spare capacity are confirmed.

## Prevention

Alert on NVMe reset/timeouts, RAID degradation, thin-pool metadata health, storage latency, exporter loss, and NIC drops with independent off-host probes. Keep tested spare devices, capacity headroom, firmware qualification, fencing tests, restore drills, and immutable backups. Correlate logs and metrics by host and minute so the first fault is visible before cascading symptoms.
