#!/bin/sh
# Run the plugin eval suite without shipping it: the cases and mocks live in ./evals,
# outside the plugin folder users install, so this assembles a temporary copy of the
# plugin with the suite inside and runs `claude plugin eval` on it.
# Every run is a real model call billed to your plan or API key.
# Usage: scripts/run_evals.sh [claude plugin eval options...]
#   quick smoke test:  scripts/run_evals.sh --runs 1 --ablation none
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/scio-plugin-eval.XXXXXX")
trap 'rm -rf "$work"' EXIT INT TERM
cp -R "$root/scio" "$work/scio"
mkdir "$work/scio/evals"
for entry in "$root"/evals/*; do
  [ "$(basename "$entry")" = results ] || cp -R "$entry" "$work/scio/evals/"
done
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$root/evals/results/$stamp"
mkdir -p "$out"
claude plugin eval "$work/scio" --trust-plugin --no-publish \
  --output-dir "$out" --report "$out/report.html" "$@"
