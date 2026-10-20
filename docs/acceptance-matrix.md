# Acceptance matrix against the supplied exercise

The exercise asks for a **partial implementation** of a KVM host plus operational design and incident analysis. "Implemented" below means applied to the supplied Debian VM; "designed" does not imply a working multi-host platform.

| PDF requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Ansible role for a fresh Debian virtualization host: administrator, SSH, firewall, NTP, kernel settings, logging, packages, KVM/libvirt | Implemented on the supplied VM | [`ansible/roles/virt_host`](../ansible/roles/virt_host/tasks/main.yml), [run summary](../evidence/validation-summary.md), and [live KVM validation](../evidence/kvm-host-validation.txt). The supplied server was used as the provisioning target; this is not evidence of testing every Debian release or hardware model. |
| Idempotent second run with zero changes | Verified | [Mac second run](../evidence/mac-second-run.txt): `changed=0 failed=0`. |
| Node and libvirt metrics, with rules for disk latency, RAID, load, memory, VM failure, packet loss | Implemented and validated as configuration | [Nine rules](../monitoring/virt-host-alerts.yml), [health checks](../evidence/mac-health.md). No physical RAID exists on this VM; no real RAID failure was induced. The lab guests do not prove the alert works for every guest-failure mode. Host NIC drops are a proxy for loss, not an end-to-end packet-loss test. |
| State immediate page versus business-hours response and why | Configured and explained | [Alert policy](../README.md#alert-coverage-and-routing). Receiver routing works inside Alertmanager; no on-call endpoint was supplied, so no human receives a notification. |
| Incident response for an unreachable host with 300 VMs after storage latency | Written | [Incident response](incident-response.md), including first 15 minutes, fault isolation, reboot decision, recovery batches, and communications. It was not exercised against 300 actual VMs. |
| HA design with RPO/RTO, quorum, split brain, failure domains, backup, overhead, maintenance | Designed | [Architecture and diagram](architecture.md). A single supplied VM cannot prove the stated recovery objectives. |
| Analyze supplied logs, causal chain, root cause versus symptom, noise | Written | [Log analysis](log-analysis.md). |
| Run Ansible twice against a VM and show second output | Verified | [Initial local repeat](../evidence/second-run.txt) and [Mac execution](../evidence/mac-apply-run.txt) followed by [Mac repeat](../evidence/mac-second-run.txt). |
| Force two alerts and observe them in Alertmanager; report failures | Verified with safe test metrics | [Alertmanager firing response](../evidence/alert-firing.json) and [failures corrected](../evidence/validation-summary.md). Test metrics were removed afterward. |
| Git repository containing role, monitoring, README, architecture, incident, and log documents | Ready locally; publication blocked | The reviewed commit is ready for [MmaryamM80/abrnoc-challenge](https://github.com/MmaryamM80/abrnoc-challenge). GitHub rejected the push because the current SSH account lacks write access. |

## Later requests and additional laboratory work

These activities were requested after the PDF or added as extra validation; they are not acceptance requirements in the supplied exercise.

| Request or extra test | Status | Evidence and boundary |
| --- | --- | --- |
| Run Ansible from the Mac | Verified | [Mac apply](../evidence/mac-apply-run.txt) and [second run](../evidence/mac-second-run.txt). |
| Test nested KVM guest failover | Historical lab, measured and retired | [KVM laboratory](kvm-ha-lab.md): three nested guests, replica-3 Gluster, lab VIP, 100 of 100 acknowledged records retained, first successful HTTP response 42.468 seconds after destroying the VIP owner. All guests shared the supplied VM, so independent-host HA remains untested. |
| Test Ceph on the supplied server and remove the active Gluster lab | Implemented | [Ceph laboratory](ceph-lab.md): three nested KVM guests, three monitors in quorum, three OSDs, and size-three pools. The original [RADOS verification](../evidence/ceph-final-validation.txt), [retirement](../evidence/gluster-retirement.txt), and [remaining-resource verification](../evidence/retirement-verification.txt) are recorded. All replicas still share one outer VM. |
| Test one nested Ceph guest failure | Measured at guest level | [Drill output](../evidence/ceph-ha-drill-2026-10-20.json): 100 acknowledged objects remained readable and unchanged through `ceph2` after stopping `ceph1`. The first successful read was observed at 27.413 seconds; it is not a measured outage duration or cross-host tenant RTO. |
| Include Mac Ansible commands and a natural English handoff | Written | [Run guide](ansible-operations.md), [task report](../TASK_REPORT.md), and [checklist](../TASK_CHECKLIST.md). |
| Provide an English Markdown handoff and audit every task | Written | [Task report](../TASK_REPORT.md), [checklist](../TASK_CHECKLIST.md), and [October 20 recheck](recheck-2026-10-20.md). |

## Assumptions and tradeoffs

- The supplied VM is the permitted implementation target. Its `/dev/kvm` is usable, but it has one virtual disk, no physical NVMe or md RAID, no tenant guests, and no independent failure domain.
- We chose one local Prometheus and Alertmanager pair to show rule evaluation and routing. It fails with the host, so production monitoring must live outside the compute failure domain. The receivers are intentionally empty until an authorized on-call destination is supplied.
- We chose a broad `ansible` sudo grant and SSH access on port 22 from any source to preserve a recovery path in this exercise. Production should use a management network or VPN, restricted source addresses, individual operator identities, audited privilege escalation, and a tested break-glass path.
- Physical RAID degradation, 300-VM failover, and independent-host HA could not be exercised on the supplied VM. The retired Gluster lab exercised guest-level behavior only. The current Ceph guests establish quorum and replication at guest level, but all OSDs share the supplied VM and its virtual disk. `virt-host-validate qemu` and libvirt health checks prove host capability, while the separate lab evidence records what workload and failover tests actually showed.
- The monitoring rules use simple fixed thresholds. Production thresholds need baseline data, per-device/per-host tuning, runbooks, and an independent reachability probe. A crashed guest can also disappear from exporter output; detecting every expected VM requires an external inventory or control-plane state comparison.

## If more time and infrastructure were available

1. Add an off-host monitoring stack and real on-call receiver, then test both delivery and acknowledgement end to end.
2. Build three independent compute/storage failure domains, fencing, and a VM placement controller; run measured host and rack failure drills to validate RPO/RTO.
3. Create representative guests, exercise boot and migration, and compare expected VM inventory with actual libvirt state.
4. Test physical disk, controller, and network failure modes in a staging cluster; tune alert thresholds and restore runbooks from observed behavior.
5. Narrow management ingress and sudo permissions after documenting the real access path and recovery method.
