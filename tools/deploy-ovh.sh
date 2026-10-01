#!/usr/bin/env bash
# Uploads dist/ to the OVH web hosting over SFTP.
#
#   npm run deploy:ovh             build and upload
#   DRY_RUN=1 npm run deploy:ovh   build and list what would change
#
# Settings come from .env.deploy locally, or from the environment in CI.
# Needs lftp (brew install lftp / apt-get install lftp).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env.deploy ]]; then
  set -a; source .env.deploy; set +a
fi
: "${OVH_SFTP_HOST:?} ${OVH_SFTP_USER:?} ${OVH_SFTP_PASSWORD:?} ${OVH_REMOTE_DIR:?}"
OVH_SFTP_PORT="${OVH_SFTP_PORT:-22}"

[[ -f dist/index.html ]] || { echo "No build in dist/; run npm run build first." >&2; exit 1; }
grep -q 'rel="canonical" href="https://aaastrategy.eu/"' dist/index.html \
  || { echo "dist/ is not a production build (SITE_URL/BASE_PATH set?)." >&2; exit 1; }
cp deploy/ovh/.htaccess dist/.htaccess

dry=""
[[ -n "${DRY_RUN:-}" ]] && dry="--dry-run"

# Visitors mid-deploy never get a page whose assets are missing:
#  1. new fingerprinted assets (same name means same content, so size is enough)
#  2. pages and the rest, which point at those assets
#  3. only then, files no longer in the build
# OVH's own folders on the hosting are left alone.
keep="--exclude ^\.well-known/ --exclude ^\.ovhconfig$ --exclude ^cgi-bin/"
export LFTP_PASSWORD="$OVH_SFTP_PASSWORD"
lftp -c "
  set cmd:fail-exit yes
  set net:max-retries 3
  set net:timeout 30
  set sftp:connect-program 'ssh -a -x -o UserKnownHostsFile=deploy/ovh/known_hosts -o StrictHostKeyChecking=yes'
  open --env-password -u '$OVH_SFTP_USER' -p '$OVH_SFTP_PORT' 'sftp://$OVH_SFTP_HOST'
  mkdir -p -f '$OVH_REMOTE_DIR/_astro'
  mirror -R $dry --ignore-time --no-perms --parallel=4 --verbose dist/_astro '$OVH_REMOTE_DIR/_astro'
  mirror -R $dry --no-perms --parallel=4 --verbose --exclude ^_astro/ $keep dist '$OVH_REMOTE_DIR'
  mirror -R $dry --delete --ignore-time --no-perms --verbose $keep dist '$OVH_REMOTE_DIR'
"
