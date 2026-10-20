# Operator walkthrough and command ledger

This page explains what was done on the supplied VM and why. The exact run results and alert observations are in [validation-summary](../evidence/validation-summary.md). Commands below are reproducible examples; the private SSH key and the original password are intentionally absent.

## 1. Establish the starting point

The host accepted the provided root credentials for the first connection. Before changing SSH or firewall settings, I checked its OS, kernel, CPU virtualization support, memory, disk layout, network, and existing services. It was a Debian 13.7 virtual machine with `/dev/kvm`, four vCPUs, about 11 GiB RAM, and one 300 GB `vda` disk. There was no physical NVMe device, md RAID array, or tenant VM to operate on.

I placed my **public** SSH key on the host and verified key-based access before starting the role. This allowed the role to create a named administrator and turn off root/password SSH without losing the management path.

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@104.194.148.88
ssh -o BatchMode=yes root@104.194.148.88 'id -un'
```

## 2. Run provisioning

The project was copied to `/opt/abrnoc-virt-host` on the VM. Debian's `ansible-core` and `prometheus-libvirt-exporter` packages were installed as bootstrap dependencies. The playbook was syntax-checked before its first local run on the VM.

```sh
cd /opt/abrnoc-virt-host/ansible
ansible-playbook --syntax-check -i inventory-local.ini site.yml
ansible-playbook -i inventory-local.ini site.yml
```

The role installs KVM/libvirt and host utilities, creates the `ansible` administration user with the operator's public key, validates `sshd` and nftables configuration, and starts the services. It sets persistent journald storage, conservative kernel settings, chrony, a restrictive inbound firewall, node exporter, and libvirt exporter. Prometheus and Alertmanager are local demonstration services for this one-host exercise.

## 3. Verify access and service health

These checks confirm that the intended administration path works, that libvirt answers, and that the exporters and monitoring processes are reachable on the host:

```sh
ssh -o BatchMode=yes ansible@104.194.148.88 'id -un; sudo -n virsh -c qemu:///system list --all'
sudo systemctl is-active chrony nftables rsyslog libvirtd prometheus-node-exporter prometheus-libvirt-exporter prometheus prometheus-alertmanager
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication'
sudo nft list ruleset
curl -fsS http://127.0.0.1:9100/metrics
curl -fsS http://127.0.0.1:9177/metrics
curl -fsS http://127.0.0.1:9090/api/v1/targets
```

The exporter ports and Prometheus/Alertmanager bind to loopback for this exercise. No monitoring web port is opened in the firewall. The SSH port remains 22; a production build should restrict its source addresses to a management network.

### Problems found and corrected during verification

The first deployment reached the Alertmanager handler and failed. Its time interval used a weekday range crossing the end of the week, which this Alertmanager version rejected. The single public-IP VM also had no private address suitable for Alertmanager's gossip listener. I changed the interval to explicit weekday names and disabled clustering for this one-node demonstration, then validated the configuration with `amtool` and reran the playbook successfully.

A later functional check found that `sshd -T` still reported `passwordauthentication yes`: cloud-init's `50-cloud-init.conf` was read before our `50-virt-host.conf`, and OpenSSH kept the first value. The role now places its policy in `00-virt-host.conf`, removes its old drop-in, and asserts the **effective** SSH settings. I verified the new `ansible` login before and after SSH reload and confirmed a root key login is refused.

The libvirt exporter process was running but reported `libvirt_up 0`. Its `prometheus` service account could not open the libvirt management socket. The role now adds that account to the `libvirt` group and restarts the exporter; querying as `prometheus` and the metric both succeed. This check is why service `active` and scrape `up` alone were insufficient.

## 4. Prove repeatability

Run the same playbook a second time and inspect the `PLAY RECAP`. `changed=0` with `failed=0` is the idempotency acceptance criterion.

```sh
cd /opt/abrnoc-virt-host/ansible
sudo -n ansible-playbook -i inventory-local.ini site.yml
```

### Follow-up run from the operator's Mac

On October 20, 2026, I used an isolated `.venv` with Python 3.12 and `ansible-core==2.19.3` on macOS. The inventory points at the host's `ansible` account and its existing private-key path; no password was placed in the repository or command line. I checked key-based SSH and passwordless sudo first, ran a syntax check and `--check --diff`, inspected the diff, applied the role, and ran it again for idempotence. The exact outputs are saved in [`mac-check-run.txt`](../evidence/mac-check-run.txt), [`mac-apply-run.txt`](../evidence/mac-apply-run.txt), and [`mac-second-run.txt`](../evidence/mac-second-run.txt).

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ansible-core==2.19.3
cd ansible
../.venv/bin/ansible-playbook --syntax-check -i inventory.ini site.yml
../.venv/bin/ansible-playbook -i inventory.ini site.yml --check --diff
../.venv/bin/ansible-playbook -i inventory.ini site.yml --diff
../.venv/bin/ansible-playbook -i inventory.ini site.yml
```

The role's read-only `sshd -t` and `sshd -T` checks now execute during Ansible check mode. The effective-policy assertion is deferred if a check-mode run predicts an SSH drop-in change; the real run verifies the resulting policy before the SSH handler reloads the service.

### Current Ceph guest and retired Gluster lab

The Mac also ran the [Ceph host](../ansible/ceph-host.yml) and [Ceph node](../ansible/ceph-node.yml) playbooks against the supplied server and its nested `ceph1` guest. The guest has a dedicated 8 GiB OSD disk. The [verification playbook](../ansible/ceph-verify.yml) checks daemon state, placement groups, and a RADOS object write/read/byte comparison. After moving the Ceph image dependency out of the former Gluster directory, the [retirement playbook](../ansible/retire-gluster-lab.yml) removed only the known `ha1`/`ha2`/`ha3` lab resources. See the [Ceph report](ceph-lab.md) for commands and the limits of this single-node test.

## 5. Prove alert flow without harming storage

The two critical storage rules have normal host-metric expressions and explicit synthetic test series. A textfile collector can expose those series temporarily. Prometheus must move the rules through their one-minute `for` duration; then Alertmanager should show both as firing and routed to `page`.

```text
abrnoc_test_disk_latency_high 1
abrnoc_test_raid_degraded 1
```

After observing the alerts, remove the test metric file and confirm they resolve. This checks the monitoring path without inducing an NVMe outage or degrading an array. The `page` receiver has no delivery destination because none was provided, so it records and groups the alert but does not notify an on-call person.
