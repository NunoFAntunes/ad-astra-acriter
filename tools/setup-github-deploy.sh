#!/usr/bin/env bash
# One-off GitHub setup for both deploys; safe to re-run (also to rotate the
# OVH password after changing .env.deploy).
#  - GitHub Pages, built by Actions, which the dev branch may deploy to
#  - the "production" environment, usable only from prod, holding the OVH
#    settings from .env.deploy (the password as a secret)
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source .env.deploy; set +a
: "${OVH_SFTP_PASSWORD:?fill in .env.deploy first}"
repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Creates an environment that only the given branch can deploy from.
env_for_branch() {
  gh api -X PUT "repos/$repo/environments/$1" --silent --input - <<<'{
    "deployment_branch_policy": { "protected_branches": false, "custom_branch_policies": true }
  }'
  gh api -X POST "repos/$repo/environments/$1/deployment-branch-policies" \
    -f name="$2" -f type=branch --silent 2>/dev/null || true # already there
}

gh api "repos/$repo/pages" --silent 2>/dev/null \
  || gh api -X POST "repos/$repo/pages" -f build_type=workflow --silent
env_for_branch github-pages dev

env_for_branch production prod
for name in OVH_SFTP_HOST OVH_SFTP_PORT OVH_SFTP_USER OVH_REMOTE_DIR; do
  gh variable set "$name" --env production --body "${!name}"
done
printf %s "$OVH_SFTP_PASSWORD" | gh secret set OVH_SFTP_PASSWORD --env production

echo "Done: $(gh api "repos/$repo/pages" -q .html_url) (dev), https://aaastrategy.eu (prod)"
