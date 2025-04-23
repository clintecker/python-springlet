#!/bin/bash
# Cleanup script for Spring '83 boards
# Removes boards that are older than 22 days (TTL defined in the protocol)

set -euo pipefail

BOARDS_DIR="/opt/spring83/boards"
TTL_DAYS=22

# Find and delete files older than TTL_DAYS
find "$BOARDS_DIR" -type f -mtime +$TTL_DAYS -delete

# Log the cleanup
echo "$(date -u +"%Y-%m-%d %H:%M:%S UTC") - Cleaned up boards older than $TTL_DAYS days" \
  >> /var/log/spring83_cleanup.log