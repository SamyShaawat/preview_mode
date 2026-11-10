#!/usr/bin/env python3
"""Static checks that the module is ready for the Odoo Apps Store. Standard library only.

Run from anywhere: python3 scripts/check_store_ready.py
Exit code 1 and one line per problem when something is wrong.
"""
import ast
import glob
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, 'preview_mode')  # the module folder
DESC = os.path.join(ROOT, 'static', 'description')
errors = []


def fail(msg):
    errors.append(msg)


def path(*parts):
    return os.path.join(ROOT, *parts)


def read(*parts):
    with open(path(*parts), encoding='utf-8') as f:
        return f.read()


def png_size(file):
    with open(file, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', head[16:24])


# --- manifest -------------------------------------------------------------
manifest = ast.literal_eval(read('__manifest__.py'))
for key in ('name', 'summary', 'version', 'category', 'author', 'maintainer', 'website',
            'license', 'depends', 'images', 'data'):
    if not manifest.get(key):
        fail("manifest: missing or empty key '%s'" % key)
if 'price' in manifest:
    fail("manifest: 'price' must not be set (free module)")
if manifest.get('license') != 'LGPL-3':
    fail("manifest: license must be LGPL-3")
if sorted(manifest.get('depends', [])) != ['base', 'web']:
    fail("manifest: depends must be exactly base and web")
if not re.fullmatch(r'\d+\.0\.\d+\.\d+\.\d+', manifest.get('version', '')):
    fail("manifest: version must look like 20.0.1.0.0")
if len(manifest.get('summary', '')) > 120:
    fail("manifest: summary is longer than 120 characters")
if '@' in repr(manifest):
    fail("manifest: contains an '@' (no email addresses in public files)")

# --- icon and images ------------------------------------------------------
icon = path('static', 'description', 'icon.png')
if not os.path.isfile(icon):
    fail("static/description/icon.png is missing")
elif png_size(icon) != (128, 128):
    fail("static/description/icon.png must be a real 128x128 PNG, got %s" % (png_size(icon),))
signatures = (b'\x89PNG', b'GIF8', b'\xff\xd8\xff')
for rel in manifest.get('images', []):
    if not os.path.isfile(path(rel)):
        fail("manifest images: %s does not exist" % rel)
    else:
        with open(path(rel), 'rb') as f:
            if not f.read(4).startswith(signatures):
                fail("manifest images: %s is not PNG, GIF or JPEG" % rel)
images = manifest.get('images', [])
if images and os.path.basename(images[0]) != 'banner.png':
    fail("manifest images: the first image must be banner.png")
if not any(os.path.basename(i).endswith('_screenshot.png') for i in images):
    fail("manifest images: no image ending in _screenshot.png (the Store shows it large)")

# --- description page -----------------------------------------------------
index = read('static', 'description', 'index.html')
for pattern, why in ((r'<script', '<script>'), (r'<style', '<style> block'), (r'<iframe', '<iframe>'),
                     (r'<link\b', '<link>'), (r'\son\w+\s*=', 'inline event handler'),
                     (r'(?:src|href)\s*=\s*["\']?\s*(?:https?:)?//', 'external URL'),
                     (r'url\(\s*["\']?https?:', 'external CSS url()'), (r'@import', '@import')):
    if re.search(pattern, index, re.I):
        fail("index.html: contains %s, which the Store strips" % why)
for src in re.findall(r'<img[^>]+src="([^"]+)"', index):
    if src.startswith('data:') or not os.path.isfile(os.path.join(DESC, src)):
        fail("index.html: image %s is not a file in static/description" % src)

# --- translations ---------------------------------------------------------
def po_entries(file):
    """Return {msgid: msgstr} from a .po/.pot file (no plural forms used here)."""
    text = open(file, encoding='utf-8').read()
    out = {}
    for block in re.split(r'\n\n+', text):
        msgid = msgstr = None
        cur = None
        for line in block.splitlines():
            if line.startswith('msgid '):
                cur, msgid = 'id', ast.literal_eval(line[6:])
            elif line.startswith('msgstr '):
                cur, msgstr = 'str', ast.literal_eval(line[7:])
            elif line.startswith('"') and cur == 'id':
                msgid += ast.literal_eval(line)
            elif line.startswith('"') and cur == 'str':
                msgstr += ast.literal_eval(line)
        if msgid:
            out[msgid] = msgstr or ''
    return out


def placeholders(text):
    return sorted(re.findall(r'%\([a-z_]+\)s|%s|%d', text))


pot_file = path('i18n', 'preview_mode.pot')
if not os.path.isfile(pot_file):
    fail("i18n/preview_mode.pot is missing")
else:
    pot = po_entries(pot_file)
    # Every translatable string written in the code must be in the template.
    found = set()
    for file in glob.glob(path('**', '*.py'), recursive=True):
        if '/tests/' in file or '/scripts/' in file:
            continue
        for m in re.finditer(r"""\b_\(\s*(['"])((?:\\.|(?!\1).)*)\1""", open(file, encoding='utf-8').read()):
            found.add(ast.literal_eval(m.group(1) + m.group(2) + m.group(1)))
    for file in glob.glob(path('static', 'src', '**', '*.js'), recursive=True):
        for m in re.finditer(r"""\b_t\(\s*(["'`])((?:\\.|(?!\1).)*)\1""", open(file, encoding='utf-8').read()):
            found.add(m.group(2))
    for msgid in sorted(found):
        if msgid not in pot:
            fail("i18n: %r is in the code but not in preview_mode.pot (re-export it)" % msgid)
    for text in (manifest.get('name'), manifest.get('summary')):
        if text and text not in pot:
            fail("i18n: manifest text %r is not in preview_mode.pot (re-export it)" % text)
    for po_file in sorted(glob.glob(path('i18n', '*.po'))):
        name = os.path.basename(po_file)
        po = po_entries(po_file)
        for msgid in set(pot) - set(po):
            fail("i18n/%s: missing %r" % (name, msgid))
        for msgid in set(po) - set(pot):
            fail("i18n/%s: %r is not in the template" % (name, msgid))
        for msgid, msgstr in po.items():
            if msgid.startswith('<img'):
                continue
            if not msgstr:
                fail("i18n/%s: %r is not translated" % (name, msgid))
            elif placeholders(msgid) != placeholders(msgstr):
                fail("i18n/%s: placeholders differ in %r" % (name, msgid))
    for lang in ('ar', 'fr', 'es'):
        if not os.path.isfile(path('i18n', lang + '.po')):
            fail("i18n/%s.po is missing" % lang)

if errors:
    print('\n'.join('FAIL ' + e for e in errors))
    sys.exit(1)
print('store-ready checks passed')
