# Publishing Preview Mode on the Odoo Apps Store

Sources, read on 2026-11-10: [Submit your Apps and Themes](https://apps.odoo.com/apps/upload) (the upload page and its FAQ), [Vendor Guidelines](https://apps.odoo.com/apps/vendor-guidelines) and [Sales Conditions](https://apps.odoo.com/apps/sales-conditions). Anything those pages do not state is marked NOT VERIFIED. Odoo can change these pages; re-read them before you publish.

The Store publishes from a Git repository that Odoo reads. It does not take a zip upload (the upload page describes only repository registration; a zip upload flow is NOT VERIFIED). The zip built by `scripts/build_store_zip.sh` is for people who install by hand and for GitHub releases.

## Before you start

1. Run the checks and fix anything they print:

   ```bash
   python3 scripts/check_store_ready.py
   ```

2. Open `static/description/index.html` in a browser. The Store only keeps resources from `static/description`, canonical YouTube links, Microsoft Teams links and `mailto:` or `skype:` links; other external links are invalidated, and scripts, widgets and modals are not allowed (Vendor Guidelines, Description). The page uses inline styles only and has no links, so nothing is stripped. The support section names the GitHub project as plain text on purpose.
3. Check the manifest: `license` is `LGPL-3` (an accepted value), there is no `price`, the version starts with the Odoo series (`20.0.1.0.0`), and `images` lists the banner first and one image ending in `_screenshot.png`. Per the upload page, the first image whose name ends in `_screenshot` is shown large. A manifest error unpublishes every module of the repository (Vendor Guidelines, Removal).

## Account and repository access

1. Sign in on apps.odoo.com with an Odoo.com account. The upload page says you must sign in to register a repository.
2. The repository is private today. For a private repository Odoo needs read access: on GitHub, authorize the user `online-odoo` on the repository (Settings > Collaborators). For other hosts use Odoo's public SSH key from `apps.odoo.com/apps/repository-keys`. A public repository needs no access step.
3. Do not make the repository public for this step unless you want to. Visibility is your decision.

## Register the repository

1. Go to <https://apps.odoo.com/apps/upload> and register the repository with its SSH URL and the branch as a `#version` suffix:

   ```
   ssh://git@github.com/SamyShaawat/preview_mode#20.0
   ```

   The upload page gives the format `ssh://git@gitServer(:port)/mypath#version` and says to use a colon only before a port number. Whether the suffix is the branch name or the Odoo series is described only by its example (`#9.0`); the branches here are named exactly `16.0` to `20.0`, so both readings give the same result.
2. Register one URL per version branch you want to list: `#20.0` now, `#19.0` and the others when those ports are merged. Each version is a separate product from 13.0 on (Sales Conditions), and the module name must stay `preview_mode` across versions (Vendor Guidelines, Updates and Versioning).
3. The upload page does not describe the registration form fields, how the scan is started or its error messages (NOT VERIFIED). A forum thread reports that a false "no icon" error can clear after refreshing the repository a couple of times; treat that as hearsay.

## What the Store reads from the module

| Store field | Where it comes from |
|---|---|
| Title | `name` |
| One-line summary | `summary` |
| Author, website | `author`, `website` |
| Category | `category` (Productivity) |
| Icon | `static/description/icon.png`, a real 128x128 PNG. Renamed files do not work. |
| Cover and screenshots | `images`, PNG, GIF or JPEG |
| Description page | `static/description/index.html` |
| License | `license` and the root `LICENSE` file |
| Price | none: no `price` key makes it free |

Pixel sizes for the banner and screenshots are not stated on the upload page (NOT VERIFIED). The banner is 1200x600, the icon 128x128.

## Rules that apply to this module

- Description and screenshots in English; no promotions or links to other stores (Vendor Guidelines).
- No data collected without consent: the module collects nothing, and the description says so (upload page, Rules).
- No obfuscated code, no downloading or running other code (Rules R1 to R6).
- Free apps do not require support (Vendor Guidelines, Support). Support is via GitHub Issues and Discussions; the `support` manifest key is meant for an email and is left out so no personal email is published.
- Beta apps need a version below 1.0. This one is 1.0.0 (CHANGELOG).
- Third-party apps cannot be installed on Odoo Online (SaaS); they work on Odoo.sh and on-premise (Sales Conditions). The description states Odoo.sh support.

## Per-version files

For each version branch, the same set of files, built from that branch:

1. `__manifest__.py` with `version` `<series>.1.0.0` or higher.
2. `static/description/icon.png`, `banner.png`, the screenshots and `index.html`.
3. `i18n/preview_mode.pot`, `ar.po`, `fr.po`, `es.po` (re-exported on that version).
4. `LICENSE`.

Screenshots show Odoo 20. When a port lands, retake the screenshots on that version if the UI differs; otherwise reuse them.

## Update later

1. Merge the change into the version branch through a pull request.
2. Raise `version` in `__manifest__.py`. The Vendor Guidelines say each release should have a new version number and that it must rise whenever the database schema changes. Add a `CHANGELOG.md` entry.
3. If strings changed, re-export the template and update the `.po` files (`odoo-bin i18n export -d <db> -l pot -o i18n/preview_mode.pot preview_mode` on a database where the module is updated), then run `python3 scripts/check_store_ready.py`.
4. Tag the release (`v1.0.1`). The release workflow builds `dist/preview_mode-<version>.zip` and attaches it to the GitHub release.
5. How the Store picks up a new commit (automatic rescan or a manual refresh) is NOT VERIFIED on the pages above. After pushing, open the app on apps.odoo.com and check that the version shown matches.

## Removing the app

Per the upload page, deleted modules stay in the Store for safekeeping; to remove one, email apps@odoo.com. Apps already installed or depended on are hidden, not removed.
