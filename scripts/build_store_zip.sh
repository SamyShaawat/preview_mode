#!/usr/bin/env bash
# Build dist/preview_mode-<version>.zip for the Odoo Apps Store.
# The zip has one top-level folder, preview_mode/, and only runtime files:
# what `git archive` exports after the export-ignore rules in .gitattributes.
# It packs the last commit (HEAD), so commit first. Needs git and python3.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "warning: uncommitted changes are NOT in the zip (it is built from HEAD)" >&2
fi

version=$(python3 -c "import ast;print(ast.literal_eval(open('__manifest__.py').read())['version'])")
zip_path="dist/preview_mode-${version}.zip"
mkdir -p dist
rm -f "$zip_path"
git archive --format=zip --prefix=preview_mode/ -o "$zip_path" HEAD
echo "built $zip_path"
