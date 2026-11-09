<img src="static/description/icon.png" alt="Preview Mode icon" width="64" align="right">

# Preview Mode

[![tests](https://github.com/SamyShaawat/preview_mode/actions/workflows/tests.yml/badge.svg?branch=20.0)](https://github.com/SamyShaawat/preview_mode/actions/workflows/tests.yml)
![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue.svg) ![Odoo 20.0](https://img.shields.io/badge/odoo-20.0-875a7b.svg)

Preview Mode shows what a button click would create, change or delete, and where, before you commit to it. With the switch in the top bar on, a button that changes data opens a popup instead of acting; nothing is saved until you press Confirm.

It works on every such button in every app, for every internal user. There is no per-app or per-user setup.

## Install

Put the `20.0` branch in your addons path under the folder name `preview_mode`, update the apps list and install **Preview Mode**. It depends only on `base` and `web`.

```bash
git clone --branch 20.0 https://github.com/SamyShaawat/preview_mode.git /path/to/addons/preview_mode
```

On Odoo.sh, add the repository as a git submodule named `preview_mode`.

## Use

1. Click the eye switch in the top bar. It stays on until you click it again, and Odoo remembers it per user.
2. Click a button that changes data, for example Confirm on a quotation or Post on an invoice.
3. A popup titled `Preview: <button name>` lists the changes. **What** is New, Changed (old value struck through, then the new one) or Deleted. **Where** is the Odoo menu path, for example `Sales › Orders › Quotations`. A click that creates a journal entry also gets a Debit/Credit table.
4. Press the primary button (it has the same label as the button you clicked) to run it for real, or **Go back** to leave everything untouched. **Copy** puts the preview on the clipboard as text.
5. After a real run, a notification links to the records that were created.

Buttons that change nothing (smart buttons, report printing, buttons that only open a wizard) run normally without a popup. If the click would fail, the popup says `Confirming will fail: <message>`; Confirm stays available because the real run decides.

More detail, with screenshots, is in the [user guide](docs/user-guide.md).

## What is covered

| Click | Previewed |
|---|---|
| Buttons that call a model method (Confirm, Validate, Post, wizard buttons) | Yes |
| List view Archive, Unarchive, Delete on the selected records | Yes (Odoo's own "Are you sure?" comes first) |
| Status bar stage click | Yes, as the write of the stage field at click time |
| Server actions in the list Actions menu | No |
| Kanban drag and drop | No |
| Delete from a form's Actions menu | No (tested: the record is deleted after Odoo's own question) |
| Buttons on module install/upgrade, Settings, `ir.model`, `ir.model.fields`, `ir.ui.view` | No, they run as usual: a savepoint cannot undo registry changes |
| Reports and printing, imports, scheduled actions, automations | No |

Audit fields, tracking values, followers, chatter messages and attachments are left out of the list.

## Settings

All optional. An administrator sets them in Settings > Technical > System Parameters.

| Key | Default | Effect |
|---|---|---|
| `preview_mode.enabled` | on | Set to `False` to stop previews for everyone. The click then runs as in stock Odoo and says "Preview Mode is switched off by your administrator." |
| `preview_mode.timeout` | 10 | Seconds a preview may spend in database statements (clamped to 1-120). Past that the popup says it timed out. |
| `preview_mode.max_records` | 0 | Skip the preview when a click acts on more records than this. 0 means no limit. |

## How it works

1. The browser asks `POST /preview_mode/run` before the click.
2. The server runs the clicked method with the user's own rights inside a database savepoint.
3. A recorder on `create`, `write`, `unlink` and `_write_multi` collects the changes. `flush_all()` runs before the end so delayed writes (recomputed totals, states) are seen.
4. The savepoint is rolled back, always.
5. Raw SQL writes are caught by comparing PostgreSQL's per-transaction row counters before and after.
6. The client shows the popup. On Confirm the real click runs, and the ids it creates are stored for the notification.

## Safety guards during a preview

- `commit` is a no-op on the preview's cursor, and `rollback` marks the preview incomplete.
- Sequences return `(new)`, so no real number is used.
- Emails are recorded, not sent. Queued `mail.mail` rows are listed too.
- Outgoing calls through `requests`, `urllib` and `http.client` are blocked and reported.
- Opening any other database connection (cron, bus) marks the preview incomplete. Post-commit callbacks are dropped.
- One preview per user at a time (advisory lock). A second one is skipped with a notice.

## What it cannot promise

A preview is an estimate. Sequence numbers, random values, the time and other users' changes can differ at the real run. It can miss plain sockets, files written to the filestore, work in threads, and Python loops that never touch the database (the timeout only bounds SQL statements). A raw `UPDATE` on a table the ORM also wrote in the same click is not detected. When the module sees something it cannot cover, the popup says "Preview incomplete" instead of an all-clear.

The click runs twice, so a heavy button takes about twice as long.

## Extending the popup

Another module can add its own table to the popup by overriding `preview.mode.section._preview_sections`. See the [developer guide](docs/developer-guide.md#extension-point) for a working example.

## Compatibility

Odoo 20.0 only, Community; it installs and runs with Enterprise but Enterprise 20 has not been tested here. Other versions are planned and not ready. The `16.0` to `19.0` branches hold older, incomplete code and should not be used.

## Documentation

- [User guide](docs/user-guide.md)
- [Developer guide](docs/developer-guide.md)
- [Changelog](CHANGELOG.md)

## Contributing

Every change is a pull request against the version branch. Outside contributions need a DCO sign-off. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

LGPL-3, see [LICENSE](LICENSE). Author: Samy Mostafa Shaawat.
