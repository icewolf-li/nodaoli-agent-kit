#!/usr/bin/env bash
set -euo pipefail

command -v python3 >/dev/null 2>&1 || { echo 'Python 3.9+ is required.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || {
  echo 'Python 3.9+ is required.' >&2; exit 1;
}

# The Python installer reads the project manifest and downloads the payload.
# Resolve repo/ref here too, so the implementation comes from the same source.
kit_repo=''
kit_ref=''
kit_project="$PWD"
kit_source=''
kit_args=("$@")
while (($#)); do
  case "$1" in
    --repo|--ref|--project|--source|--stack|--skills|--agents)
      (($# >= 2)) || { echo "Missing value for $1" >&2; exit 1; }
      case "$1" in
        --repo) kit_repo="$2" ;;
        --ref) kit_ref="$2" ;;
        --project) kit_project="$2" ;;
        --source) kit_source="$2" ;;
      esac
      shift 2 ;;
    --no-skills|--update|--force) shift ;;
    -h|--help)
      echo 'Usage: install.sh [--project DIR] [--repo OWNER/REPO] [--ref REF]'
      echo '                  [--stack NAME] [--skills NAME,... | --no-skills]'
      echo '                  [--agents codex,claude] [--update] [--force] [--source DIR]'
      exit 0 ;;
    *) echo "Unknown argument: $1 (use --help)" >&2; exit 1 ;;
  esac
done

kit_metadata=$(python3 - "$kit_project" "$kit_repo" "$kit_ref" <<'PY'
import json, pathlib, re, sys
path = pathlib.Path(sys.argv[1]).expanduser() / '.agent/kit.json'
old = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
repo = sys.argv[2] or old.get('repo', 'nodaoli/nodaoli-agent-kit')
ref = sys.argv[3] or old.get('ref', 'main')
if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
    raise SystemExit('Repo must be owner/name')
if not re.fullmatch(r'[A-Za-z0-9_./-]+', ref) or '..' in ref:
    raise SystemExit('Invalid Git ref')
from urllib.parse import quote
print(repo)
print(quote(ref, safe=''))
PY
)
kit_repo=${kit_metadata%%$'\n'*}
kit_encoded_ref=${kit_metadata#*$'\n'}

if [[ -n "$kit_source" ]]; then
  exec python3 "$kit_source/scripts/install.py" "${kit_args[@]}"
fi

kit_temp=$(mktemp -d "${TMPDIR:-/tmp}/nodaoli-agent-kit-XXXXXXXX")
trap 'rm -f -- "$kit_temp/install.py"; rmdir -- "$kit_temp"' EXIT
kit_url="https://raw.githubusercontent.com/$kit_repo/$kit_encoded_ref/scripts/install.py"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL --connect-timeout 15 --max-time 60 "$kit_url" -o "$kit_temp/install.py"
elif command -v wget >/dev/null 2>&1; then
  wget -q --timeout=60 "$kit_url" -O "$kit_temp/install.py"
else
  echo 'curl or wget is required.' >&2
  exit 1
fi
python3 "$kit_temp/install.py" "${kit_args[@]}"
