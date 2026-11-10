#!/usr/bin/env bash
# Build dist/preview_mode-<version>.zip for the Odoo Apps Store.
# The zip has one top-level folder, preview_mode/ (the module folder of this
# repository) plus a copy of LICENSE, so the Store finds the license inside the module.
# It packs the last commit (HEAD), so commit first. Needs git and python3.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "warning: uncommitted changes are NOT in the zip (it is built from HEAD)" >&2
fi

version=$(python3 -c "import ast;print(ast.literal_eval(open('preview_mode/__manifest__.py').read())['version'])")
zip_path="dist/preview_mode-${version}.zip"
mkdir -p dist
rm -f "$zip_path"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git archive HEAD preview_mode | tar -x -C "$tmp"
git show HEAD:LICENSE > "$tmp/preview_mode/LICENSE"
python3 -c "import shutil,sys;shutil.make_archive(sys.argv[1][:-4],'zip',sys.argv[2])" "$zip_path" "$tmp"
echo "built $zip_path"
