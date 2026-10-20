# VirtHost task report

**Exercise:** AbrNOC Senior DevOps — KVM virtualization host  
**Implementation target:** supplied Debian 13 virtual server  
**Validation date:** October 20, 2026  
**Status:** the host implementation and written deliverables are complete. A three-guest Ceph lab runs on the server. Production multi-host HA remains open.

## What was requested

The supplied exercise asks for a partially implemented KVM host, operated through Ansible, plus monitoring, an incident response plan, an HA design, and analysis of supplied failure logs. It also asks for a second Ansible run with no changes and two alerts observed in Alertmanager. The [acceptance matrix](docs/acceptance-matrix.md) maps each requirement to its evidence and limits.

## What was done, step by step

1. **Inspected the server.** It is a Debian 13 VM with 4 vCPUs, about 11 GiB RAM, one 300 GB virtual disk, and an accessible `/dev/kvm`. It has no physical RAID, NVMe device, or tenant VM.
2. **Built the host automation.** The [host playbook](ansible/site.yml) runs focused roles for base system settings, KVM, metrics, access, firewall, and optional local monitoring. They configure an administrator account with key-based SSH, disable root and password SSH login, install a firewall and time synchronization, set host logging and kernel options, and install KVM/libvirt and host utilities. The access role checks the effective SSH policy before reloading SSH.
3. **Added monitoring.** Node and libvirt exporters feed a local Prometheus instance. Nine [alert rules](monitoring/virt-host-alerts.yml) cover disk latency, RAID degradation, load, memory pressure, packet drops, exporter/libvirt failures, and failed VMs. Alertmanager routes critical alerts to `page` and warning alerts to the documented business-hours policy.
4. **Ran Ansible from the Mac.** An isolated Python 3.12 environment with `ansible-core==2.19.3` was used for syntax checking, a check-mode diff, a real apply, and a second real run. The [check](evidence/mac-check-run.txt), [apply](evidence/mac-apply-run.txt), and [second-run output](evidence/mac-second-run.txt) are saved. The second run ended with `changed=0`, `unreachable=0`, and `failed=0`.
5. **Checked the live host.** All eight relevant services were active. `virt-host-validate qemu` passed the KVM device and cgroup checks; it warned that IOMMU and secure guest support were unavailable or unknown. See [live validation](evidence/kvm-host-validation.txt) and [monitoring health](evidence/mac-health.md).
6. **Tested two alerts safely.** Temporary synthetic textfile metrics triggered `DiskLatencyHigh` and `RAIDDegraded`. Both appeared as active alerts in Alertmanager with receiver `page`; the test metrics were then removed. See the [captured Alertmanager response](evidence/alert-firing.json).
7. **Wrote the operational deliverables.** The [incident response](docs/incident-response.md) covers the first 15 minutes, fault isolation, reboot criteria, recovery, and communications for a hypothetical 300-VM outage. The [HA architecture](docs/architecture.md) covers storage choice, quorum, failure domains, RPO/RTO, backups, capacity, and maintenance. The [log analysis](docs/log-analysis.md) distinguishes likely cause from symptoms and uncertainty.
8. **Built and tested a nested KVM cluster, then retired it.** Three guest VMs previously ran on the supplied server. GlusterFS replica 3 stored a shared nginx page, and keepalived moved a lab-only VIP. Destroying the active guest produced a first successful VIP response after 42.468 seconds; neither survivor lost any of 100 acknowledged, synced test records. After validation, this lab was removed at the user's request. The [historical report](docs/kvm-ha-lab.md) preserves the measurement method, raw evidence, and failure-domain limits.
9. **Repeated the lab automation.** The [host repeat](evidence/kvm-lab-repeat.txt) and [steady-state guest repeat](evidence/kvm-cluster-steady.txt) both completed with `changed=0` and `failed=0`.
10. **Installed Ceph on the server, not the Mac.** Mac-run Ansible first created and verified `ceph1`, then added `ceph2` and `ceph3`. Each nested KVM guest has a dedicated 8 GiB OSD disk. The three monitors reached quorum, all three OSDs were `up` and `in`, and both pools were set to `size 3` and `min_size 2`. The [Ceph report](docs/ceph-lab.md) records the commands, package workaround, and limits.
11. **Removed Gluster safely.** Ceph's boot image was made independent of the former Gluster directory before the [retirement playbook](ansible/retire-gluster-lab.yml) removed `ha1`/`ha2`/`ha3`, their DHCP entries, and known lab files. The [retirement evidence](evidence/gluster-retirement.txt) and [repeat](evidence/gluster-retirement-repeat.txt) capture the result.
12. **Rechecked every requirement and the live lab.** The [October 20 audit](docs/recheck-2026-10-20.md) separates PDF requirements from later requests. It found and fixed disabled libvirt autostart on `ceph1`; the [host-playbook repeat](evidence/recheck-ceph-host-repeat-2026-10-20.txt) made no changes. That audit is a snapshot from before the three-guest expansion. Current status belongs in the [Ceph report](docs/ceph-lab.md). A standby manager startup crash in the unused `nfs` module was inspected, addressed in Ansible, and archived.
13. **Measured one Ceph guest-failure sample.** With the cluster healthy, I wrote and confirmed 100 objects, stopped `ceph1`, and read all 100 through `ceph2` without a missing or changed object. The first successful read was observed 27.413 seconds after the stop command began. Only one probe attempt was recorded, so that figure is the first observation, not a proven outage duration. The script restarted `ceph1`. The [raw drill result](evidence/ceph-ha-drill-2026-10-20.json) records the timings and hashes.

## What the evidence does and does not prove

The host automation was applied to the supplied VM, and its recorded repeat run was idempotent. Its tasks are now organized into focused roles; the recorded run predates that layout change. The host can access KVM, libvirt is running, both exporters are being scraped, and two synthetic critical alerts reached Alertmanager.

The server has one virtual disk and no physical RAID, so storage hardware failures were not induced. The historical three-guest Gluster drill demonstrated guest-level replication and HTTP failover; its measurement does **not** prove survival of the supplied server or its underlying hypervisor. Those guests are now removed. The current Ceph lab has three replicas, but they share the same outer VM. Its guest-failure sample cannot prove cross-host tenant VM RPO/RTO. The Debian Ceph manager also logged a crash in its always-on `volumes` module after a restart; the manager remained active, but the package issue needs a lasting fix. The 300-VM incident and independently hosted HA design remain written plans. The local monitoring stack shares the host's failure domain. Alertmanager has no configured email, webhook, or paging destination, so the `page` receiver **does not deliver a notification to a person**. These limits and the recommended next steps are detailed in the [acceptance matrix](docs/acceptance-matrix.md).

The PDF permits Ceph, LINSTOR/DRBD, or another justified HA storage solution; it does not mandate Gluster. The production design selects Ceph RBD. The current three-guest deployment tests Ceph quorum and replication inside the supplied VM. See the [resource and failure-domain assessment](docs/ceph-lab.md).

## Repository and handoff

- [README](README.md): setup, Mac run procedure, alert policy, and operational links.
- [Host playbook](ansible/site.yml) and [role layout](docs/ansible-operations.md#host-role-layout): host configuration.
- [Monitoring rules](monitoring/virt-host-alerts.yml): nine alerts.
- [Acceptance matrix](docs/acceptance-matrix.md): requirement-by-requirement status and tradeoffs.
- [Task checklist](TASK_CHECKLIST.md): checked and open PDF and follow-up items.
- [Ceph lab](docs/ceph-lab.md): current three-guest deployment, verification, and Gluster retirement.
- [Ansible run guide](docs/ansible-operations.md): exact Mac commands for the host and Ceph lab.
- [Command ledger](docs/commands.md): execution and validation record.
- [October 20 recheck](docs/recheck-2026-10-20.md): line-by-line audit, fresh live checks, and remaining limits.

The reviewed repository was published to [MmaryamM80/abrnoc-challenge](https://github.com/MmaryamM80/abrnoc-challenge) using a repository-scoped deploy key. The published files contain no server password, private SSH key, or local workspace metadata.
