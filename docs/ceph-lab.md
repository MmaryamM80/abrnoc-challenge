# Ceph on the supplied KVM server

## The setup

The Mac runs Ansible and holds the operator's SSH key. Ceph runs on the supplied Debian server, inside three KVM guests named `ceph1`, `ceph2`, and `ceph3`. They use the libvirt NAT addresses `192.168.122.124` through `.126`. Each guest has its own 8 GiB virtual OSD disk. The boot images and OSD disks live under `/var/lib/libvirt/images/abrnoc-ceph-lab` on the server. The guests start automatically with libvirt.

This is a useful test of Ceph quorum and replication, but all three guests depend on one outer VM and its single virtual disk. A failure of that VM, its storage, or its hypervisor takes out every replica. There is no fencing or VM placement controller.

## How it was built

`ceph1` was first built and checked as a single-node Ceph lab. Its original object round trip is saved in [the first verification output](../evidence/ceph-final-validation.txt). The [host playbook](../ansible/ceph-ha-host.yml) then created `ceph2` and `ceph3` with distinct OSD disks and DHCP reservations. The [node playbook](../ansible/ceph-ha-node.yml) added their monitors one at a time, joined their managers, initialized their OSDs, and set `.mgr` and `lab-objects` to `size 3` and `min_size 2`.

The exact Mac commands, including syntax checks and repeat runs, are in [Running Ansible from the Mac](ansible-operations.md). The guest inventory uses SSH ProxyJump through the KVM host. The playbook checks each expected IP address and disk serial before provisioning an OSD, and does not reformat an existing OSD on a repeat run. Ceph keyrings stay on the guests and are masked in Ansible output.

The Debian `ceph-mgr` package version `18.2.7+ds-1+deb13u1` hit a Python subinterpreter issue while loading modules. The node playbook applies a version-scoped `python3-crypt-r` workaround and disables the unused `restful` module. A startup crash in the unused `nfs` manager module was inspected in [its crash record](../evidence/ceph-mgr-crash-2026-10-20.json); the playbook now disables it. A later manager restart also logged an `AttributeError` from the `volumes` module; [that crash record](../evidence/ceph-mgr-volumes-crash-2026-10-20.json) is preserved. `volumes` is listed as an always-on module, so the NFS workaround does not cover it. Both inspected crash entries were archived after the managers were running again. Check for new crash entries after any manager restart or package upgrade; the package compatibility issue needs a lasting upstream or package fix.

## What the tests establish

The cluster had three monitors in quorum, three OSDs `up` and `in`, one active manager and two standbys. Both pools had three replicas, and 33 placement groups were `active+clean`. The [final status capture](../evidence/ceph-ha-health-2026-10-20.txt) records those counts and the guests' running state. In [the guest-failure drill](../evidence/ceph-ha-drill-2026-10-20.json), I wrote and confirmed 100 objects, stopped `ceph1`, and read all 100 from `ceph2` with no missing or changed objects. The first successful read was observed 27.413 seconds after the stop command began. The probe made one successful attempt, so this is the time of first observation, not a measured outage duration or RTO. The script restarted `ceph1` afterward. This tests one nested guest failure; it does not measure application recovery, tenant VM reboot, physical-host failure, or cross-host RPO/RTO.

The earlier Gluster lab was removed after the Ceph boot image was moved off its old backing directory. The [retirement playbook](../ansible/retire-gluster-lab.yml) removed only `ha1`, `ha2`, and `ha3`, their DHCP reservations, and known disk files. The [retirement output](../evidence/gluster-retirement.txt) and [verification](../evidence/retirement-verification.txt) record what was removed. The earlier [Gluster failure drill](kvm-ha-lab.md) remains historical evidence; those guests are no longer running.

For production, place Ceph OSDs and monitors on independent physical hosts and failure domains, add fencing and a workload placement controller, and measure recovery with the intended applications and backups. The proposed values in the [architecture](architecture.md) remain targets until that test is run.
