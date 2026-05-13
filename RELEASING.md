# Releasing rgevolve

Operator-facing guide for cutting a **production** release of the
rgevolve ecosystem. The day-to-day flow is **Step 1** + **Step 2**
below — most operators won't need anything else. The later sections
(*One-time setup*, *TestPyPI rehearsal*) are needed once, before the
first-ever production release.

## The lockstep invariant

rgevolve ships as ten separately installable PyPI distributions —
`rgevolve-core`, the eight matrix packages (`rgevolve.smeft.warsaw`,
`rgevolve.smeft.warsaw_up`, `rgevolve.wet.flavio`,
`rgevolve.wet.jms`, `rgevolve.wet_3.flavio`, `rgevolve.wet_3.jms`,
`rgevolve.wet_4.flavio`, `rgevolve.wet_4.jms`), and the meta package
(`rgevolve`) — but is versioned in lockstep: every release advances
all ten packages to the same `X.Y.Z`. The meta-package's
`pyproject.toml` pins each sub-package with `==X.Y.Z`, so
`pip install rgevolve==X.Y.Z` resolves to a fixed, reproducible set.

**Never release one package without the others.** The orchestrator
described below enforces this by fanning out to all ten in a single
`workflow_dispatch`.

## Cutting a release

The release flow is **draft-then-dispatch**: write release notes in
GitHub's rich-text editor as a draft, then trigger the orchestrator
from the Actions tab.

### Step 1 — Draft the release on the meta-repo

1. Open https://github.com/rgevolve/rgevolve/releases/new.
2. *Choose a tag* → type the new tag, e.g. `v0.1.2`. GitHub will
   offer *Create new tag: v0.1.2 on publish* — that's correct; the
   tag will be created by the orchestrator at the right commit.
3. *Release title*: same as the tag (e.g. `v0.1.2`).
4. *Describe this release*: write notes in the rich editor —
   highlights, breaking changes, contributors, etc.
5. Click **Save draft** at the bottom. **Do not click "Publish
   release".** Publishing the draft manually does no harm (no
   workflow listens to `release:published`), but it would force you
   to clean up before the orchestrator can run — see *Recovery*
   below.

### Step 2 — Run the orchestrator

1. Open https://github.com/rgevolve/rgevolve/actions.
2. In the left sidebar, click **Orchestrate Release**.
3. Top-right, click **Run workflow**.
4. Fill in:
   - **tag** → `v0.1.2` (must match the draft).
   - **test** → unchecked.
5. Click the green **Run workflow** button.

The orchestrator runs four sequential jobs.

## What happens

| Job                      | Purpose                                                                                          | Typical duration |
| ------------------------ | ------------------------------------------------------------------------------------------------ | ---------------- |
| `preflight`              | Derive version from tag; verify it's a valid next increment from the latest PyPI version; verify the meta draft exists and is unpublished; read its notes. | < 10 s           |
| `release-subpackages`    | For each of 9 sub-repos: `gh release create <tag>` (tag + GitHub Release), then `gh workflow run release.yml --ref <tag>` (dispatch publish). | ~30 s            |
| `wait-for-pypi`          | Poll `https://pypi.org/pypi/<dist>/<version>/json` for each of 9 sub-packages until HTTP 200.    | 2–10 min         |
| `release-meta`           | Rewrite `pyproject.toml` pins → commit + push to `main` → `gh release edit --draft=false` (publishes the draft, auto-creating the tag at the new HEAD) → `gh workflow run release.yml` to dispatch the meta publish. | ~30 s            |

The meta-repo's `release.yml` build itself runs after the orchestrator
finishes and uploads to PyPI via OIDC. Total wall time, end-to-end,
typically 5–15 minutes depending on PyPI propagation.

## Monitoring + verifying

- **Live**: the workflow run page at
  https://github.com/rgevolve/rgevolve/actions/workflows/orchestrate-release.yml
  shows the four jobs and their logs.
- **Per sub-repo**: each sub-repo's *Actions* tab shows the dispatched
  `release.yml` run; failures here surface in `wait-for-pypi` as a
  timeout.
- **GitHub Releases**: each of the 10 repos now has a release at
  `v0.1.2`. The meta-repo's release has the rich-text notes; the
  sub-repos' releases have a one-line pointer to the meta release.
- **PyPI**: each of `https://pypi.org/project/<dist>/<version>/`
  renders 200 OK.
- **End-user check**:
  ```
  pip install --dry-run rgevolve==0.1.2
  ```
  should resolve cleanly, pulling in `rgevolve-core==0.1.2` and the
  eight matrix packages at `==0.1.2`.

## Recovery

### Preflight rejects the version as "not a valid increment"

The orchestrator refuses to publish a version that isn't a strict
next-increment from the latest final version on PyPI: patch +1,
minor +1 (patch reset to 0), or major +1 (minor & patch reset to 0).
Pre-releases (`.dev`, `rc`, `.post`) are matched against their base
version. This catches fat-fingered jumps like `0.1.1 → 0.1.3` that
PyPI would happily publish (and refuse to undo).

If the failure was a typo:

1. Delete the draft on `rgevolve/rgevolve`.
2. Re-draft with the correct tag.
3. Re-run the orchestrator.

If you legitimately need to skip a version (e.g. an earlier release
was botched and you want to abandon that number), temporarily delete
the latest production tag from `rgevolve/rgevolve` so the check uses
the previous one as its reference, then re-run. Restore the tag
afterward if it still corresponds to a real PyPI release.

### A sub-package's `release.yml` failed mid-run

PyPI does not allow republishing a version. If the underlying issue is
fixable on the same version (e.g. an upload retry needed):

1. Diagnose from the sub-repo's Actions log.
2. Fix in code if needed (e.g. push a patch to the sub-repo, **not**
   bumping the version).
3. **Re-run the orchestrator** with the same tag. Idempotent guards
   make this safe — already-existing sub-releases are skipped,
   already-uploaded packages are skipped by PyPI's `skip-existing`,
   and the meta pin rewrite either no-ops (if already done) or
   completes the remaining step.

If the issue isn't fixable on the same version (e.g. a build-system
bug that produces a corrupt wheel):

1. The partially-published versions stay on PyPI as orphans — they
   cause no harm; nothing will resolve to them once the meta is at a
   higher version.
2. Delete the meta draft (it has an obsolete tag).
3. Draft a new release at the next patch (`v0.1.3`), re-run.

### You accidentally clicked "Publish release" on the draft

The meta-repo's `release.yml` has no `release:published` trigger, so
**nothing gets uploaded to PyPI** from a manual publish. You'll be
left with a published release on the meta-repo pointing at the old
`main` (no pin rewrite). To recover:

1. *Releases → v0.1.2 → Delete*.
2. `git push --delete upstream v0.1.2` (deletes the tag GitHub
   auto-created on publish).
3. Re-draft the release at *Releases → Draft a new release*.
4. Re-run the orchestrator.

### A sub-repo got a manual GitHub Release before the orchestrator ran

Same shape: no workflow auto-fires, so nothing was uploaded. To
recover:

```
gh release delete v0.1.2 --repo rgevolve/<sub> --yes --cleanup-tag
```

The orchestrator will recreate the release and tag on its next run.

## Design note — orchestrator-only publishing

All ten `release.yml` files trigger on `workflow_dispatch` **only**.
There is no `release:published` trigger on any of them. The
orchestrator is the sole path that fires a PyPI publish, on both the
meta-repo and the sub-packages.

This is intentional. It means:
- Drafting a release in the GitHub UI doesn't, by itself, publish
  anything.
- Accidentally publishing a draft is harmless.
- Manually creating a release on any sub-repo is harmless.

The trade-off is that ad-hoc single-repo releases (without going
through the orchestrator) require `gh workflow run release.yml --ref <tag>`
instead of the GitHub Release UI. For the rgevolve ecosystem, where
the only releases that should ever happen are lockstep, this is the
correct trade-off.

---

The remaining sections cover **first-time setup** and the **TestPyPI
rehearsal**. They are needed once, before the first-ever production
release (and the rehearsal also runs again after any non-trivial
change to the orchestrator). Day-to-day releases need none of this.

## One-time setup

Three pieces have to be in place before the orchestrator can run a
production release.

### `ORG_RELEASE_TOKEN` secret on `rgevolve/rgevolve`

The orchestrator runs on `rgevolve/rgevolve` but acts across all 10
lockstep repos: it pushes tags, creates GitHub Releases on the 9
sub-repos, dispatches each repo's `release.yml` via `gh workflow
run`, and commits the pin rewrite to `main`. The default
`GITHUB_TOKEN` is scoped to the current repo only. A fine-grained PAT
with explicit access to all 10 repos is needed instead.

**Create the fine-grained PAT.**

1. Open https://github.com/settings/personal-access-tokens/new.
2. *Token name*: e.g. `rgevolve-orchestrator`.
3. *Resource owner*: `rgevolve` (the org). If the dropdown doesn't
   offer `rgevolve`, you need to be added as a member of the org
   first — ask another maintainer.
4. *Expiration*: pick a duration; 1 year is reasonable. (GitHub no
   longer offers "no expiration" for fine-grained tokens; mark your
   calendar to rotate.)
5. *Repository access* → *Only select repositories* → pick all 10:
   `rgevolve-core`, `rgevolve.smeft.warsaw`, `rgevolve.smeft.warsaw_up`,
   `rgevolve.wet.flavio`, `rgevolve.wet.jms`, `rgevolve.wet_3.flavio`,
   `rgevolve.wet_3.jms`, `rgevolve.wet_4.flavio`, `rgevolve.wet_4.jms`,
   `rgevolve`.
6. *Repository permissions*:
   - **Contents**: *Read and write* — for tag pushes, the pin-rewrite
     commit, and GitHub Release creation.
   - **Actions**: *Read and write* — for `gh workflow run` to
     dispatch each repo's `release.yml`.
   - Leave all other permissions at *No access*.
7. Click **Generate token** and copy the `github_pat_…` value
   immediately (you can't view it again — only regenerate).

**Approve the PAT (org owners).** If the `rgevolve` org has
*Personal access token policies → Require approval for new
fine-grained PATs* enabled, the token is in a *Pending* state until
an org owner approves it at
https://github.com/organizations/rgevolve/settings/personal-access-tokens-pending.
If approval isn't required, skip this.

**Add the token as a repo secret.**

1. Open https://github.com/rgevolve/rgevolve/settings/secrets/actions.
2. Click **New repository secret**.
3. *Name*: `ORG_RELEASE_TOKEN` (must match the workflow exactly).
4. *Secret*: paste the `github_pat_…` value.
5. Click **Add secret**.

A common silent failure is forgetting *Actions: write* in step 6.
`gh release create` succeeds but `gh workflow run` fails with
`HTTP 403: Resource not accessible by personal access token`. If
that happens, regenerate the PAT with the missing permission and
update the secret.

### PyPI trusted publishers for all 10 packages

Each package on pypi.org needs a trusted-publisher entry pointing at
the per-repo `release.yml`. Register at
`https://pypi.org/manage/project/<dist>/settings/publishing/` →
*Add a new publisher* → **GitHub**, filling in the table below. Leave
*Environment name* blank for all ten.

| PyPI Project Name          | Owner      | Repository name            | Workflow name |
| -------------------------- | ---------- | -------------------------- | ------------- |
| `rgevolve-core`            | `rgevolve` | `rgevolve-core`            | `release.yml` |
| `rgevolve.smeft.warsaw`    | `rgevolve` | `rgevolve.smeft.warsaw`    | `release.yml` |
| `rgevolve.smeft.warsaw_up` | `rgevolve` | `rgevolve.smeft.warsaw_up` | `release.yml` |
| `rgevolve.wet.flavio`      | `rgevolve` | `rgevolve.wet.flavio`      | `release.yml` |
| `rgevolve.wet.jms`         | `rgevolve` | `rgevolve.wet.jms`         | `release.yml` |
| `rgevolve.wet_3.flavio`    | `rgevolve` | `rgevolve.wet_3.flavio`    | `release.yml` |
| `rgevolve.wet_3.jms`       | `rgevolve` | `rgevolve.wet_3.jms`       | `release.yml` |
| `rgevolve.wet_4.flavio`    | `rgevolve` | `rgevolve.wet_4.flavio`    | `release.yml` |
| `rgevolve.wet_4.jms`       | `rgevolve` | `rgevolve.wet_4.jms`       | `release.yml` |
| `rgevolve`                 | `rgevolve` | `rgevolve`                 | `release.yml` |

Repository names match the **upstream** GitHub repo names
(underscored throughout — note that PyPI's display name still uses
hyphens for the five `*_up` / `*_3` / `*_4` packages because PyPI
locked those at first upload; PEP 503 normalisation makes this
irrelevant for resolving).

### Branch protection on `rgevolve/rgevolve` `main`

The orchestrator's `release-meta` job commits the pin rewrite
directly to `main`. If `main` has branch protection that forbids
direct pushes, this push fails and the release stalls between
sub-packages being published and the meta being tagged — recoverable
but messy.

Pick one:

- **Option A — no branch protection on `main`.** Simplest;
  appropriate for a sole maintainer or a trusted team. Open
  https://github.com/rgevolve/rgevolve/settings/branches and delete
  any rule for `main`.
- **Option B — branch protection with PAT bypass.** Open
  https://github.com/rgevolve/rgevolve/settings/branches → edit the
  `main` rule. Under *Restrict who can push to matching branches* /
  *Bypass list*, add the account that owns `ORG_RELEASE_TOKEN`.
  Direct human pushes still go through the rule; the orchestrator's
  push bypasses it.
- **Option C — branch protection with a GitHub Apps bypass.** Only
  if Options A/B are unacceptable for policy reasons.

Test the choice by running the first production release (below) and
confirming the `release-meta` job's `git push` succeeds.

## TestPyPI rehearsal

Before the first-ever production release — and again after any
non-trivial change to `orchestrate-release.yml` — run the full
lockstep against TestPyPI. It proves the fan-out, polling, and pin
rewrite end-to-end without burning a real PyPI version.

### Prerequisites

- **`ORG_RELEASE_TOKEN`** configured per *One-time setup* above.
- **TestPyPI trusted publishers registered for all 10 packages.**
  Same shape as the production table; URL is
  `https://test.pypi.org/manage/project/<dist>/settings/publishing/`.
- **All WP2 code pushed upstream.** Each repo's `release.yml` plus
  the meta-repo's new files must be on `main`.

### Step 1 — Pick a rehearsal version

Use a PEP 440 developmental pre-release distinct from any future real
release, e.g. `v0.1.2.dev0`. `setuptools-scm` on a tagged commit
produces a clean `0.1.2.dev0` with no local `+gHASH` segment, which
TestPyPI accepts. TestPyPI artifacts are permanent — bump the
trailing number (`v0.1.2.dev1`, …) for repeat rehearsals.

### Step 2 — Draft a rehearsal release

Same flow as for a production release (see *Cutting a release → Step
1* above). At https://github.com/rgevolve/rgevolve/releases/new, set
tag `v0.1.2.dev0`, write any notes you want (rehearsal-flavoured —
they'll show on the GitHub release page only), and click **Save
draft**. Test mode uses the same draft-lookup logic as production, so
the draft is required.

### Step 3 — Trigger the orchestrator

1. https://github.com/rgevolve/rgevolve/actions → *Orchestrate
   Release* → **Run workflow**.
2. Fill in:
   - **tag** → `v0.1.2.dev0` (must match the draft).
   - **test** → **ticked** (the key difference from production).
3. Click **Run workflow**.

### Step 4 — Monitor

| Job                      | What to look for                                                                                                              | Typical duration |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| `preflight`              | "Looking up draft 'v0.1.2.dev0' on rgevolve/rgevolve…" + isDraft check passes; version derived as `0.1.2.dev0`.                | < 10 s           |
| `release-subpackages`    | For each of 9 sub-repos: "created release …" + "dispatched release.yml … (TestPyPI)."                                         | ~30 s            |
| `wait-for-pypi`          | "Polling https://test.pypi.org/pypi/&lt;dist&gt;/0.1.2.dev0/json …" followed by "200 (attempt N)" for each of 9 dist names.   | 2–10 min         |
| `release-meta`           | "Published draft v0.1.2.dev0 on rgevolve/rgevolve …" then "Dispatched release.yml … (TestPyPI)." Pin-rewrite steps are skipped (test mode). | < 30 s           |

The meta-repo's `release.yml` build runs *after* the orchestrator
itself finishes; watch it at
https://github.com/rgevolve/rgevolve/actions/workflows/release.yml.

### Step 5 — Verify on TestPyPI

For each of the 10 distributions, open
`https://test.pypi.org/project/<dist>/0.1.2.dev0/` and confirm 200 OK
with the right version. The meta package's dependencies will still
show the **old** pins (`==0.1.1` or whatever current main says) — in
test mode the orchestrator skips the pin rewrite, since meta's pins
reference production-PyPI versions that may not exist on TestPyPI.

Also confirm the GitHub side: the meta-repo's draft is now
**published** (Releases page shows `v0.1.2.dev0` with your rehearsal
notes), and each of the 9 sub-repos has a release at the same tag
with the one-line pointer note.

### Step 6 — Cleanup (optional)

TestPyPI artifacts persist permanently — that's fine. To tidy up
GitHub Releases + tags across all 10 repos:

```bash
TAG=v0.1.2.dev0
for repo in rgevolve-core \
            rgevolve.smeft.warsaw rgevolve.smeft.warsaw_up \
            rgevolve.wet.flavio rgevolve.wet.jms \
            rgevolve.wet_3.flavio rgevolve.wet_3.jms \
            rgevolve.wet_4.flavio rgevolve.wet_4.jms \
            rgevolve; do
  gh release delete "$TAG" --repo "rgevolve/$repo" --yes --cleanup-tag || true
done
```

### Rehearsal failure modes & remedies

| Symptom                                                                       | Cause                                                                                            | Fix                                                                                                                                                                                |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `preflight` fails: "tag must start with 'v'"                                  | Typed `0.1.2.dev0` (no leading `v`) in the `tag` input.                                          | Re-run with `v0.1.2.dev0`.                                                                                                                                                         |
| `preflight` fails: "No release 'v0.1.2.dev0' on rgevolve/rgevolve"            | You skipped Step 2 — no draft exists with this tag.                                              | Draft a release at https://github.com/rgevolve/rgevolve/releases/new with tag `v0.1.2.dev0` and **Save draft**, then re-run.                                                       |
| `preflight` fails: "release is already published … operates on drafts"        | The release exists but isn't a draft (e.g. you clicked *Publish release* by accident).           | *Releases → v0.1.2.dev0 → Delete*, then `git push --delete upstream v0.1.2.dev0` to remove the tag GitHub auto-created on publish; re-draft; re-run.                               |
| `release-subpackages` fails: `HTTP 401` / `403` from `gh release create`      | `ORG_RELEASE_TOKEN` missing, expired, or lacks `contents: write` on the failing repo.            | Regenerate PAT with `contents: write` + `actions: write` on all 10 repos; update the secret.                                                                                       |
| `release-subpackages` fails: `HTTP 422` from `gh workflow run`                | Tag exists but workflow doesn't on that ref, or `actions: write` missing on the PAT.             | Confirm `release.yml` is on `main` of the failing repo; check the PAT scope.                                                                                                       |
| `wait-for-pypi` times out on a dist                                           | That sub-repo's `release.yml` failed (build error, OIDC mismatch, etc.).                         | Open the failing sub-repo's *Actions* tab → inspect the `release.yml` run for the rehearsal tag.                                                                                   |
| `release.yml` fails: `Trusted publishing exchange failure: invalid-publisher` | TestPyPI publisher entry mismatched (Owner / Repository / Workflow).                             | Open `https://test.pypi.org/manage/project/<dist>/settings/publishing/` and verify `Owner: rgevolve`, `Repository: <dist>`, `Workflow: release.yml`, *Environment*: blank.          |
| `release.yml` fails: `Refusing to publish non-final version`                  | `test` input was unticked but a `.dev` / `+local` version slipped through.                       | Re-run with `test` ticked.                                                                                                                                                         |
| Sub-package on TestPyPI with version `0.0.0` or `…+gHASH`                     | `actions/checkout` ran shallow; `setuptools-scm` couldn't see the tag.                           | `fetch-depth: 0` is set in `release.yml`. If altered, restore.                                                                                                                     |
