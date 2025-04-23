#!/bin/bash
# LXC container setup script for Spring '83 server
# This script creates and configures a Debian 12 LXC container on Proxmox
# to run the Spring '83 server behind Caddy

set -euo pipefail

# Configuration
CONTAINER_ID=1083  # Container ID
CONTAINER_NAME="spring83"  # Container name
STORAGE="local-lvm"  # Storage location
MEMORY=512  # Memory in MB
CPU=1  # CPU cores
DISK=8  # Disk size in GB
HOSTNAME="spring83"  # Hostname
DOMAIN="${HOSTNAME}.local"  # Domain
IP_ADDRESS="192.168.1.83/24"  # IP address
GATEWAY="192.168.1.1"  # Gateway
DNS_SERVER="1.1.1.1"  # DNS server

# Check if we have the required permissions
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# Check if pct command exists
if ! command -v pct &> /dev/null; then
    echo "pct command not found. Are you running this on a Proxmox host?" >&2
    exit 1
fi

# Create the container
echo "Creating LXC container..."
pct create "$CONTAINER_ID" "local:vztmpl/debian-12-standard_12.0-1_amd64.tar.zst" \
    --arch amd64 \
    --cores "$CPU" \
    --memory "$MEMORY" \
    --swap 0 \
    --storage "$STORAGE" \
    --rootfs "$STORAGE:$DISK" \
    --net0 "name=eth0,bridge=vmbr0,ip=$IP_ADDRESS,gw=$GATEWAY" \
    --hostname "$HOSTNAME" \
    --nameserver "$DNS_SERVER" \
    --ostype debian \
    --password "spring83" \
    --unprivileged 1 \
    --features nesting=0

# Start the container
echo "Starting container..."
pct start "$CONTAINER_ID"

# Wait for container to boot
echo "Waiting for container to boot..."
sleep 10

# Install required packages
echo "Installing packages..."
pct exec "$CONTAINER_ID" -- bash -c "apt-get update && \
    apt-get install -y \
    python3 python3-venv \
    caddy \
    ufw \
    curl \
    git \
    cron \
    logrotate"

# Create spring83 user
echo "Creating spring83 user..."
pct exec "$CONTAINER_ID" -- bash -c "useradd -m -r -s /bin/bash spring83"

# Create directories
echo "Creating directories..."
pct exec "$CONTAINER_ID" -- bash -c "mkdir -p /opt/spring83/boards /var/log/caddy"
pct exec "$CONTAINER_ID" -- bash -c "chown -R spring83:spring83 /opt/spring83"
pct exec "$CONTAINER_ID" -- bash -c "chmod 755 /opt/spring83"

# Set up UFW
echo "Configuring firewall..."
pct exec "$CONTAINER_ID" -- bash -c "ufw default deny incoming"
pct exec "$CONTAINER_ID" -- bash -c "ufw default allow outgoing"
pct exec "$CONTAINER_ID" -- bash -c "ufw allow 22/tcp"
pct exec "$CONTAINER_ID" -- bash -c "ufw allow 443/tcp"
pct exec "$CONTAINER_ID" -- bash -c "echo 'y' | ufw enable"

# Generate self-signed certificate (for testing)
echo "Generating self-signed certificate..."
pct exec "$CONTAINER_ID" -- bash -c "mkdir -p /etc/ssl/private"
pct exec "$CONTAINER_ID" -- bash -c "openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/spring83.key \
    -out /etc/ssl/certs/spring83.crt \
    -subj '/CN=$DOMAIN/O=Spring83/C=US'"

echo "LXC container setup complete!"
echo "Container ID: $CONTAINER_ID"
echo "Hostname: $HOSTNAME"
echo "IP Address: $IP_ADDRESS"
echo ""
echo "Next steps:"
echo "1. Deploy the Spring '83 server using 'make deploy'"
echo "2. Access the server at https://$IP_ADDRESS"