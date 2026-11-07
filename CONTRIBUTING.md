# Contributing to SafeSignal

This repository is shared by three owners (company, patient, doctor) and their coding agents. The rules below keep everyone's work conflict-free and the history readable. CI enforces them on every pull request.

## 1. Ownership

Edit only the folders your area owns (`CODEOWNERS`, `README.md`). `schema/` and `packages/` are the shared contract: changes go through the company owner. In `evals/` and `data/`, write only inside your area's subfolder.

## 2. Branches

One branch per unit of work, always cut from the latest `main`:

```
<area>/<type>/<short-description>
```

| Part | Values |
| --- | --- |
| `area` | `company`, `patient`, `doctor` |
| `type` | A Conventional Commit type (section 3) |
| `short-description` | lowercase, kebab-case, 2–5 words |

Examples: `company/feat/sqlite-store`, `doctor/feat/timeline-view`, `patient/fix/egress-retry`.

Never commit directly to `main`. Never force-push a shared branch.

## 3. Commit messages: Conventional Commits 1.0.0

```
<type>(<scope>): <description>

[optional body: what and why, wrapped at 72 characters]

[optional footers: BREAKING CHANGE: ..., Refs: D-048]
```

- **Description:** imperative mood ("add", not "added"), lowercase start, no trailing period, whole subject line at most 72 characters.
- **Breaking change:** add `!` after the type/scope and a `BREAKING CHANGE:` footer. Any `schema_version` major bump is breaking.
- **Decisions:** reference decision IDs in a `Refs:` footer.
- **One logical change per commit.** Split unrelated changes into separate commits.

| Type | Use for |
| --- | --- |
| `feat` | A new capability for a user or another app |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `style` | Formatting with no behaviour change |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `build` | Dependencies, packaging, lockfiles |
| `ci` | CI configuration and scripts |
| `chore` | Maintenance that fits none of the above |
| `revert` | Reverting an earlier commit |

| Scope | Area |
| --- | --- |
| `schema`, `contract`, `service`, `company-web`, `scripts`, `docs`, `repo`, `github` | Company |
| `patient-runtime`, `patient-web` | Patient |
| `doctor-web` | Doctor |
| `evals`, `data` | Any (inside your subfolder) |

Examples:

```
feat(service): persist check-in records in SQLite
fix(doctor-web): reject envelopes whose hash does not match
feat(schema)!: rename onset values

BREAKING CHANGE: onset "1_3_days" is now "days_1_3"; schema_version 2.0.
Refs: D-052
```

## 4. Pull requests

1. Sync and branch: `git switch main && git pull && git switch -c <area>/<type>/<description>`
2. Commit in small Conventional Commits.
3. Check locally before pushing:
   - `scripts/check_ownership.sh` (only your folders changed)
   - `scripts/check_commits.sh` (commit messages follow section 3)
   - your app's tests (company: `uv run pytest -q` in `packages/contract-py` and `apps/service`; `npm test --prefix packages/contract-ts`)
4. Rebase on the latest `main` and confirm there are no conflicts: `git fetch origin && git rebase origin/main`
5. Push the branch: `git push -u origin <branch>`
6. Open a pull request into `main` (`gh pr create --base main`). The title must be a Conventional Commit subject; fill in the template.
7. CI must be green and GitHub must show "no conflicts" before merging. Merge with **Squash and merge**: `main` gets one Conventional Commit per pull request, titled after the PR.
8. Delete the branch after merging.

If `main` moves while your PR is open, rebase again (step 4) and push with `git push --force-with-lease` to your own branch only.

**Stacked pull requests.** When your work depends on a PR that is not merged yet, branch from that PR's branch and open your PR with `--base <that branch>`, so its diff shows only your commits. Once the parent PR is squash-merged, GitHub retargets your PR to `main`; then run `git rebase --onto origin/main <old parent tip> <your branch>` and push with `--force-with-lease`.
