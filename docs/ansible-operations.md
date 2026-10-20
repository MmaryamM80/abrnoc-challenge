# Running Ansible

The controller can be macOS, Ubuntu, or Linux Mint. Ansible runs on the controller and connects to the Debian KVM host over SSH. KVM, libvirt, Ceph, and the guest disks remain on the server. Run every command below from the repository root so Ansible loads `ansible.cfg`.

## Host role layout

Without a Ceph tag, `ansible/site.yml` runs six host roles in order:

| Role | Responsibility |
| --- | --- |
| `base_system` | Host packages, time sync, persistent logging, kernel settings |
| `kvm` | KVM and libvirt packages and service |
| `host_metrics` | Node and libvirt exporters |
| `host_access` | Administrator account, public key, sudo, SSH policy |
| `host_firewall` | nftables policy and service |
| `local_monitoring` | Optional local Prometheus and Alertmanager |

Each role owns its defaults, tasks, handlers, and templates under `ansible/roles/<role>/`. Related services use task files within a role; add a new role when it needs an independent lifecycle, configuration boundary, or reuse. Both host playbooks use the same ordered role list. `virt_host_demo_monitoring: false` skips local Prometheus and Alertmanager. The lab playbook runs the host roles before creating guests. `site.yml` defines the Ceph stages after the host play; their `never` tag keeps them out of a normal host run.

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

The `host_access` role updates the matching key line and leaves other administrator keys intact. During a key rotation, verify login with the new key before deliberately removing the retired key from the host.

For a manual GitHub Actions check or apply, see the [GitHub Actions run guide](github-actions.md). The Actions runner uses its own SSH key and receives the operator public key from an environment secret; `keys/admin.pub` stays local and ignored by Git.

Set the host address and login account in `ansible/inventory.ini`. For first provisioning, that login account must already have sudo. `host_access` creates the `ansible` account. This inventory enables `virt_host_lab_network_enabled` because the supplied host already runs libvirt guests that need DNS and DHCP on `virbr0`; remove that setting for a host without this lab network. Set Ceph guest addresses in `ansible/ceph-inventory.yml`. The root `ansible.cfg` loads both inventories, although a normal host run does not contact the guests. Confirm you can log in with the key and that the host fingerprint matches an independently verified value before accepting it. For the Ceph guest inventory, verify each guest fingerprint as well; its connections go through the KVM host using SSH ProxyJump. Host key checking stays enabled.

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

Use `site.yml` for the Ceph laboratory too. The root `ansible.cfg` loads both host and guest inventories. Each tag selects only its named stage; a normal `site.yml` run still applies only the host roles.

Ceph has two roles. `ceph_guests` creates and expands the KVM guest set; `ceph_cluster` bootstraps Ceph, joins the additional nodes, sets replication, and verifies cluster health. Role defaults hold lab-specific paths, addresses, and probe names. `site.yml` selects the hosts and orders the stages behind explicit tags; the implementation stays in the roles.

| Stage | What it does |
| --- | --- |
| `ceph-bootstrap` | Create `ceph1`, then bootstrap its Ceph monitor, manager, OSD, and pools |
| `ceph-ha` | Create `ceph2` and `ceph3`, then join them to the cluster |
| `ceph-verify` | Check three healthy monitors and OSDs, then round-trip a RADOS object |

On a fresh lab, run the stages in this order. On the supplied VM, bootstrap and HA have already been applied, so use the verify stage for a current health check.

```sh
.venv/bin/ansible-playbook ansible/site.yml --syntax-check
.venv/bin/ansible-playbook ansible/site.yml --list-tasks --tags ceph-bootstrap
.venv/bin/ansible-playbook ansible/site.yml --tags ceph-bootstrap
.venv/bin/ansible-playbook ansible/site.yml --tags ceph-ha
.venv/bin/ansible-playbook ansible/site.yml --tags ceph-verify
ssh -J ansible@104.194.148.88 ansible@192.168.122.124 'sudo ceph -s'
```

The `ceph_guests` expansion stage defines `ceph2` and `ceph3`, reserves their addresses, gives each a dedicated OSD disk, and enables guest autostart. It checks available RAM before creating missing guests. The `ceph_cluster` join and replication stages add each monitor to quorum, add standby managers and OSDs, then set the two lab pools to `size 3` and `min_size 2`. They check disk serials and empty signatures before first OSD creation. Repeat the `ceph-ha` stage after applying; the target is zero changes and no failures. These are nested guests on one outer VM, so this test cannot establish host or rack failure tolerance.

To repeat the measured guest-failure drill, first confirm `sudo ceph -s` reports `HEALTH_OK`. The script writes 100 acknowledged objects, stops `ceph1`, reads them through `ceph2`, and restarts `ceph1` in its cleanup path. Run it with the same Python environment used for Ansible:

```sh
.venv/bin/python scripts/ceph-ha-drill.py --output evidence/ceph-ha-drill-new.json
ssh -J ansible@104.194.148.88 ansible@192.168.122.125 'sudo ceph -s'
```

Wait for all placement groups to return to `active+clean` after the guest restarts. Use a new output filename for a later run so the measured sample is preserved. The raw output and prior drill are linked from [the Ceph lab report](ceph-lab.md).
