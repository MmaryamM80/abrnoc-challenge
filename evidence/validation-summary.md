# VirtHost host validation

This is the record of the original host setup and the later Ansible run from the Mac. It predates the KVM guest and Ceph work. For the current lab state, see the [Ceph report](../docs/ceph-lab.md) and [acceptance matrix](../docs/acceptance-matrix.md).

## Starting point

The supplied machine was a Debian 13.7 VM with four virtual CPUs, about 11 GiB of RAM, one 300 GB virtual disk, and access to `/dev/kvm`. It had no physical NVMe disk, RAID array, or tenant VMs. Hardware disk failure and independent host failure could not be tested on this machine.

## Host work and checks

| Work | Observed result |
| --- | --- |
| Created the `ansible` administrator with the supplied public SSH key, passwordless sudo, and SSH hardening | Key login continued to work. Effective `sshd -T` settings showed root login and password authentication disabled; a root key login attempt was rejected. |
| Installed QEMU/KVM, libvirt, disk utilities, chrony, rsyslog, persistent journald, kernel settings, and nftables | `virsh -c qemu:///system list --all` worked. At this stage, the guest list was empty. |
| Installed node exporter, libvirt exporter, Prometheus, and Alertmanager | Both Prometheus targets were up; `libvirt_up=1`. The monitoring web ports listened on `127.0.0.1`. |
| Installed nine alert rules | `promtool check rules` and `amtool check-config` passed. Two storage alerts were tested without causing a real fault. |
| Repeated the host playbook | The [original second run](second-run.txt) ended with `ok=27 changed=0 unreachable=0 failed=0`. |

Three issues surfaced during setup. Alertmanager initially rejected the weekday range and lacked a suitable private IP for gossip on this single node; the days were listed individually and clustering was disabled. A cloud-init SSH file took precedence over the first hardening file, so the role moved its settings to `00-virt-host.conf` and now checks the effective policy before reloading SSH. The libvirt exporter process was running but reported `libvirt_up=0` until its service user gained access to the libvirt socket; it then reported `1`.

## Alert test

Temporary textfile metrics set `abrnoc_test_disk_latency_high=1` and `abrnoc_test_raid_degraded=1`. After the rules' one-minute hold time, Prometheus marked `DiskLatencyHigh` and `RAIDDegraded` as firing. [Alertmanager's API response](alert-firing.json) showed both active with receiver `page`. The test metrics were removed; a later check found no active alerts. This exercised rule evaluation and routing, but the `page` receiver has no delivery integration because no on-call destination was supplied.

## Mac-run Ansible, October 20, 2026

An isolated Python 3.12 environment on the Mac used `ansible-core==2.19.3`. Key-based SSH as `ansible` and passwordless sudo were checked before the run. The syntax check passed. Check mode predicted an Alertmanager `group_by` change to the existing `host` label and its restart handler; the label was present on both scrape targets.

| Run | Result |
| --- | --- |
| [Check mode and diff](mac-check-run.txt) | `ok=28 changed=2 unreachable=0 failed=0` |
| [Apply](mac-apply-run.txt) | `ok=28 changed=2 unreachable=0 failed=0` |
| [Repeat](mac-second-run.txt) | `ok=27 changed=0 unreachable=0 failed=0` |

The [post-run health check](mac-health.md) found all eight expected services active, both scrape targets up, `libvirt_up=1`, valid alert rules and Alertmanager configuration, and no active alerts. The [KVM readiness check](kvm-host-validation.txt) passed for `/dev/kvm`, guest networking, and cgroups. It did not establish PCI passthrough or secure guest support.

This snapshot only covers the host setup. The later KVM guests, three-replica Ceph lab, and guest-failure drill are recorded separately in the [Ceph report](../docs/ceph-lab.md). The [incident response](../docs/incident-response.md), [HA design](../docs/architecture.md), and [log analysis](../docs/log-analysis.md) are written deliverables; the HA targets were not measured across independent hosts.
