# Preview Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An Odoo Community app, `preview_mode`, that shows what a data-changing button click would create, change or delete, and where, before the user commits to it. Versions 16.0 to 20.0, milestone 1 is 19.0.

**Architecture:** A server route runs the clicked method inside a savepoint with every side channel guarded (commit, sequences, mail, HTTP, extra cursors), records changes through a thread-local recorder hooked on `base` create/write/unlink, then always rolls back and returns a JSON payload. A client wrapper around `doActionButton` calls it when the per-user switch is on, shows a native dialog, and on Confirm runs the original click with a token so the real run reports the records it created for the toast links.

**Tech Stack:** Python (Odoo ORM, werkzeug), OWL (JS) per Odoo version, QWeb XML, PostgreSQL savepoints. No external dependencies.

**Spec:** `/media/samy/Home/My-Github/Odoo/preview_mode/docs/superpowers/specs/2026-11-02-preview-mode-design.md`

## Global Constraints

- Manifest `depends` is `['base', 'web']` only. Must install on Community. `license` is `OPL-1`. Version string `<series>.1.0.0` (for example `19.0.1.0.0`).
- Audience is every user of every app. No accounting dependency. No accounting wording in names, defaults or screenshots.
- Popup title is `Preview: <button label>`. Subtext is exactly `This is a preview. Nothing from this click has been saved yet.` Footer left to right: primary button with the clicked button's label, then `Go back`. Warning wording for a failing click starts `Confirming will fail:`. The Confirm button is never disabled.
- Look: Odoo native dialog (`web.Dialog` or the version's equivalent), one accent `#714b67`, flat tables, yellow only for the warning banner, no pills, no emoji, no gradients, no absolute positioning, header and footer fixed with a scrolling middle, logical start/end for RTL.
- The preview never commits, never sends email, never calls an outside service, never consumes a real sequence number, and reports `incomplete` instead of an all-clear when it cannot be sure.
- With the switch off, no extra RPC and no behaviour change. Server hooks cost one thread-local lookup.
- Every task ships as a pull request: topic branch `<type>/<series>-<topic>`, base the matching version branch, squash merge, branch deleted after merge, no Claude attribution lines. See `CONTRIBUTING.md`.
- Ignore list for "what counts as a change" lives in one place: `IGNORED_MODELS` and `IGNORED_FIELDS` in `models/recorder.py`.

## Review Focus

1. A button that only returns an action (opens a wizard or view): no popup, click runs normally. Pinned in Task 4.
2. A button that raises `UserError` or `ValidationError`: popup shows `Confirming will fail: <message>`, Confirm stays clickable. Pinned in Task 4.
3. A list-header button on 30 selected records: rows grouped per record, capped at 200 rows with `and N more`, no timeout. Pinned in Task 4.
4. A user without access to the menu of a changed model: `Where` falls back to the parent record or the plain record type name, never leaks a hidden menu. Pinned in Task 3.
5. An exception inside the preview: recorder and guards are cleared, the next click behaves normally, no locks remain. Pinned in Task 2.

---

## File Structure (19.0 reference; other branches mirror it)

The git repo root is the Odoo module itself, so a clone placed at `odoo-<v>/addons/preview_mode` is directly loadable.

```
preview_mode/                       (repo root = Odoo module; one branch per Odoo version)
  __manifest__.py
  __init__.py
  models/{__init__,recorder,base,guards,where,payload,res_users,ir_http}.py
  controllers/{__init__,main}.py
  static/src/{preview_service.js,preview_dialog.js,preview_dialog.xml,preview_switch.js,preview_switch.xml,preview_toast.js,preview.scss}
  static/description/{icon.png,index.html}
  tests/{__init__,test_recorder,test_guards,test_where,test_payload,test_controller}.py
  docs/superpowers/{specs,plans}/
```

Each file has one job: `recorder` collects changes; `base` hooks the ORM into it; `guards` makes a run safe; `where` finds menu paths; `payload` turns recorded changes into the JSON the client shows; `controllers/main` exposes it.

---

### Task 1: Module skeleton and 19.0 wiring

**Files:**
- Create: the tree above as empty modules plus `__manifest__.py`.
- Place: the repo at `/media/samy/Home/My-Github/Odoo/odoo-19.0/addons/preview_mode`.

**Interfaces:**
- Produces: an installable module `preview_mode` on 19.0 that later tasks fill.

- [ ] **Step 1:** Write `__manifest__.py` with name `Preview Mode`, summary `See what a button click will do before it does it`, category `Productivity`, `depends: ['base','web']`, `license: 'OPL-1'`, `installable: True`, `application: False`, assets bundle `web.assets_backend` listing the files in `static/src/`, and `post_load: 'post_load'`.
- [ ] **Step 2:** Create the empty package `__init__.py` files and an empty `post_load()` function in `__init__.py`. Add `preview_mode` to `odoo-19.0/.git/info/exclude`.
- [ ] **Step 3:** Install on a fresh database. Run (from `odoo-19.0`): `./odoo-venv/bin/python odoo-bin -c odoo.conf -d pm19 -i preview_mode --stop-after-init`. Expected: exits 0, log shows `Module preview_mode loaded`, no warnings naming `preview_mode`.
- [ ] **Step 4:** Open the first PR against `19.0` (see `CONTRIBUTING.md`).

---

### Task 2: Change recorder and ORM hooks

**Files:**
- Create: `models/recorder.py`, `models/base.py`
- Test: `tests/test_recorder.py`

**Interfaces:**
- Produces in `recorder.py`:
  - `IGNORED_MODELS: tuple[str, ...]` = `('mail.tracking.value','mail.followers','mail.message','ir.attachment')`; `IGNORED_FIELDS: tuple[str, ...]` = `('write_date','write_uid','create_date','create_uid')`. Transient models are ignored by checking `model._transient`.
  - `class Change(NamedTuple)`: `kind: str` (`'new'|'changed'|'deleted'`), `model: str`, `res_id: int`, `display_name: str`, `fields: list[tuple[str, str, str]]` as `(field label, old text, new text)`.
  - `class ChangeRecorder`: context manager. Attributes `changes: list[Change]`, `warnings: list[str]`, `emails: list[dict]` (`{'to': str, 'subject': str}`), `incomplete: bool`. Methods `note_create(records)`, `note_write(records, old, vals)`, `note_unlink(records)`. Entering pushes it as the thread's active recorder; exiting always pops it, including after an exception.
  - `active_recorder() -> ChangeRecorder | None`.
- Produces in `base.py`: `class Base(models.AbstractModel)` with `_inherit = 'base'` overriding `create`, `write`, `unlink`. Each calls `active_recorder()` once; when it is `None` the override just calls `super()`.

- [ ] **Step 1: Failing tests** in `test_recorder.py`:
  - `test_create_is_recorded`: inside `ChangeRecorder()`, `env['res.partner'].create({'name': 'A'})` gives one `Change` with `kind == 'new'`, `model == 'res.partner'`, `display_name == 'A'`.
  - `test_write_records_old_and_new`: write `name` from `A` to `B` gives `kind == 'changed'` and `fields == [('Name', 'A', 'B')]`.
  - `test_unlink_is_recorded`: `kind == 'deleted'`.
  - `test_ignored_models_and_fields`: posting a chatter note and writing only `write_date` produce zero changes.
  - `test_transient_ignored`: creating a wizard record produces zero changes.
  - `test_no_recorder_means_no_effect`: with no recorder active, `active_recorder() is None` and create/write behave normally.
  - `test_recorder_cleared_after_exception`: raise inside `with ChangeRecorder()`; afterwards `active_recorder() is None`. (Review Focus 5.)
- [ ] **Step 2:** Run `./odoo-venv/bin/python odoo-bin -c odoo.conf -d pm19 -u preview_mode --test-tags /preview_mode:TestRecorder --stop-after-init`. Expected: FAIL (names missing).
- [ ] **Step 3:** Implement `recorder.py` and `base.py` per Interfaces. The thread-local is a module-level `threading.local()`. In `write`, read old values with `read(list(vals))` only when a recorder is active. Many2one, selection and monetary values are rendered through `display_name` or the selection label.
- [ ] **Step 4:** Re-run the same command. Expected: PASS.
- [ ] **Step 5:** Commit on the task branch and open a PR against the series branch (see `CONTRIBUTING.md`).

---

### Task 3: Safe-run guards and the Where lookup

**Files:**
- Create: `models/guards.py`, `models/where.py`
- Modify: `__init__.py` (`post_load` installs the HTTP guard)
- Test: `tests/test_guards.py`, `tests/test_where.py`

**Interfaces:**
- Consumes: `ChangeRecorder`, `active_recorder` from Task 2.
- Produces in `guards.py`: `safe_run(env) -> ContextManager[ChangeRecorder]`. Opens a savepoint, activates a recorder, neutralises `cr.commit`, makes `ir.sequence._next` return `'(new)'`, makes `ir.mail_server.send_email` record to `recorder.emails` and send nothing, makes outgoing `requests` calls raise `PreviewBlocked` and add a warning, and makes opening any other cursor set `recorder.incomplete = True` and raise `PreviewIncomplete`. Always rolls back the savepoint. Also defines `class PreviewBlocked(Exception)` and `class PreviewIncomplete(Exception)`.
- Produces in `where.py`: `locate(env, model_name: str, record=None) -> str` returning a menu path such as `Accounting › Accounting › Journal Entries` using the `complete_name` of the nearest-to-root visible `ir.ui.menu` whose window action has that `res_model`. Falls back to the parent record's path (first required many2one such as `move_id`, `order_id`, `picking_id`), then to the model's description. Menus the user cannot open are never used.

- [ ] **Step 1: Failing tests** in `test_guards.py` (use a real second cursor from `self.registry.cursor()` for the commit test, because `TransactionCase` already neutralises commit):
  - `test_rollback_after_run`: create a partner inside `safe_run`, afterwards `search_count` of that name is 0.
  - `test_commit_does_not_persist`: inside `safe_run` on a real cursor, create a partner then call `cr.commit()`; a fresh cursor then finds none. Clean up any row on failure.
  - `test_sequence_is_placeholder_and_not_consumed`: `env['ir.sequence'].next_by_code(code)` inside returns `'(new)'`; the next call outside returns the first real number.
  - `test_email_listed_not_sent`: `send_email` on a built message inside records one entry in `emails` and opens no SMTP connection (patch `smtplib.SMTP` to raise if touched).
  - `test_http_blocked`: `requests.get('http://example.invalid')` inside raises `PreviewBlocked` and the recorder has a warning mentioning `example.invalid`.
  - `test_separate_cursor_marks_incomplete`: `self.registry.cursor()` inside sets `incomplete`.
  - In `test_where.py`:
  - `test_where_uses_menu_path`: `locate(env, 'res.partner')` returns a string containing `›` and ending with a menu name.
  - `test_where_hides_inaccessible_menu`: for a user without the menu's group, the path is the model description, not the menu path. (Review Focus 4.)
  - `test_where_falls_back_to_parent`: a model with no menu returns the parent's path.
- [ ] **Step 2:** Run `... -u preview_mode --test-tags /preview_mode:TestGuards,/preview_mode:TestWhere --stop-after-init`. Expected: FAIL.
- [ ] **Step 3:** Implement `guards.py` and `where.py`. Commit neutralisation on 19.0: replace the commit callable on the cursor instance for the duration of the run (verify the cursor class allows this; otherwise wrap `Cursor.commit` once with a thread-local check). HTTP guard patches `requests.Session.send` once in `post_load` with a thread-local check. Cursor guard patches `Registry.cursor` the same way.
- [ ] **Step 4:** Re-run. Expected: PASS.
- [ ] **Step 5:** Commit on the task branch and open a PR against the series branch (see `CONTRIBUTING.md`).

---

### Task 4: Preview payload and the controller routes

**Files:**
- Create: `models/payload.py`, `models/res_users.py`, `models/ir_http.py`, `controllers/main.py`
- Test: `tests/test_payload.py`, `tests/test_controller.py`

**Interfaces:**
- Consumes: `safe_run`, `ChangeRecorder`, `locate` from Tasks 2 and 3.
- Produces in `payload.py`: `build_preview(env, model: str, method: str, res_ids: list[int], args: list, kwargs: dict, label: str) -> dict` returning:
  `{'changes': [{'kind','what','where','fields':[{'label','old','new'}]}], 'emails': [...], 'warnings': [{'text','blocking'}], 'incomplete': bool, 'summary': str, 'journal': []}`.
  `'changes'` is empty exactly when there is nothing to show and nothing failed (client then runs the click normally). A method that raises `UserError`/`ValidationError` yields a blocking warning `Confirming will fail: <message>`. A method that returns only an action dict yields empty `changes`. Rows are capped at 200 with a final `and N more` row. `summary` is one sentence such as `Confirming will create 1 journal entry, update 1 record, and queue 1 email (not sent during the preview).`
- Produces in `res_users.py`: boolean field `preview_mode_enabled` on `res.users`, writable by the user (add to `SELF_WRITEABLE_FIELDS`), default `False`.
- Produces in `ir_http.py`: `session_info()` also returns `preview_mode_enabled`.
- Produces in `controllers/main.py`:
  - `POST /preview_mode/run` (RPC type `jsonrpc` on 19.0, params `model, method, res_ids, args, kwargs, label`) returns `build_preview(...)`.
  - `POST /preview_mode/created` (params `token: str`) returns `[{'model','res_id','name','menu_path'}]` for records created by the real run carrying that token, then deletes the rows.
- Token recording: a transient model `preview.mode.created` (fields `token`, `model`, `res_id`, `name`); `base.create` writes a row when `self.env.context.get('preview_mode_token')` is set, ignoring the same models as the recorder and ignoring `preview.mode.created` itself.

- [ ] **Step 1: Failing tests:**
  - `test_payload_for_create_button`: `build_preview(env,'res.partner','create_company',[partner.id],[],{},'Create company')` has one `changes` row with `kind 'new'`, nonempty `where`, and `summary` starting `Confirming will create`.
  - `test_payload_empty_for_action_only_button`: a method returning `{'type':'ir.actions.act_window',...}` with no writes gives `changes == []`. (Review Focus 1.)
  - `test_payload_failing_button_is_blocking_warning`: a method raising `UserError('Period locked')` gives a warning with `blocking == True` and text `Confirming will fail: Period locked`. (Review Focus 2.)
  - `test_payload_caps_rows`: a button writing 300 partners gives at most 201 rows, last row text `and 100 more`. (Review Focus 3.)
  - `test_payload_rolls_back`: after `build_preview` the changes are not in the database.
  - `test_user_flag_is_self_writable`: a plain internal user can write `preview_mode_enabled` on themselves.
  - `test_created_endpoint_returns_and_clears`: a real call carrying `preview_mode_token='t1'` that creates a partner, then `/preview_mode/created` with `'t1'` returns one entry; a second call returns `[]`.
- [ ] **Step 2:** Run `... --test-tags /preview_mode:TestPayload,/preview_mode:TestController --stop-after-init`. Expected: FAIL.
- [ ] **Step 3:** Implement. The controller must call `build_preview` with the request's real environment and the user's own rights (no `sudo`). Do not override `call_button`.
- [ ] **Step 4:** Re-run. Expected: PASS.
- [ ] **Step 5:** Commit on the task branch and open a PR against the series branch (see `CONTRIBUTING.md`).

---

### Task 5: Accounting journal view (optional extra)

**Files:**
- Modify: `models/payload.py`
- Test: `tests/test_payload.py`

**Interfaces:**
- Consumes: `build_preview` from Task 4.
- Produces: `payload['journal']` as `[{'move': str, 'lines': [{'account': str, 'debit': float, 'credit': float}], 'balanced': bool}]`, filled only when `'account.move' in env` and a new `account.move` was recorded. Otherwise `[]`.

- [ ] **Step 1: Failing test** (tagged `post_install`, skipped when `account` is not installed): `test_journal_for_post_button`: previewing `action_post` on a draft vendor bill returns one journal entry whose debit total equals credit total and `balanced is True`.
- [ ] **Step 2:** Run the test. Expected: FAIL.
- [ ] **Step 3:** Implement by reading the recorded new `account.move` lines before rollback.
- [ ] **Step 4:** Re-run. Expected: PASS. Also run on a fresh database without `account` (`-i preview_mode`). Expected: PASS, test skipped.
- [ ] **Step 5:** Commit on the task branch and open a PR against the series branch (see `CONTRIBUTING.md`).

---

### Task 6: Client service, switch, dialog, toast (19.0)

**Files:**
- Create: `static/src/preview_service.js`, `preview_dialog.js`, `preview_dialog.xml`, `preview_switch.js`, `preview_switch.xml`, `preview_toast.js`, `preview.scss`

**Interfaces:**
- Consumes: routes from Task 4, `session_info.preview_mode_enabled`.
- Produces: a service `preview_mode` that wraps `env.services.action.doActionButton`. For `params.type === 'object'` with the switch on, it calls `/preview_mode/run`; empty `changes` runs the original; otherwise it opens `PreviewDialog` with props `{ title, summary, warnings, changes, journal, confirmLabel, onConfirm, onBack }`. `onConfirm` runs the original `doActionButton` with `context.preview_mode_token = <uuid>`, then calls `/preview_mode/created` and shows a toast with one link per record. `onBack` only closes the dialog.
- Switch: a toggle on the right side of the control panel, label `Preview mode`, writing `preview_mode_enabled` on the current user.

- [ ] **Step 1:** Build per the Interfaces, following the design document's section 3 for every visible string and layout rule.
- [ ] **Step 2:** Manual check: enable the switch, open a draft record with a Confirm-type button, click it. Expected: popup titled `Preview: <label>`, exact subtext, What/Where table, footer `[<label>] [Go back]`. Click `Go back`. Expected: record unchanged in the database, no message in chatter.
- [ ] **Step 3:** Manual check: click the button again, then the primary button. Expected: real action runs once, toast appears with clickable links, each opens its record.
- [ ] **Step 4:** Manual check, switch off. Expected: no `/preview_mode/run` call in the network tab and normal behaviour.
- [ ] **Step 5:** Manual check: click Print and a smart button with the switch on. Expected: no popup.
- [ ] **Step 6:** Manual check with a dirty form: edit a field, click the button. Expected: the edit is saved first as in stock Odoo, then the popup shows only the button's effects.
- [ ] **Step 7:** Commit on the task branch and open a PR against the series branch (see `CONTRIBUTING.md`).

---

### Task 7: Layout hardening and Store assets (19.0)

**Files:**
- Modify: `static/src/preview.scss`, `static/src/preview_dialog.xml`
- Create: `static/description/icon.png`, `static/description/index.html`

- [ ] **Step 1:** Manual stress check: a click producing very long names, 9-digit amounts and 40 lines. Expected: names wrap, amounts stay on one line right-aligned, only the middle scrolls, footer buttons always visible, nothing overlaps.
- [ ] **Step 2:** Manual check in Arabic (user language `ar_001`). Expected: dialog mirrors, numbers keep left-to-right inside, no overlap.
- [ ] **Step 3:** Manual check at phone width. Expected: dialog is full width, footer pinned.
- [ ] **Step 4:** Write `index.html` (app-neutral copy: what it does, three screenshots from sales, inventory and accounting) and the icon. Expected: Odoo Apps list shows the icon and description.
- [ ] **Step 5:** Milestone 1 acceptance: run the spec's Done list on 19.0 (switch, popup, Where, journal view, toast links, no commit, no email sent, no sequence burned). Expected: all pass. Open the milestone 1 PR against `19.0`.

---

### Task 8: Port to 18.0, 17.0, 16.0, 20.0

One pass per version, in this order, each ending with the same acceptance as Task 7 step 5.

**Files per version:** the same module tree on the branch named for the version, cloned at `odoo-<v>/addons/preview_mode`.

- [ ] **Step 1 (per version):** The branch `<v>` is cut from `19.0`. Its clone sits at `odoo-<v>/addons/preview_mode` and is listed in that Odoo checkout's `.git/info/exclude`. Install on a fresh `pm<v>` database.
- [ ] **Step 2 (per version):** Adjust and re-run the Python tests. Known differences to handle: controller RPC `type='json'` on 16.0, 17.0, 18.0 versus `'jsonrpc'` on 19.0, 20.0; manifest version prefix; cursor commit neutralisation technique; `session_info` location; the `readonly` route flag only exists on 18.0 and later.
- [ ] **Step 3 (per version):** Port the frontend. 18.0 and 17.0: same service approach on `doActionButton` in `action_service.js` (signature differs, see `odoo-18.0/addons/web/static/src/webclient/actions/action_service.js:1442` and `odoo-17.0/...:1229`). 16.0: OWL 1 and legacy widgets, wrap `doActionButton` at `action_service.js:1267`, and check legacy views that bypass it. 20.0: the code moved to `webclient/actions/action_plugin.js` (plugin architecture), so write the wrapper against that file.
- [ ] **Step 4 (per version):** Run Task 6 steps 2 to 6 manually and Task 7 steps 1 to 3. Expected: same results as 19.0.
- [ ] **Step 5 (per version):** Open a port PR against branch `<v>`. Repeat for the next version.

---

## Self-review notes

- Spec coverage: intent and goals map to Tasks 2 to 6; non-goals need no task; anti-goals are pinned by Task 3 tests; UX section by Tasks 6 and 7; Where lookup by Task 3; toast links by Tasks 4 and 6; repo and versions by Tasks 1 and 8; security by `SELF_WRITEABLE_FIELDS` and no `sudo` in Task 4.
- Open owner items from the spec (price, support policy) are not in any task.
- Automated tests cover the Python engine; frontend is verified by numbered manual steps with expected results.
- Layout change from the spec: the repo root is the module (spec section 6 had a nested `preview_mode/` folder), so a clone drops straight into `addons/`. The spec was updated to match on 2026-11-02.
