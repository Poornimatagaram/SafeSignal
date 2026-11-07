#!/usr/bin/env bash
# Wipe every runtime database before a demo and after the event (Scoping Doc 26.12; D-031).
#
#   scripts/reset_all.sh           # delete var/ (service company.db + relay.db, patient.db)
#   scripts/reset_all.sh --seed    # then reseed the service with the demo program and synthetic history
#
# Stop the service and the patient runtime first. The doctor's browser database cannot be deleted from here.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
var="$root/var"

if [ -d "$var" ]; then
  find "$var" -type f \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' -o -name '*.db-journal' \) -print -delete
  find "$var" -mindepth 1 -type d -empty -delete
fi
echo "Deleted all databases under var/."
echo "Doctor browser: open the doctor web app, then DevTools > Application > Storage > Clear site data"
echo "(removes IndexedDB 'sentinel_doctor_view', including the doctor's key pair)."

if [ "${1:-}" = "--seed" ]; then
  (cd "$root/apps/service" && uv run -q python -m sentinel_service.seed)
fi
