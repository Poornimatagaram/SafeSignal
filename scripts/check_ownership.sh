#!/usr/bin/env bash
# Fails if your branch changes files outside the folders your area owns (D-044). Run before every push.
#
#   scripts/check_ownership.sh            # area taken from the branch name: <company|patient|doctor>/<topic>
#   scripts/check_ownership.sh doctor     # or name the area explicitly
#
# Checks committed changes since origin/main plus uncommitted and untracked files.
# Keep the folder lists in sync with CODEOWNERS.
set -euo pipefail

area="${1:-$(git rev-parse --abbrev-ref HEAD | cut -d/ -f1)}"
case "$area" in company|patient|doctor) ;; *)
  echo "Unknown area '$area'. Use a branch named <company|patient|doctor>/<topic> or pass the area." >&2; exit 2;;
esac

owner_of() {
  case "$1" in
    apps/patient-runtime/*|apps/patient-web/*|evals/patient/*|data/patient/*) echo patient ;;
    apps/doctor-web/*|evals/doctor/*|data/doctor/*)                           echo doctor ;;
    *)                                                                         echo company ;;
  esac
}

git fetch -q origin main 2>/dev/null || echo "warning: could not fetch origin/main; comparing with the local copy" >&2
base="$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD)"

files="$( { git diff --name-only "$base"..HEAD; git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u )"

bad=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  o="$(owner_of "$f")"
  if [ "$o" != "$area" ]; then
    echo "NOT YOURS ($o owns it): $f"
    bad=1
  fi
done <<< "$files"

if [ "$bad" -ne 0 ]; then
  echo "Ownership check failed for '$area'. Revert those files, or ask their owner to make the change." >&2
  exit 1
fi
echo "Ownership check passed for '$area' ($(printf '%s\n' "$files" | grep -c . || true) changed files)."
