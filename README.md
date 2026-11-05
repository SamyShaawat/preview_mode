<img src="static/description/icon.png" alt="Preview Mode icon" width="64" align="right">

# Preview Mode

**See what a button click will do before it does it.**

Preview Mode is an Odoo app for every user of every app. Turn on the Preview toggle in the top bar, click a button that changes data (Confirm, Validate, Post, and so on), and a popup lists what the click would create, change or delete, and where each change lands in Odoo's menus. Then you confirm for real or go back. Nothing from the click is saved during the preview.

> **Status: in development.** Built so far: the module skeleton, the change recorder (it records what a click would create, change or delete), and the safe-run guards in review (they make sure a preview never saves, emails, calls out or uses real numbers). The switch and the popup are not built yet, so there is nothing to click today. The design and plan are in [Docs](#docs).

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

- It never saves anything: the click runs inside a database savepoint that is always rolled back.
- It never sends an email. Emails the click would send are listed as "queued, not sent".
- It never calls an outside service. Outgoing web requests are blocked and reported as a warning.
- It never uses up a real sequence number. Numbers show as a placeholder until the real run.

## Limits, stated plainly

- **Preview incomplete.** If a click opens a separate database connection or calls an outside service, the preview cannot be sure of the result. It says "Preview incomplete" instead of an all-clear.
- **An estimate, not a promise.** The real run happens later, so sequence numbers (shown as `(new)`), random values, the time and changes made by other users can differ. The popup says so.
- **Unsaved edits are saved first.** If you edited the form and then click a button, Odoo saves your edit as it normally does, then the preview shows only what the button does. The popup text says "Nothing from this click has been saved yet" for that reason.
- **Button types.** Version 1 covers buttons that call a method on a model (the usual Confirm, Validate and Post buttons, including those inside wizards).
- **Not covered:** printing and reports, imports, scheduled actions, server automations, and any undo after a real run.
- **What counts as a change.** Audit fields, tracking values, followers, chatter notes, attachments and wizard records are ignored, so the popup lists real business changes only.

## Compatibility

| Branch | Odoo version | Status |
|---|---|---|
| `16.0` | Odoo 16.0 | skeleton and change recorder |
| `17.0` | Odoo 17.0 | skeleton and change recorder |
| `18.0` | Odoo 18.0 | skeleton and change recorder |
| `19.0` | Odoo 19.0 | skeleton and change recorder |
| `20.0` | Odoo 20.0 | reference version, default branch: skeleton and change recorder, guards in review |

Works on Community, and it works when Enterprise is installed. Depends only on `base` and `web`.

## Install

Clone the branch that matches your Odoo version into your addons path under the folder name `preview_mode`, then update the apps list and install **Preview Mode**:

```bash
git clone --branch 20.0 https://github.com/SamyShaawat/preview_mode.git /path/to/addons/preview_mode
```

(The repository is private for now, so you need access to it.)

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
