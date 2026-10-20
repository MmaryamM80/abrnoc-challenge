# GitHub Actions for the KVM host

The workflow in `.github/workflows/host.yml` checks the Ansible inventory and playbook syntax on every push to `main` and on pull requests. It does not contact the server for those events. Server access is available only through a manual **Run workflow** dispatch from `main`:

- `check` connects with SSH and runs the host playbook in Ansible check mode.
- `apply` runs the same check, applies the host playbook, repeats it to require `changed=0`, and verifies libvirt.

The server job uses the GitHub environment named `server`. Configure its protection rules and secrets before using the manual job. It calls `site.yml` without a Ceph tag, so it applies only the host roles. Ceph stages are manual commands in the [Ansible run guide](ansible-operations.md).

## One-time setup

1. Create a dedicated Ed25519 SSH key for the Actions runner. Add **only its public key** to `/home/ansible/.ssh/authorized_keys` on `104.194.148.88`. Confirm key-only login works before removing or changing any existing key.
2. In the repository, open **Settings → Environments → New environment**, name it `server`, and restrict deployment branches to `main`. Add required reviewers if the repository plan supports them. A reviewer must approve each manual run before the runner receives environment secrets.
3. Add these **environment secrets** under `server`:

   | Secret | Value |
   | --- | --- |
   | `SERVER_SSH_PRIVATE_KEY` | Complete private half of the dedicated Actions SSH key, including its header and footer. |
   | `SERVER_KNOWN_HOSTS` | A trusted `104.194.148.88 ssh-ed25519 ...` host-key line. Verify its fingerprint out of band before adding it. |
   | `ADMIN_PUBLIC_KEY` | The operator public key that the `host_access` role should manage, in OpenSSH one-line format. |

   Do not put any of these values in a commit, workflow file, issue, or Actions variable. The public key remains an environment secret here because the public repository must not publish the operator key. Do not use the repository deploy key for server login; the keys have separate jobs.
4. Open **Actions → Validate and deploy virtualization host → Run workflow** on branch `main`. Run `check`, read its result, then run `apply` if the proposed host changes are expected. `apply` also repeats the playbook to verify idempotence.

On a new server, complete the bootstrap and firewall review in the [Ansible run guide](ansible-operations.md) first. This workflow assumes the `ansible` account already has key-only SSH and passwordless sudo. GitHub-hosted runners have changing source IPs, so this workflow is suitable for the supplied lab host only while its SSH access policy allows those runners. For a restricted production network, use a private runner or a controlled VPN route.

## Validation and scope

The workflow pins the checkout action to a full commit SHA and installs the pinned Ansible controller dependencies from `requirements-controller.txt`. The runner verifies the host identity through `known_hosts` with strict checking. Secrets are written only to temporary runner files with a restrictive umask. The access role suppresses its managed key value from Ansible output.

The GitHub environment and its secrets are account settings, not repository files. A committed workflow alone is **not** a successful server deployment. Confirm that both the GitHub validation run and a manual server run passed before marking automation operational. Actions logs in this public repository may be visible to others; review them before sharing links.
