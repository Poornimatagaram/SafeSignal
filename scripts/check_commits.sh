#!/usr/bin/env bash
# Checks that every commit on this branch (since it left origin/main) follows Conventional Commits 1.0.0
# as defined in CONTRIBUTING.md section 3. Merge commits are skipped.
#
#   scripts/check_commits.sh                      # check this branch's commits
#   scripts/check_commits.sh --title "<PR title>"  # also check a pull-request title (CI does this)
#   scripts/check_commits.sh --base <ref>          # compare with another base (default: origin/main)
set -euo pipefail

TYPES="feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
PATTERN="^(${TYPES})(\([a-z0-9-]+\))?!?: [^A-Z ].*[^. ]$"
MAX=72

base="origin/main"
title=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) base="$2"; shift 2 ;;
    --title) title="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

bad=0
check() {  # $1 = label, $2 = subject
  local subject="$2"
  if ! [[ "$subject" =~ $PATTERN ]]; then
    echo "BAD $1: \"$subject\""
    echo "    expected <type>(<scope>): <description>, type one of ${TYPES//|/, }; lowercase start; no trailing period"
    bad=1
  elif [ "${#subject}" -gt "$MAX" ]; then
    echo "BAD $1: subject is ${#subject} characters (max $MAX): \"$subject\""
    bad=1
  fi
}

git fetch -q origin main 2>/dev/null || true
merge_base="$(git merge-base HEAD "$base")"
count=0
while IFS=$'\t' read -r sha subject; do
  [ -z "$sha" ] && continue
  count=$((count + 1))
  check "commit ${sha:0:7}" "$subject"
done < <(git log --no-merges --format='%H%x09%s' "$merge_base"..HEAD)

[ -n "$title" ] && check "PR title" "$title"

if [ "$bad" -ne 0 ]; then
  echo "Commit message check failed. See CONTRIBUTING.md section 3; reword with 'git rebase -i' on your own branch." >&2
  exit 1
fi
echo "Commit message check passed ($count commits${title:+ and the PR title})."
