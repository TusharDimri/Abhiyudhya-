#!/usr/bin/env bash
# Install a release on the server - the runbook's "Releasing a new version",
# run by .github/workflows/deploy.yml (or by hand, as the ubuntu user):
#
#   cd /opt/abhiyudhya && bash scripts/deploy.sh v1.1.0
#
# The new images are built while the old ones keep serving; the database is
# upgraded with the new image; then the containers are swapped and checked.
# If the site isn't healthy afterwards, the previous release is put back
# (code only - a migration that ran stays; restore the RDS snapshot for that).
set -euo pipefail

TAG="${1:?usage: deploy.sh <tag>}"
APP=/opt/abhiyudhya
DC=(docker compose -f docker-compose.prod.yml)

cd "$APP"
[[ -f .env.prod ]] || { echo "No .env.prod in $APP - see runbook step 4.6"; exit 1; }

PREVIOUS="$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)"
echo "== Releasing $TAG (now running: $PREVIOUS)"

git fetch --tags --force --quiet
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null || { echo "No tag $TAG on GitHub"; exit 1; }
git checkout --quiet "$TAG"

healthy() {
  # port 80 sends on to HTTPS once there's a certificate: follow it, on this machine
  for _ in $(seq 1 30); do
    if curl -fsSkL --max-time 5 http://localhost/health/deep | grep -q '"status": *"ok"'; then
      return 0
    fi
    sleep 4
  done
  return 1
}

roll_back() {
  echo "!! $TAG is not healthy - putting $PREVIOUS back"
  "${DC[@]}" logs --tail 40 backend || true
  git checkout --quiet "$PREVIOUS"
  "${DC[@]}" up -d --build
  healthy && echo "== $PREVIOUS is back and healthy" || echo "!! $PREVIOUS is not healthy either - look now"
  echo "If $TAG changed the database, restore its RDS snapshot (runbook: Recover from a data mistake)."
  exit 1
}

echo "== Building images (the site stays up)"
"${DC[@]}" build

echo "== Upgrading the database with the new code"
"${DC[@]}" run --rm --no-deps backend flask db upgrade || roll_back
"${DC[@]}" run --rm --no-deps backend flask db current

echo "== Starting the new containers"
"${DC[@]}" up -d

echo "== Checking the site"
healthy || roll_back
"${DC[@]}" ps

docker image prune -f >/dev/null
echo "== $TAG is live"
