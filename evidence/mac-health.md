# Health check after Mac-run host Ansible

Checked on October 20, 2026, after the unchanged repeat run. These are host checks from before the KVM guests were added.

| Check | Observation |
| --- | --- |
| `systemctl is-active` for chrony, nftables, rsyslog, libvirtd, node exporter, libvirt exporter, Prometheus, and Alertmanager | All eight services were `active`. |
| `virsh -c qemu:///system list --all` | Command succeeded; the guest list was empty at this point. |
| `promtool check rules /etc/prometheus/virt-host-alerts.yml` | `SUCCESS: 9 rules found` |
| `amtool check-config /etc/prometheus/alertmanager.yml` | `SUCCESS`; three receivers. |
| `promtool query instant http://127.0.0.1:9090 up` | `node=1` and `libvirt=1`; both series had `host="debian-London-12gb"`. |
| `promtool query instant http://127.0.0.1:9090 libvirt_up` | `libvirt_up=1` |
| `curl -fsS http://127.0.0.1:9093/api/v2/alerts` | `[]`; no active alerts remained. |

Key-based SSH as `ansible` and passwordless sudo worked before the run. During apply and repeat, the role checked the effective SSH settings: `permitrootlogin no`, `passwordauthentication no`, and `kbdinteractiveauthentication no`.
