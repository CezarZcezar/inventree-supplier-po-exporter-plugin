#!/usr/bin/env bash
# Copy the plugin into the InvenTree plugin directory of the local docker deployment
# and restart the server and worker.
#
# Usage: ./deploy.sh [path to docker compose directory]   (default: parent directory)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="${1:-$(dirname "$HERE")}"
TARGET="$COMPOSE_DIR/inventree-data/plugins/supplier_po_exporter"

echo "Deploying to $TARGET"
mkdir -p "$TARGET"
rsync -a --delete --delete-excluded \
    --exclude '__pycache__' --exclude 'tests' \
    "$HERE/inventree_supplier_po_exporter/" "$TARGET/"

cd "$COMPOSE_DIR"
docker compose restart inventree-server inventree-worker
echo "Done."
