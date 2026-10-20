# AbrNOC VirtHost task checklist

**Checked** means the specified implementation, document, or test has evidence linked below. It does not turn a written HA design or a single-host laboratory into a production cluster. This checklist covers the supplied PDF and the later requests for Mac-run Ansible, a server-side Ceph test, Gluster removal, and English Markdown documentation.

The [acceptance matrix](docs/acceptance-matrix.md) separates PDF requirements from later requests. The [October 20 recheck](docs/recheck-2026-10-20.md) records fresh live findings.

## Host automation

- [x] Create an Ansible role for a fresh Debian KVM host: administrator account, SSH hardening, firewall, NTP, kernel settings, persistent logs, required packages, KVM, and libvirt. [Role](ansible/roles/virt_host/tasks/main.yml) · [validation](evidence/validation-summary.md)
- [x] Run the host playbook from the Mac with a syntax check, check-mode diff, real apply, and a second real run. The second run reported `changed=0`, `unreachable=0`, and `failed=0`. [Mac run evidence](evidence/mac-second-run.txt)
- [x] Verify KVM and service state on the server. [Host validation](evidence/kvm-host-validation.txt)

## Monitoring and incident operations

- [x] Collect host and libvirt metrics and define alerts for disk latency, RAID degradation, load, memory pressure, VM failure, and packet drops. [Rules](monitoring/virt-host-alerts.yml) · [health](evidence/mac-health.md)
- [x] Explain urgent paging versus business-hours handling and configure Alertmanager routing. [Policy](README.md#alert-coverage-and-routing)
- [x] Trigger at least two alert rules and observe them in Alertmanager. `DiskLatencyHigh` and `RAIDDegraded` reached the `page` receiver using temporary synthetic metrics. [Alert evidence](evidence/alert-firing.json)
- [x] Write the incident response for one unreachable host carrying 300 VMs after storage latency. [Runbook](docs/incident-response.md)
- [x] Analyze the supplied logs, separate likely root cause from symptoms and noise, and state uncertainty. [Log analysis](docs/log-analysis.md)
- [x] Record implementation problems and corrections. [Validation summary](evidence/validation-summary.md) · [Ceph lab](docs/ceph-lab.md)
- [ ] Deliver an actual alert to a person. No on-call destination was provided; Alertmanager routing was tested internally.
- [ ] Induce a physical RAID/NVMe failure or a real 300-VM incident. The supplied server has one virtual disk and no tenant VMs.

## HA and storage

- [x] Write an HA architecture covering storage choice, quorum, split brain, failure domains, capacity overhead, backups, maintenance, and proposed RPO/RTO. The design uses Ceph RBD. [Architecture](docs/architecture.md)
- [x] Measure one guest-level failover sample in the earlier three-guest Gluster lab: 0 of 100 acknowledged records missing on survivors, first HTTP recovery 42.468 seconds after stopping the active guest. [Historical drill](docs/kvm-ha-lab.md)
- [x] Install and exercise Ceph **on the supplied server**. The original `ceph1` guest passed an object round trip; the expanded lab has three KVM guests, three monitors in quorum, and three OSDs. The lab pools use three replicas with a minimum of two. [Ceph lab](docs/ceph-lab.md) · [original verification](evidence/ceph-final-validation.txt)
- [x] Remove the active Gluster lab after making Ceph's boot image independent of its old directory. The three guests, reservations, and known disk files were retired. [Retirement playbook](ansible/retire-gluster-lab.yml) · [run](evidence/gluster-retirement.txt) · [state verification](evidence/retirement-verification.txt)
- [x] Enable libvirt autostart for all three Ceph guests and confirm they are running. [Ceph lab](docs/ceph-lab.md)
- [x] Repeat the original single-guest Ceph playbooks without changes. [Host repeat](evidence/recheck-ceph-host-repeat-2026-10-20.txt) · [node repeat](evidence/recheck-ceph-node-repeat-2026-10-20.txt)
- [x] Repeat the expanded three-guest Ceph playbooks without changes. [Host repeat](evidence/ceph-ha-host-repeat-2026-10-20.txt) · [node repeat](evidence/ceph-ha-node-final-repeat-2026-10-20.txt)
- [x] Stop one nested Ceph guest and check acknowledged objects from a survivor. All 100 objects remained readable and unchanged; the first successful read was observed after 27.413 seconds. This does not establish an outage duration or tenant VM RTO. [Drill result](evidence/ceph-ha-drill-2026-10-20.json)
- [ ] Build a real multi-host Ceph/compute cluster with independent failure domains, fencing, and automated VM placement. All three current Ceph guests and all three replicas share the supplied VM.
- [ ] Measure the proposed **cross-host** tenant VM RPO/RTO. A nested guest failure drill can measure a narrower Ceph object-read and acknowledged-write sample; it cannot establish cross-host tenant recovery.
- [ ] Resolve the Debian Ceph manager's Python module compatibility issue before treating this lab as production ready. An always-on `volumes` module raised an `AttributeError` after a manager restart; the manager stayed active, and the [crash record](evidence/ceph-mgr-volumes-crash-2026-10-20.json) is saved.

## Handoff

- [x] Provide an English Markdown README, Ansible source, monitoring rules, architecture, incident response, log analysis, evidence, and this checklist in the local Git repository. [Report](TASK_REPORT.md)
- [ ] Publish the reviewed repository to [MmaryamM80/abrnoc-challenge](https://github.com/MmaryamM80/abrnoc-challenge). The staged-file check passed, but GitHub rejected the push because the Mac's SSH key belongs to `marco1370`, which has no write access to this repository.
