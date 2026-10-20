# Running Ansible from the Mac

The Mac is the controller. Ansible connects as `ansible` over SSH; KVM, libvirt, Ceph, and all guest disks stay on the Debian server. Run these commands from the repository root. They use a local virtual environment and your existing SSH private key. Never copy the private key or the server password into this repository.

## Prepare and inspect

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ansible-core==2.19.3
ssh -o BatchMode=yes ansible@104.194.148.88 true
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/site.yml --syntax-check
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff
```

Review the inventory, `keys/admin.pub`, and the check-mode diff before an apply. On a **new** Debian host, use a bootstrap account with sudo in `ansible/inventory.ini`; the role creates the `ansible` account. The current server already has that account and key access. Check mode cannot prove a newly installed SSH policy until the real run validates it.

## Apply and check the host

```sh
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/site.yml --diff
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/site.yml
ssh ansible@104.194.148.88 'sudo virsh -c qemu:///system list --all'
```

The second real run should end with `changed=0`, `failed=0`, and `unreachable=0`. The saved Mac run is in [the validation summary](../evidence/validation-summary.md). The host role does not build the Ceph guests; the next playbooks do.

## Ceph laboratory on this server

The existing `ceph1` guest was created with `ansible/ceph-host.yml` and bootstrapped with `ansible/ceph-node.yml`. For the **current** three-guest laboratory, use these playbooks in order:

```sh
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/ceph-ha-host.yml --syntax-check
.venv/bin/ansible-playbook -i ansible/ceph-inventory.yml ansible/ceph-ha-node.yml --syntax-check
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/ceph-ha-host.yml
.venv/bin/ansible-playbook -i ansible/ceph-inventory.yml ansible/ceph-ha-node.yml
ssh -J ansible@104.194.148.88 ansible@192.168.122.124 'sudo ceph -s'
```

`ceph-ha-host.yml` defines `ceph2` and `ceph3`, reserves their addresses, gives each a dedicated OSD disk, and enables guest autostart. It checks available RAM before creating missing guests. `ceph-ha-node.yml` joins each monitor to quorum, adds a standby manager and an OSD, then sets the two lab pools to `size 3` and `min_size 2`. It checks the disk serial and empty signatures before first OSD creation. Repeat both playbooks after applying; the target is zero changes and no failures. These are nested guests on one outer VM, so this test cannot establish host or rack failure tolerance.

To repeat the measured guest-failure drill, first confirm `sudo ceph -s` reports `HEALTH_OK`. The script writes 100 acknowledged objects, stops `ceph1`, reads them through `ceph2`, and restarts `ceph1` in its cleanup path. Run it with the same Python 3.12 environment used for Ansible:

```sh
.venv/bin/python scripts/ceph-ha-drill.py --output evidence/ceph-ha-drill-2026-10-20.json
ssh -J ansible@104.194.148.88 ansible@192.168.122.125 'sudo ceph -s'
```

Wait for all placement groups to return to `active+clean` after the guest restarts. Use a new output filename for a later run so the measured sample is preserved.

The Ceph guest inventory uses SSH ProxyJump through the host and the Mac's `~/.ssh/id_ed25519`. If your key path differs, change `ansible_ssh_private_key_file` in `ansible/ceph-inventory.yml`. Keep Ceph keyrings on the guests. The raw output and measured failure drill are linked from [the Ceph lab report](ceph-lab.md).
