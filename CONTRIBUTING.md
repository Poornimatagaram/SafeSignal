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

**Keep `main` current.** Merge each pull request as soon as CI is green and GitHub shows no conflicts, so `main` always reflects what has been built. Prefer finishing and merging a PR before starting work that depends on it.

**Stacked pull requests (only when unavoidable).** If your work depends on a PR that is not merged yet:

1. Branch from that PR's branch and open your PR with `--base <that branch>`, so its diff shows only your commits.
2. **Before the parent PR is merged, retarget your PR to `main`** (`gh pr edit <n> --base main`). GitHub *closes* a PR whose base branch is deleted, and a closed PR cannot be retargeted.
3. After the parent is squash-merged, update your branch by merging `main` into it (`git merge origin/main`) and push normally. Do not rebase or force-push shared branches.
4. Conflicts after a squash merge are expected where your branch edited lines the parent added. If `git diff <parent's old tip> origin/main` is empty, `main` contains nothing you are missing, and your branch's version of each conflicting file is the correct result. In append-only log files, keep every entry from both sides.
