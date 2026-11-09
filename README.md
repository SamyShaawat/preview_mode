<img src="static/description/icon.png" alt="Preview Mode icon" width="64" align="right">

# Preview Mode

[![tests](https://github.com/SamyShaawat/preview_mode/actions/workflows/tests.yml/badge.svg?branch=20.0)](https://github.com/SamyShaawat/preview_mode/actions/workflows/tests.yml)

**See what a button click will do before it does it.**

Preview Mode is an Odoo app for every user of every app. Turn on the Preview toggle in the top bar, click a button that changes data (Confirm, Validate, Post, and so on), and a popup lists what the click would create, change or delete, and where each change lands in Odoo's menus. Then you confirm for real or go back. Nothing from the click is saved during the preview.

> **Status: working on 20.0, not yet ported.** On Odoo 20.0 the top-bar switch, the popup, the journal-entry view and the toast after a real run all work. Branches 16.0 to 19.0 are older and do not have these yet; they will be ported one by one once 20.0 is frozen. The design and plan are in [Docs](#docs).

## Why

Confirming a vendor bill posts journal entries. Confirming a sales order creates deliveries. Validating a transfer moves stock. These clicks are hard to undo, and Odoo does not show you the result first. Preview Mode does.

It works on any button that changes data, in any app, for any user. There is no list of supported apps, models, buttons or users, and nothing to configure per app: install it, turn the Preview toggle on, and it applies everywhere.

It is not an accounting module. Sales, purchase, inventory, manufacturing, CRM, HR, project and third-party apps all get the same preview.

## How it works for the user

1. Click the **Preview mode** toggle button in the top bar. It is on every page, and it lights up while preview is on. Click it again to turn it off. Your choice is remembered for your user.
2. Click a button that changes data, for example **Confirm** on a vendor bill.
3. A popup titled **Preview: Confirm** opens with the message "This is a preview. Nothing from this click has been saved yet."
4. Read it, then press **Confirm** to run the real action, or **Go back** to leave everything as it was.
5. After a real run, a message lists the records that were created. Each one is a link that opens the record.

Buttons that only open something (smart buttons, Print, filters, buttons that just open a wizard) do not show a popup. They run as usual.

## What the popup shows

- **Warnings first.** If the click would fail, for example because the period is locked, you see "Confirming will fail: ..." in a yellow banner. The Confirm button stays clickable. The real run decides, and a failed run changes nothing.
- **A one-sentence summary**, such as "Confirming will create 1 journal entry, update this bill, and queue 1 email (not sent during the preview)."
- **What will happen**, one row per change, in two columns:
  - **What:** New, Changed or Deleted, with changed values shown as old value (struck through) then new value.
  - **Where:** the place in Odoo in plain menu words, such as `Accounting > Accounting > Journal Entries`, or "Here, on this bill" for the record you are on.
- **Journal entry lines** (account, debit, credit, balanced total) when the click would create a journal entry and the accounting app is installed.

The popup uses Odoo's own dialog. Long names wrap, numbers stay on one line, only the middle part scrolls so the buttons are always visible, and the layout mirrors for right-to-left languages such as Arabic.

## What a preview never does

- It does not save database changes: the click runs inside a database savepoint that is always rolled back.
- It does not send email. Emails the click would send, directly or as queued mail records, are listed as "not sent during the preview".
- It blocks outgoing web requests made with the Python `requests` library and reports them as a warning.
- It does not use up a real sequence number. Numbers show as a placeholder until the real run.

These guards cover what Odoo's own code does. See the limits below for what they cannot cover.

## Limits, stated plainly

- **Preview incomplete.** If a click opens a separate database connection, calls an outside service through `requests`, or rolls back by itself, the preview says "Preview incomplete" instead of an all-clear.
- **What a preview can still miss.** A savepoint only undoes database rows. Writes made with raw SQL (`cr.execute`) are detected by comparing PostgreSQL's per-transaction row counters before and after the click; the preview then says "Preview incomplete" and names the table. The one case it cannot see is a raw `UPDATE` on a table the click also changed through the ORM. Not covered today: outgoing calls made with anything other than `requests` (for example `urllib`, `http.client`, plain sockets), files written to the filestore, work done in threads a button starts, and long Python loops (the timeout stops slow database statements only). A preview that looks complete can still miss these. Treat it as a careful estimate.
- **Cost.** The click runs twice, once as a preview and once for real, and the preview holds database locks until it finishes. Heavy buttons (posting thousands of invoices) take about twice as long.
- **An estimate, not a promise.** The real run happens later, so sequence numbers (shown as `(new)`), random values, the time and changes made by other users can differ. The popup says so.
- **Unsaved edits are saved first.** If you edited the form and then click a button, Odoo saves your edit as it normally does, then the preview shows only what the button does. The popup text says "Nothing from this click has been saved yet" for that reason.
- **Button types.** Version 1 covers buttons that call a method on a model (the usual Confirm, Validate and Post buttons). Wizard buttons use the same type but are not yet tested one by one. Not covered: stage changes in the status bar, list-view mass actions such as Archive and Delete, and buttons that open another action.
- **Not covered:** printing and reports, imports, scheduled actions, server automations, and any undo after a real run.
- **What counts as a change.** Audit fields, tracking values, followers, chatter notes, attachments and wizard records are ignored, so the popup lists real business changes only.

## Compatibility

| Branch | Odoo version | Status |
|---|---|---|
| `16.0` | Odoo 16.0 | not ported, older skeleton only |
| `17.0` | Odoo 17.0 | not ported, older skeleton only |
| `18.0` | Odoo 18.0 | not ported, older skeleton only |
| `19.0` | Odoo 19.0 | not ported, older skeleton only (first port planned) |
| `20.0` | Odoo 20.0 | reference version and default branch: working, tested on Community |

Works on Community, and it works when Enterprise is installed. Depends only on `base` and `web`.

## Configure (optional)

Nothing is required. An administrator can set these system parameters (Settings > Technical > System Parameters):

| Key | Default | Meaning |
|---|---|---|
| `preview_mode.enabled` | on | Kill switch. Set to `False` to hide the toggle and stop previews for every user; buttons then run as in stock Odoo. |
| `preview_mode.timeout` | 10 | Seconds a preview may spend in database statements before it stops with "timed out". |
| `preview_mode.max_records` | 0 | Skip the preview when a click acts on more records than this (0 = no limit). The click then runs as usual. |

## Install

Clone the branch that matches your Odoo version into your addons path under the folder name `preview_mode`, then update the apps list and install **Preview Mode**:

```bash
git clone --branch 20.0 https://github.com/SamyShaawat/preview_mode.git /path/to/addons/preview_mode
```


## Technical facts

- Technical name: `preview_mode`. Display name: Preview Mode.
- Repo root is the Odoo module itself (the manifest sits at the root). One branch per Odoo version.
- Security: available to internal users. A preview runs with the user's own access rights, so it can never show or do more than the real click.
- Menu paths shown in the "Where" column only include menus the user can open.
- Enterprise: it stays a Community module with no Enterprise dependency. Working next to Enterprise is a requirement, checked per version.
- Odoo.sh: built to work there. No external Python packages, no system changes, no files written outside Odoo's own storage, and safe with several workers. On Odoo.sh, add this repo as a git submodule named `preview_mode` in your project repository.
- License: LGPL-3 (GNU Lesser General Public License v3). See [LICENSE](LICENSE). Free to use; the module follows OCA conventions in its own repository.

## Docs

- Design: [`docs/superpowers/specs/2026-11-02-preview-mode-design.md`](docs/superpowers/specs/2026-11-02-preview-mode-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-11-02-preview-mode.md`](docs/superpowers/plans/2026-11-02-preview-mode.md)
