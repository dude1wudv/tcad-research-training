#!/bin/bash
# Run as root once from a trusted VMware console; no passwords accepted or stored.
set -euo pipefail
if [ "$(id -u)" -ne 0 ] || [ "$#" -ne 2 ]; then
    echo 'Usage: sudo bash guest-bootstrap.sh USER PUBLIC_KEY_FILE' >&2
    exit 2
fi
user=$1
key=$2
home=$(getent passwd "$user" | cut -d: -f6)
[ -n "$home" ] && [ -d "$home" ]
ssh-keygen -l -f "$key" >/dev/null
install -d -m 700 -o "$user" -g "$(id -gn "$user")" "$home/.ssh"
touch "$home/.ssh/authorized_keys"
while IFS= read -r line; do
    if ! grep -qxF "$line" "$home/.ssh/authorized_keys"; then
        printf '%s\n' "$line" >> "$home/.ssh/authorized_keys"
    fi
done < "$key"
chown "$user:$(id -gn "$user")" "$home/.ssh/authorized_keys"
chmod 600 "$home/.ssh/authorized_keys"
restorecon -R "$home/.ssh" 2>/dev/null || true
systemctl enable --now NetworkManager
nmcli networking on
nmcli device set ens33 managed yes
nmcli connection modify ens33 connection.autoconnect yes
nmcli connection up ens33
systemctl enable --now sshd
if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --reload
fi
install -d -m 700 -o "$user" -g "$(id -gn "$user")" "$home/research-training" "$home/research-training/runs"
printf '\nVerify and pin this host key via the trusted console:\n'
cat /etc/ssh/ssh_host_ed25519_key.pub
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
ip -4 -brief address
