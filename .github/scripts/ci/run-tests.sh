#!/bin/bash
set -euo pipefail
set -x

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <TEST_BUILD>" >&2
    exit 1
fi

TEST_BUILD="$1"
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

compose_files=(-f docker-compose.yml -f .github/docker-compose.ci.override.yml)
compose() {
    docker compose "${compose_files[@]}" "$@"
}

cleanup() {
    compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

cp website/settings/local-travis.py website/settings/local.py
cp api/base/settings/local-travis.py api/base/settings/local.py
cp tasks/local-dist.py tasks/local.py

python3 <<'PY'
from pathlib import Path
website_local = Path('website/settings/local.py')
website_local.write_text(website_local.read_text() + '\nDB_HOST = \'postgres\'\nDB_PORT = 5432\nELASTIC_URI = \'elasticsearch:9200\'\n')
PY

compose pull postgres elasticsearch6 web >/dev/null 2>&1 || true
compose build elasticsearch
compose up -d postgres elasticsearch elasticsearch6

for _ in $(seq 1 60); do
    if compose exec -T postgres pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
        break
    fi
    sleep 5
done

if ! compose exec -T postgres pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
    echo "postgres did not become ready" >&2
    exit 1
fi

for url in "http://localhost:9200/_cluster/health?wait_for_status=yellow" "http://localhost:9201/_cluster/health?wait_for_status=yellow"; do
    for _ in $(seq 1 60); do
        if curl -fs "$url" >/dev/null 2>&1; then
            break
        fi
        sleep 5
    done
    if ! curl -fs "$url" >/dev/null 2>&1; then
        echo "elasticsearch endpoint $url did not respond" >&2
        exit 1
    fi
done

compose run --rm requirements

read -r -d '' container_script <<'BASH' || true
set -euo pipefail
set -x
export PATH="/usr/local/bin:/usr/bin:$PATH"
invoke travis_addon_settings
# Minimal Ember app shells so send_from_directory returns 200 during tests
mkdir -p "$HOME/preprints" "$HOME/website/ember_osf_web"
for ember_stub in "$HOME/preprints/index.html" "$HOME/website/ember_osf_web/index.html"; do
    if [ ! -f "$ember_stub" ]; then
        printf '<!doctype html><title>stub</title>' > "$ember_stub"
    fi
done
if [ "$TEST_BUILD" = "addons" ]; then
    cat <<'EOF' > ~/.nodeenvrc
[nodeenv]
node = system
EOF
    pip3 install --force-reinstall --no-deps pre-commit==1.10.5
    hash -r
fi
mkdir -p user_key_info
cp root_cert_verifycate.pem user_key_info/
netstat -an | grep 'tcp.*LISTEN' || true
pip3 uninstall uritemplate.py --yes || true
pip3 install uritemplate.py==0.3.0
if [ "$TEST_BUILD" = "api1_and_js" ]; then
    invoke assets --dev
fi
invoke "test_travis_${TEST_BUILD}" -n 1
BASH

compose run --rm \
    -e TEST_BUILD="$TEST_BUILD" \
    -e BOWER_ALLOW_ROOT=1 \
    -e NPM_CONFIG_FORCE=true \
    -e npm_config_force=true \
    web bash -lc "$container_script"
