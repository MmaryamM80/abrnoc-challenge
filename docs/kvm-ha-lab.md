# Historical KVM high-availability laboratory (retired)

This page preserves the October 20, 2026 Gluster failure drill and its measured results. The `ha1`, `ha2`, and `ha3` guests, their DHCP reservations, and their known disk files were [removed](../evidence/gluster-retirement.txt) after the user requested Ceph on the server. The [current laboratory](ceph-lab.md) is a single Ceph guest. Reproducing the commands below would recreate the retired Gluster lab and compete with Ceph for memory.

## Scope and failure domains

The supplied machine is one Debian virtual server with nested KVM access. This historical laboratory created three **KVM guest nodes inside that one server**. It demonstrated replication, service failover, and a measured *guest* failure. It could not survive failure of the supplied server, its virtual disk, its upstream network, or its underlying hypervisor. The production multi-host RPO/RTO targets in [the architecture](architecture.md) remain separate acceptance criteria.

The task PDF permits Ceph, LINSTOR/DRBD, **or another justified solution**; it does not require GlusterFS. The production design in this repository uses Ceph RBD. GlusterFS was used only for this measured guest-failure laboratory. The host's roughly 12 GiB RAM did not support three adequately sized Ceph guests alongside this lab. A separate [single-node Ceph functional test](ceph-lab.md) now runs on the server. Ceph **failover RPO/RTO remains unmeasured**; that requires independent, adequately provisioned hosts, separate OSD devices, quorum, fencing, and a fresh failure drill.

| Component | Lab configuration |
| --- | --- |
| Hypervisor | Supplied Debian 13 VM, libvirt/KVM |
| Guest nodes | `ha1`/`.121`, `ha2`/`.122`, `ha3`/`.123`; each 1 vCPU, 1536 MiB RAM, 12 GiB sparse overlay |
| Network | libvirt `default` NAT, `192.168.122.0/24`; lab traffic and VIP stay inside the supplied host |
| Replication | GlusterFS volume `ha`, replica 3, client quorum `auto` (two of three bricks needed for writes) |
| Service | nginx serves `/mnt/ha/www/index.html` from the replicated mount |
| Failover | keepalived unicast VRRP moves `192.168.122.130` after a local mount/HTTP health failure |

## Reproduce from a macOS, Ubuntu, or Linux Mint controller

Run these from the repository root after configuring `ansible/inventory.ini` and placing the operator's public key in `keys/admin.pub`:

```sh
.venv/bin/ansible-playbook --syntax-check -i ansible/inventory.ini ansible/lab-host.yml
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/lab-host.yml
.venv/bin/ansible-playbook --syntax-check -i ansible/lab-inventory.yml ansible/lab-cluster.yml
.venv/bin/ansible-playbook -i ansible/lab-inventory.yml ansible/lab-cluster.yml
```

`lab-host.yml` enables only the lab bridge's DHCP/DNS access in the host firewall, fetches the official Debian 13 cloud image, reserves three addresses, and creates guests using cloud-init and a **public** SSH key. `lab-cluster.yml` configures the replicated storage and HTTP failover service through SSH ProxyJump. Guest private keys and passwords are never copied into the repository.

Check `virsh -c qemu:///system list --all`, `gluster volume status ha`, `gluster volume heal ha info`, `systemctl is-active keepalived`, and `curl http://192.168.122.130/` on the host or relevant guest. Repeat both playbooks to check steady-state idempotence.

## Failure drill and measurement method

Before inducing failure, write a uniquely named test file into `/mnt/ha` on the active VIP owner, `fsync` it, and verify the same hash through another guest. The RPO sample is the number of **acknowledged** test records missing on a surviving guest after the failure. Zero missing records in one drill is an observed sample, not a guarantee of zero data loss for every failure mode.

From the KVM host, run `scripts/measure-vip-rto.py --domain <active-VIP-owner>`. It first requires three successful HTTP probes, runs `virsh destroy` for that guest, and probes the VIP every 0.2 seconds with a 0.75-second request timeout. The reported outage spans the first failed probe to the first later successful probe. Its resolution is limited by the polling interval and request timeout. Also record elapsed time from the destroy command to the first successful response. Start the guest again after the drill and verify Gluster healing and all three service nodes.

The drill is intentionally destructive **only to one disposable lab guest's running state**; the guest disk persists. The test file is specifically created for this drill. A killed guest may have unacknowledged or buffered writes, so only acknowledged, synced records count toward the observed RPO.

## Observed run on October 20, 2026

The [host playbook](../evidence/kvm-lab-apply.txt) finished with `failed=0` and all three guests running. The [cluster playbook](../evidence/kvm-cluster-apply.txt) finished with `failed=0`; the three Gluster bricks were online, both peers were connected, and `cluster.quorum-type` was `auto`. All three guests served the same page. The lab VIP initially belonged to `ha2` and returned the shared page from the KVM host.

After the failure drill and guest restart, a repeat cluster run reapplied `/etc/hosts` on `ha2` because cloud-init had rewritten it during boot. A subsequent [steady-state cluster run](../evidence/kvm-cluster-steady.txt) finished with `changed=0`, `unreachable=0`, and `failed=0` on all three guests. The [repeated host run](../evidence/kvm-lab-repeat.txt) also finished with `changed=0`, `unreachable=0`, and `failed=0`.

The active guest `ha2` wrote 100 unique records to `/mnt/ha`, successfully synced both the file and containing directory, and received a successful result. Before failure, `ha1` and `ha3` each read 100 records with the same SHA-256. We then stopped `ha2` using `virsh destroy` and probed the VIP from the outer KVM host. See the [RPO sample](../evidence/kvm-rpo-sample.json) and [timestamped RTO probes](../evidence/kvm-vip-rto.json).

| Observation | Result |
| --- | --- |
| Failed guest | `ha2`, the active VIP owner |
| First failed HTTP probe after destroy started | 0.530 seconds |
| First successful HTTP probe after destroy started | **42.468 seconds** |
| Observed failed-probe interval | **41.939 seconds** |
| Acknowledged records missing on either survivor | **0 of 100** |
| Post-recovery condition | VIP served HTTP; restarted `ha2`; three bricks online; Gluster heal queue 0 on each brick; all three nodes retained the sample hash |

These are **one guest-failure sample**, not a guaranteed RPO/RTO for host loss. RPO here measures only the 100 acknowledged test records: an observed zero missing records. RTO here measures this HTTP endpoint from the KVM host: its first successful response was 42.468 seconds after the destructive command started, with the probe cadence and timeout stated above. The interval includes a period where the Gluster-backed health checks timed out on survivors; keepalived logs showed a temporary reduction in effective priority. That behavior should be tuned and remeasured before any service-level commitment. It does not validate the architecture's separate 15-minute **tenant-VM restart** target.

## Operational boundaries

- All three bricks and the VIP share one physical failure domain. Do not call this a production HA cluster or claim it meets the architecture's host-failure RPO/RTO targets.
- Gluster client quorum protects writes when only one brick is lost; two failed guests should block writes rather than accept conflicting copies. This should be verified in a separate drill before any production use.
- The VIP is reachable from the KVM host and its lab guests. External clients would need explicit routing and a different network design.
- VRRP protects this single HTTP endpoint. It does not migrate or restart arbitrary tenant VMs. Real VM HA needs independently hosted compute nodes, shared or replicated storage, fencing, and a placement controller.
- This lab has no backup copy outside the supplied machine, so replication does not protect against loss or corruption of that machine.
