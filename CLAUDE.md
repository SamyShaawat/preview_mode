# Preview Mode (`preview_mode`): project guide for Claude

Read this first. It records the owner's decisions and how work is done here, so a new session can continue without the old conversation. The design is in `docs/superpowers/specs/2026-11-02-preview-mode-design.md` and the task plan in `docs/superpowers/plans/2026-11-02-preview-mode.md`; they are binding, this file is the quick map.

## What it is

An Odoo app for the Odoo Store (paid, license OPL-1) that shows what a button click would create, change or delete, and where, before the user commits to it. A toggle button in the top bar turns Preview mode on and off. With it on, clicking a button that changes data opens a popup instead of acting. Nothing is saved during the preview. The user then confirms for real or goes back. Owner: Samy Mostafa Shaawat (GitHub `SamyShaawat`).

## Owner decisions (all binding)

- **Audience:** every user of every app. NOT accounting-only, NOT for specific users or apps. There is no allow-list or deny-list of any kind: once installed and the toggle is on, it works on EVERY button that changes data, in every app (core, Enterprise, third-party, custom), for every internal user, with nothing to configure. The journal-entry (Debit/Credit) view is just one extra view for accounting clicks.
- **Versions:** 16.0, 17.0, 18.0, 19.0, 20.0. **20.0 is the reference and default branch** (it was 19.0 until 2026-11-02): build there first, then port to 19, 18, 17, 16.
- **Community-based, works on Enterprise:** depends only on `base` and `web`. It must install and run when Odoo Enterprise is installed (`web_enterprise` changes the navbar and control panel). Enterprise source exists locally for 17.0, 18.0, 19.0 only.
- **Odoo.sh compatible (hard rule):** no external Python packages, no `requirements.txt`, no system or `subprocess` calls, no file writes outside Odoo storage, all state in the database (workers share no memory), no `readonly` routes, no dependence on `odoo.conf` options, no Enterprise-only code. Odoo.sh users add the repo as a git submodule named `preview_mode`.
- **Standard Odoo/OCA practice** for easy upgrade and maintenance: extend with `_inherit`, never edit core, Odoo naming, `_description`, everything prefixed `preview_mode`, user-facing strings translatable, minimal guarded patches only, the Python core identical across versions with every version difference isolated in a small `PORT:`-commented place.
- **License:** OPL-1 (official text in `LICENSE`, copyright line uses the owner's git name). A paid Store listing also needs `price` and `currency` in the manifest (not set yet).
- **Where the control lives:** a toggle button in the top bar (systray, top right, same place on Community and Enterprise). Click it to turn on, click again to turn off. Pressed look and accent colour while on, `aria-pressed`, tooltip, keyboard operable, remembered per user (`res.users.preview_mode_enabled`). The owner said "top of the page on the left or something"; the systray is the author's call (stable on 16 to 20). Ask the owner if they insist on the left.
- **Popup (design A, native Odoo look):** title `Preview: <button label>`; subtext `This is a preview. Nothing from this click has been saved yet.`; order: yellow warning banner (only yellow use), one-sentence summary, a "What will happen" table with columns What (New/Changed/Deleted, old value struck through then new) and Where (Odoo menu path like `Accounting > Accounting > Journal Entries`, or "Here, on this <record>"), then journal lines when a journal entry would be created. Footer left to right: primary button with the SAME label as the clicked button, then `Go back` (not Cancel). Header and footer fixed, middle scrolls. Native Odoo dialog, one accent `#714b67`, flat tables, no pills or emoji, long names wrap, numbers right-aligned on one line, RTL (Arabic) mirrors. A failing click shows `Confirming will fail: <message>` and Confirm stays clickable (the real run decides).
- **Only buttons that change data:** a click that would change nothing (smart buttons, Print, buttons that only open a wizard) runs normally, no popup. The server decides with the payload flag `show` (never `changes == []`).
- **Dirty form:** Odoo saves the user's own edits first as usual; the popup says "Nothing from this click has been saved yet".
- **After Confirm:** a toast lists what was created, each as a clickable link.
- **Icon:** `static/description/icon.png` (128x128) plus `icon.svg`: a white eye on Odoo purple with a click cursor in the iris. Checked on real Odoo 19 + `web_enterprise`.
- **README** must describe only what really exists (status line says what is built).

## How it works

`build_preview()` runs the clicked method inside a savepoint via `safe_run()` and always rolls back. Guards inside `safe_run`: commit and rollback are neutralised on the preview's cursor, sequences return the placeholder `(new)`, `send_email` is recorded not sent, outgoing `requests` calls are blocked, any extra DB connection (including cron/bus style `db_connect`) marks the preview incomplete, post-commit callbacks are dropped; thread-local, nest-safe, inert for other threads. A recorder hooked on `base` create/write/unlink collects changes (ignore list `IGNORED_MODELS`/`IGNORED_FIELDS` lives only in `models/recorder.py`). `locate()` turns models into Odoo menu paths (visible menus only). The real run (after Confirm) records created ids in the transient model `preview.mode.created` (token in context, DB-backed, per-user rows, sudo-created and unreadable records never returned) for the toast links. Routes: `POST /preview_mode/run`, `POST /preview_mode/created`; never `call_button`, no `sudo`, not readonly. Client (not built yet): wrap the button-click function (`doActionButton` in `action_service.js` on 16 to 19; on 20.0 it moved to `webclient/actions/action_plugin.js`, read it first), systray toggle, `web.Dialog` popup, toast.

## Repo, clones, databases

- GitHub: `SamyShaawat/preview_mode` (private). Branches `16.0 17.0 18.0 19.0 20.0` only; the repo root IS the module. Default branch 20.0.
- Local clones: `/media/samy/Home/My-Github/Odoo/odoo-<V>/addons/preview_mode` for V = 16.0 to 20.0 (each on its own branch, excluded from Odoo's own git). `/media/samy/Home/My-Github/Odoo/sync-preview-mode.sh` fast-forwards all five (skips dirty or other-branch clones); scheduling it in cron was blocked, the owner may add `*/15 * * * *`.
- Run Odoo from `odoo-<V>` with `./odoo-venv/bin/python odoo-bin -c odoo.conf ...` (all Python 3.12, venvs per version; 16.0 venv pins `setuptools==67.4.0`). DB users `odoo<V>_user`/`admin`. Test DBs `pm16`..`pm20`; Enterprise test DB `pm19e`. Hands-on demo DBs (demo data on, `admin`/`admin`, Preview Mode available but not installed): `preview_mode_16`..`preview_mode_20` (20 is the owner's own).
- Port 8069 is the owner's own running server: never touch it. Use `--http-port=8079` (or 8076 to 8078) for tests that start HTTP. A running server caches the module manifest: restart it and press "Update Apps List" after the code changes (the owner hit a stale-manifest error this way).
- Odoo 19 does not load demo data from the CLI unless `--with-demo`; 16 to 18 do by default.
- Tests: from `odoo-<V>`: `./odoo-venv/bin/python odoo-bin -c odoo.conf -d pm<NN> -u preview_mode --test-tags /preview_mode --http-port=<free port> --stop-after-init`; expect `0 failed, 0 error(s) of N tests` (N is 39 on 20.0 after Task 4).

## Workflow rules (this project only)

- Every task goes through a pull request: topic branch `<type>/<series>-<topic>` (feat, fix, docs, port, chore; NEVER `19.0/...`, a branch named `19.0` blocks it), base = the matching version branch, title `[20.0] ...`, body states the base branch and that the topic branch is deleted after merge. Squash merge only; GitHub deletes merged branches. Version branches are protected (PR required). See `CONTRIBUTING.md` and `.github/pull_request_template.md`.
- Ports are separate PRs, one per version, and must pass ALL module tests on that version's own Odoo before merging. Never leave a red version; fix it first. Known port differences: `_connect__` (20) is `connect` (16 to 19) in the cursor guard; route type `jsonrpc` (19, 20) vs `json` (16 to 18); ACL file `ir.access.csv` (20) vs `ir.model.access.csv` (16 to 19); `user_writeable` field parameter (20) vs `SELF_WRITEABLE_FIELDS`; `has_access` vs the older rights+rule pair; no walrus `:=` (Odoo 16 supports Python 3.7).
- The owner says "merge all" when they want open PRs merged; otherwise open the PR and stop. Never merge a version that fails tests.
- No Claude attribution lines (no Co-Authored-By, no "Generated with Claude Code") in commits or PRs. The owner's "never commit or push" rule applies to the FlowDesk project, not here.
- Tasks run with subagent-driven development: a fresh implementer per task, an independent reviewer (spec and quality) per task, scoped re-reviews of fixes (max 5 rounds), a ledger at `.superpowers/sdd/2026-11-02-preview-mode/progress.md` (git-ignored, lives only in the `odoo-20.0` clone; briefs and reports are next to it). Stacked task branches conflict after a squash merge: branch each task from the latest `20.0` instead, or `git rebase --onto origin/20.0 <old-base> <branch>`.
- Hooks in this environment ask for "facts" before creating files or running destructive-looking commands (checkout of paths, branch delete, force push): state the facts, then retry the IDENTICAL command.
- Reply style the owner likes: short and plain, state what was done and what is next, ask one thing at a time.

## Status (2026-11-03)

Merged on all five versions: Task 1 skeleton, Task 2 change recorder, Task 3 safe-run guards and Where lookup, the icon, docs (README, CONTRIBUTING, design, plan, LICENSE). Task 4 (payload, user flag, routes) is merged on 20.0 (PR #40, 39 tests); its ports to 19.0, 18.0, 17.0, 16.0 were in progress (check `git log` and the open PRs). Not started: Task 5 journal-entry view (optional extra, only when `account.move` exists), Task 6 client (systray toggle, popup, toast; needs the 20.0 `action_plugin.js` study first; also the manual checks incl. step 5b any-app/any-user and the toggle checks), Task 7 layout hardening and Store assets (`index.html`, screenshots), Task 8 ports of 5, 6, 7, Task 9 Enterprise verification (install with `web_enterprise` on 17, 18, 19 and run tests, check the toggle and icon in the Enterprise UI; 20.0 and 16.0 have no Enterprise source).

Deferred minors (from reviews): HTTP block covers `requests` only; x2many display names computed for every linked record; stale `display_name` stored at create time; walrus `:=` in `controllers/main.py` (to be removed in the ports; remove on 20.0 too); where-path tie-break order; summary plurals like `record(s)`; `assertRaises(Exception)` in `test_payload_private_method_refused`; the placeholder `static/description/index.html` still describes features as working.

## Open questions for the owner

Price and support policy per version; copyright holder name in `LICENSE`; whether the toggle may stay top right (systray); Enterprise source for 16.0 and 20.0 to verify there.
