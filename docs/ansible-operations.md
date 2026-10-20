# Running Ansible

The controller can be macOS, Ubuntu, or Linux Mint. Ansible runs on the controller and connects to the Debian KVM host over SSH. KVM, libvirt, Ceph, and the guest disks remain on the server. Run every command below from the repository root so Ansible loads `ansible.cfg`.

The host playbook runs four roles in order:

| Role | Responsibility |
| --- | --- |
| `host_baseline` | Base packages, NTP, journald, sysctl, and nftables. |
| `virt_host` | KVM/libvirt, node exporter, and libvirt exporter. |
| `host_access` | Administrator account, authorized key, sudo, and validated SSH policy. |
| `host_monitoring` | Optional local Prometheus and Alertmanager demonstration. |

Defaults, tasks, handlers, and templates live with their owning role under `ansible/roles/`. The lab host playbook imports the same roles before creating its guests. `virt_host_demo_monitoring: false` skips the optional monitoring role.

## Prepare the controller

Use Python 3.11–3.13 and OpenSSH. On Ubuntu or Linux Mint, install the controller prerequisites first:

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip openssh-client
```

Check `python3 --version` before creating the environment. The pinned Ansible version needs Python 3.11 or newer on the controller. On an older Ubuntu or Linux Mint release, install a supported Python separately or use `uv venv --python 3.12 .venv` and `uv pip install --python .venv/bin/python -r requirements-controller.txt`. On macOS, use a Python 3.11–3.13 installation with `venv` available. Then, on any of the three systems:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-controller.txt
.venv/bin/ansible --version
.venv/bin/ansible-config dump --only-changed
```

If your macOS Python installation lacks `venv` or `pip`, `uv venv --python 3.12 .venv` followed by `uv pip install --python .venv/bin/python -r requirements-controller.txt` is an equivalent setup.

Create `keys/admin.pub` locally with the administrator **public** key. It is ignored by Git. Keep its private counterpart outside this repository. Ansible uses your SSH agent or normal OpenSSH identities for connections; if you need a specific private key, pass `--private-key ~/.ssh/your_key` to each `ansible-playbook` command or configure it in `~/.ssh/config`. Never put private keys, passwords, or Ceph keyrings in this repository.

The access role updates the matching key line and leaves other administrator keys intact. During a key rotation, verify login with the new key before deliberately removing the retired key from the host.

For a manual GitHub Actions check or apply, see the [GitHub Actions run guide](github-actions.md). The Actions runner uses its own SSH key and receives the operator public key from an environment secret; `keys/admin.pub` stays local and ignored by Git.

Set the host address and login account in `ansible/inventory.ini`. For first provisioning, that login account must already have sudo. The access role creates the `ansible` account. This inventory enables `virt_host_lab_network_enabled` because the supplied host already runs libvirt guests that need DNS and DHCP on `virbr0`; remove that setting for a host without this lab network. Confirm you can log in with the key and that the host fingerprint matches an independently verified value before accepting it. For the Ceph guest inventory, verify each guest fingerprint as well; its connections go through the KVM host using SSH ProxyJump. Host key checking stays enabled.

## Check and apply the host roles

```sh
ssh -o BatchMode=yes ansible@104.194.148.88 true
.venv/bin/ansible-inventory --list
.venv/bin/ansible-playbook ansible/site.yml --syntax-check
.venv/bin/ansible-playbook ansible/site.yml --check --diff
.venv/bin/ansible-playbook ansible/site.yml --diff
.venv/bin/ansible-playbook ansible/site.yml
ssh ansible@104.194.148.88 'sudo virsh -c qemu:///system list --all'
```

Use the account you configured in the inventory for the SSH preflight. Read the check-mode diff before applying. Check mode cannot prove a newly installed SSH policy; the real run validates the effective `sshd` configuration before its reload. When first bootstrapping with a different account, confirm a separate login as the newly created `ansible` user before ending the bootstrap session. The second real run should report `changed=0`, `failed=0`, and `unreachable=0`. The original macOS execution is recorded in [the validation summary](../evidence/validation-summary.md).

## Ceph laboratory on this server

The existing `ceph1` guest was created with `ansible/ceph-host.yml` and bootstrapped with `ansible/ceph-node.yml`. For the current three-guest laboratory, use these playbooks in order:

```sh
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/ceph-ha-host.yml --syntax-check
.venv/bin/ansible-playbook -i ansible/ceph-inventory.yml ansible/ceph-ha-node.yml --syntax-check
.venv/bin/ansible-playbook -i ansible/inventory.ini ansible/ceph-ha-host.yml
.venv/bin/ansible-playbook -i ansible/ceph-inventory.yml ansible/ceph-ha-node.yml
ssh -J ansible@104.194.148.88 ansible@192.168.122.124 'sudo ceph -s'
```

`ceph-ha-host.yml` defines `ceph2` and `ceph3`, reserves their addresses, gives each a dedicated OSD disk, and enables guest autostart. It checks available RAM before creating missing guests. `ceph-ha-node.yml` joins each monitor to quorum, adds a standby manager and an OSD, then sets the two lab pools to `size 3` and `min_size 2`. It checks the disk serial and empty signatures before first OSD creation. Repeat both playbooks after applying; the target is zero changes and no failures. These are nested guests on one outer VM, so this test cannot establish host or rack failure tolerance.

To repeat the measured guest-failure drill, first confirm `sudo ceph -s` reports `HEALTH_OK`. The script writes 100 acknowledged objects, stops `ceph1`, reads them through `ceph2`, and restarts `ceph1` in its cleanup path. Run it with the same Python environment used for Ansible:

```sh
.venv/bin/python scripts/ceph-ha-drill.py --output evidence/ceph-ha-drill-new.json
ssh -J ansible@104.194.148.88 ansible@192.168.122.125 'sudo ceph -s'
```

Wait for all placement groups to return to `active+clean` after the guest restarts. Use a new output filename for a later run so the measured sample is preserved. The raw output and prior drill are linked from [the Ceph lab report](ceph-lab.md).
