# AbrNOC Senior DevOps — VirtHost exercise

## What this repository does

It turns a fresh Debian host into a small, observable KVM/libvirt host with one Ansible role. The supplied machine was a Debian 13 VM with `/dev/kvm`, 4 vCPUs, about 11 GiB RAM, and one 300 GB virtual disk. Three Ceph guests run under KVM **on that server**; the operator's Mac is only the Ansible controller. The earlier three-guest Gluster failover lab was measured and then removed at the user's request. All guests share one underlying failure domain, so the Ceph replica test does not demonstrate physical RAID, a real NVMe failure, or production multi-host HA.

The role installs KVM/libvirt, chrony, nftables, persistent journald, basic host tools, node exporter, and libvirt exporter. It creates an `ansible` administrator with the supplied **public** key, validates SSH before reloading it, disables password and root SSH access, permits SSH through the firewall, and starts the services. A local Prometheus/Alertmanager pair is installed only for this exercise, so the alerts can be tested on the one VM. For production, put monitoring outside the failure domain.

## What happened on the supplied VM

See [validation-summary](evidence/validation-summary.md) for the observed first and second run, service and SSH checks, and alert test evidence. The detailed command ledger is in [commands](docs/commands.md). No password or private key is stored here.

On October 20, 2026, the playbook was also run from the operator's Mac over key-based SSH. An isolated Python 3.12 virtual environment supplied `ansible-core==2.19.3`. The operator ran a syntax check, then `--check --diff`, then a real run, and finally a second real run to verify `changed=0`. The Mac run results are in the validation summary and its linked logs.

## Reproduce on a clean Debian VM

1. Put an administrator **public** key in `keys/admin.pub` on the operator's machine. This file is ignored by Git; keep the private key on the operator's machine as well.
2. Set `ansible/inventory.ini` to the host address and bootstrap SSH account. On first provisioning, use an account with sudo; after the role completes, use the created `ansible` user.
3. Run `ansible-playbook -i ansible/inventory.ini ansible/site.yml` from the repository root, or `cd ansible && ansible-playbook -i inventory.ini site.yml`. The role can also be run directly on a host using `inventory-local.ini`.
4. Run the same command again. A stable host should report `changed=0` and `failed=0`.
5. Check `virsh -c qemu:///system list --all`, `curl -fsS http://127.0.0.1:9100/metrics`, `curl -fsS http://127.0.0.1:9177/metrics`, and the Prometheus targets API on the host.

### Run from macOS

[The Ansible run guide](docs/ansible-operations.md) has copyable commands for the host and the Ceph guests, including the syntax check, check-mode diff, real apply, and repeat. Review the diff before applying. The final repeat should report `changed=0`. On a fresh machine, the real run verifies the effective SSH policy before reloading SSH.

The role defaults are in `ansible/roles/virt_host/defaults/main.yml`. Set `virt_host_demo_monitoring: false` for a host that uses centrally managed Prometheus and Alertmanager. Adjust the SSH port and management access policy before applying to a non-fresh production host. The firewall currently allows SSH from any source and all forwarding needed for guest networks; restrict management sources and define bridge rules for the real network design.

## Alert coverage and routing

The rules in `monitoring/virt-host-alerts.yml` cover host disk latency, md RAID degradation, load per CPU, memory pressure, NIC packet drops, exporter/libvirt failure, and crashed VMs. Packet drops are a host-side symptom, so use an independent probe to measure end-to-end loss. Critical alerts route to `page`; warnings route to `business-hours` in Asia/Tehran on Saturday through Thursday, 09:00–18:00. Outside that window, warnings go to `record-only`.

The supplied task did not include an on-call destination. The receivers therefore have no delivery integration: alerts are visible in Alertmanager, but nobody receives a page until a real webhook, email, or paging integration is configured. This is a deliberate boundary for the demonstration, not a production-ready notification path.

| Alert | Response | Reason |
| --- | --- | --- |
| DiskLatencyHigh, RAIDDegraded | Immediate page | Storage errors can affect many VMs at once and may precede data loss. |
| HostMemoryPressure, HostPacketDrops, HostExporterDown, LibvirtCollectionFailed, VMFailed | Immediate page | These can mean loss of guest availability or loss of host visibility; verify impact with an independent signal. |
| HostLoadHigh, LibvirtExporterDown | Business hours | A sustained load warning or one failed metrics endpoint deserves investigation, but is weaker evidence of customer impact on its own. Escalate immediately if accompanied by guest failures or independent probes. |

The warning route is record-only outside business hours. This is a conscious exercise policy, not a complete production escalation design; production should define ticketing and an after-hours escalation path for persistent warnings.

## Operational documents

* [Incident response](docs/incident-response.md): first 15 minutes, diagnosis, reboot criteria, recovery, and communications.
* [Ansible run guide](docs/ansible-operations.md): exact Mac commands for the host and Ceph guests.
* [HA architecture](docs/architecture.md): diagram, quorum and failure domains, capacity, backup, maintenance, and RPO/RTO targets.
* [Ceph KVM laboratory](docs/ceph-lab.md): current three-guest deployment, object read/write test, guest failure drill, safe Gluster retirement, and limitations.
* [Historical KVM HA laboratory](docs/kvm-ha-lab.md): the earlier three-guest Gluster failure drill and its measured guest-level recovery. This lab has been retired.
* [Supplied log analysis](docs/log-analysis.md): causal timeline and uncertainty around the NVMe path failure.
* [Task checklist](TASK_CHECKLIST.md): completed and open items from the PDF and follow-up requests.
* [Acceptance matrix and tradeoffs](docs/acceptance-matrix.md): every PDF requirement, its evidence, and what remains unproven.
* [October 20 recheck](docs/recheck-2026-10-20.md): live audit of all tasks, the Ceph autostart correction, and remaining limits.

## Limits

There were no tenant VMs or physical RAID devices on the supplied VM. The current Ceph lab has three nested guests, one OSD per guest, and size-three pools, but every replica resides on the same outer VM and physical failure domain. The earlier three Gluster guests and their DHCP reservations and disk files were removed. The alert exercise injected synthetic node-exporter textfile metrics for two rules and then removed them. It did not damage a disk or affect guests. The production HA targets are proposed values; meeting them requires independent hosts and measured host-failure drills.
