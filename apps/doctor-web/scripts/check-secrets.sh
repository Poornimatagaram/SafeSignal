#!/usr/bin/env bash
# Fails if anything key-like is in tracked source or in the built bundle.
# Run before every commit and after every build: npm run check:secrets
set -euo pipefail
cd "$(dirname "$0")/.."

PATTERN='(tvly-[A-Za-z0-9_-]{10,}|sk-ant-[A-Za-z0-9_-]{10,}|(api[_-]?key|secret|token|promo|coupon)["'\'' ]*[:=]["'\'' ]*[A-Za-z0-9_-]{12,})'
# A server-only key must never be VITE_-prefixed: Vite inlines VITE_* into the browser bundle.
VITE_KEY='VITE_[A-Z_]*(KEY|SECRET|TOKEN)'

hits=$(grep -RIinE --exclude-dir=node_modules --exclude-dir=.git --exclude='check-secrets.sh' --exclude='.env*' \
  -e "$PATTERN" -e "$VITE_KEY" src scripts index.html .env.example dist 2>/dev/null || true)

if [ -n "$hits" ]; then
  echo "Possible secret found (values hidden):"
  echo "$hits" | cut -d: -f1,2 | sort -u
  exit 1
fi
echo "check-secrets: clean"
