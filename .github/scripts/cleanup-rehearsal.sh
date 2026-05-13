#!/usr/bin/env bash
# Delete the rehearsal GitHub Release + tag from all 10 rgevolve repos.
#
# Use this after a TestPyPI rehearsal (see RELEASING.md → TestPyPI rehearsal
# → Step 6 — Cleanup) when you don't have the `gh` CLI installed locally.
# TestPyPI artifacts themselves are permanent and harmless; this script
# only tidies up GitHub Releases and tags.
#
# Usage:
#   export GH_TOKEN=<fine-grained PAT with contents:write on all 10 rgevolve/ repos>
#   bash .github/scripts/cleanup-rehearsal.sh v0.1.2.dev1
#   # or:   TAG=v0.1.2.dev1 bash .github/scripts/cleanup-rehearsal.sh
#
# Idempotent: missing releases/tags are skipped silently.

set -uo pipefail

TAG="${1:-${TAG:-}}"
if [ -z "$TAG" ]; then
  echo "Usage: $0 <tag>   (or set TAG=<tag>)" >&2
  echo "Example: $0 v0.1.2.dev1" >&2
  exit 2
fi
if [ -z "${GH_TOKEN:-}" ]; then
  echo "ERROR: set GH_TOKEN to a fine-grained PAT with 'contents: write' on the 10 rgevolve/ repos." >&2
  exit 2
fi

REPOS=(
  rgevolve-core
  rgevolve.smeft.warsaw
  rgevolve.smeft.warsaw_up
  rgevolve.wet.flavio
  rgevolve.wet.jms
  rgevolve.wet_3.flavio
  rgevolve.wet_3.jms
  rgevolve.wet_4.flavio
  rgevolve.wet_4.jms
  rgevolve
)

api() {
  curl -sS \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$@"
}

for repo in "${REPOS[@]}"; do
  echo "=== rgevolve/$repo ==="

  # 1. Look up the release id for this tag (if any).
  release_json=$(api "https://api.github.com/repos/rgevolve/$repo/releases/tags/$TAG")
  release_id=$(printf '%s' "$release_json" | python3 -c \
    'import json,sys; d=json.load(sys.stdin); print(d.get("id",""))' 2>/dev/null || true)

  if [ -n "$release_id" ]; then
    echo "  deleting release id=$release_id ($TAG)"
    code=$(api -o /dev/null -w "%{http_code}" -X DELETE \
      "https://api.github.com/repos/rgevolve/$repo/releases/$release_id")
    if [ "$code" = "204" ]; then
      echo "    ✓ release deleted"
    else
      echo "    ⚠ unexpected HTTP $code from release delete"
    fi
  else
    echo "  no release at $TAG (skipping)"
  fi

  # 2. Delete the tag ref.
  echo "  deleting tag $TAG"
  code=$(api -o /dev/null -w "%{http_code}" -X DELETE \
    "https://api.github.com/repos/rgevolve/$repo/git/refs/tags/$TAG")
  case "$code" in
    204) echo "    ✓ tag deleted" ;;
    422) echo "    (tag did not exist — skipping)" ;;
    *)   echo "    ⚠ unexpected HTTP $code from tag delete" ;;
  esac
done

echo
echo "Done. Verify with:"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' \"https://github.com/rgevolve/rgevolve/releases/tag/${TAG}\"  # expect 404"
