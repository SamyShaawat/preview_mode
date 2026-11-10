# Preview Mode: developer guide

## Architecture

The repository root holds the community files (README, LICENSE, docs, CI, scripts). The module is the folder `preview_mode/` (depends on `base` and `web`); the paths below are relative to it. This is the layout the Odoo Apps Store expects: it registers a Git repository and finds modules as folders in it.

| File | Role |
|---|---|
| `controllers/main.py` | `POST /preview_mode/run` (build a preview) and `POST /preview_mode/created` (records for the toast). Plain `auth='user'`, never `sudo`, never readonly. |
| `models/payload.py` | `build_preview()`: checks, runs the method in `safe_run`, merges changes, builds summary, journal view and sections. Holds `UNSAFE_MODELS`, the timeout, the per-user advisory lock. |
| `models/guards.py` | `safe_run()` and the guards: no-op commit, rollback marks incomplete, `(new)` sequences, recorded not sent email, blocked `requests`/`urllib`/`http.client`, no second DB cursor. |
| `models/recorder.py` | `ChangeRecorder`: collects creates, writes, unlinks and queued `mail.mail` rows. The ignore lists `IGNORED_MODELS` and `IGNORED_FIELDS` live here only. |
| `models/base.py` | Hooks `create`, `write`, `unlink` and `_write_multi` on `base`; also stores created ids for the toast when the context carries a token. |
| `models/rawwrites.py` | Compares `pg_stat_xact_user_tables` counters before and after the click to flag raw SQL writes. |
| `models/where.py` | `locate()`: turns a model into the menu path the user can open. |
| `models/formatting.py` | Formats values the way the form shows them. |
| `models/section.py` | `preview.mode.section`, the extension point. |
| `models/created.py` | Transient `preview.mode.created`: created ids per token and user. |
| `models/res_users.py`, `models/ir_http.py` | The per-user flag `preview_mode_enabled` and its session values (`preview_mode_enabled`, and `preview_mode_available`, which is false when the kill switch is off and hides the systray item). |
| `static/src/preview_service.js` | Wraps `doActionButton`, calls `/preview_mode/run`, opens the popup or the "Preview unavailable" dialog, shows the toast. |
| `static/src/preview_list.js`, `preview_statusbar.js` | Previews for list Archive/Unarchive/Delete and status bar clicks. |
| `static/src/preview_dialog.*`, `preview_toggle.*`, `preview.scss` | Popup, top-bar switch, styles. |
| `tests/`, `static/tests/tours/` | Python tests and browser tours. |

Flow: the client sends model, method, ids and context to `/preview_mode/run`. The server runs the method under the user's rights inside a savepoint, flushes, reads the recorder, rolls back and returns JSON. The client decides on the flag `show`, never on an empty change list.

## Local development

A clone of this repo sits at `odoo-<V>/addons/preview_mode`, so the module is at `odoo-<V>/addons/preview_mode/preview_mode`. Odoo only finds a module in a folder listed in `addons_path`, so add the clone itself to `odoo.conf`:

```
addons_path = <...>/odoo-<V>/addons/preview_mode,<existing entries>
```

Or pass it on the command line: `--addons-path=<...>/odoo-<V>/addons/preview_mode,<odoo addons>`. After pulling this layout change, restart the server and press Update Apps List. Test command from the Odoo checkout:

    ./odoo-bin -c odoo.conf --addons-path=<repo root>,<odoo addons> -d <db> -u preview_mode --test-tags /preview_mode --stop-after-init

## Extension point

Another module can add a table to the popup. Make a small glue module that depends on `preview_mode` and on the app it describes; with `auto_install` it loads only when both are present.

`my_glue/__manifest__.py`:

```python
{
    'name': 'Preview Mode: Inventory impact',
    'version': '17.0.1.0.0',
    'depends': ['preview_mode', 'stock'],
    'auto_install': True,
    'license': 'LGPL-3',
}
```

`my_glue/models/preview_section.py`:

```python
from odoo import api, models


class PreviewModeSection(models.AbstractModel):
    _inherit = 'preview.mode.section'

    @api.model
    def _preview_sections(self, model, method, res_ids, changes):
        sections = super()._preview_sections(model, method, res_ids, changes)
        if model == 'stock.picking' and method == 'button_validate':
            moves = self.env['stock.move'].browse(
                c['res_id'] for c in changes if c['model'] == 'stock.move')
            sections.append({
                'title': 'Inventory impact',
                'columns': ['Product', 'Destination', 'Quantity'],
                'rows': [[m.product_id.display_name, m.location_dest_id.display_name, str(m.quantity)]
                         for m in moves],
            })
        return sections
```

I installed this module on a demo database with Sales and Inventory and called `/preview_mode/run` for `stock.picking.button_validate` on a ready delivery: the response contained the section with one row per product, and the picking stayed `assigned` afterwards.

Rules:

- Arguments: the clicked `model`, `method` and `res_ids`, and `changes`, the merged list the popup shows (dicts with `kind` of `new`, `changed` or `deleted`, plus `model`, `res_id`, `what`, `fields`).
- Return `title`, `columns` (optional) and `rows` (lists of text). A section with no rows is not shown.
- It runs inside the preview, before the rollback, so changed records can still be read. Read only: do not write.
- Always call `super()` and append. An exception in your code is swallowed and the popup opens without your section.
- Sections appear in the popup after the journal tables and in the Copy text.

## Run the tests

From the `odoo-17.0` checkout, with the module in the addons path:

```bash
./odoo-venv/bin/python odoo-bin -c odoo.conf -d pm17 -u preview_mode \
  --test-tags /preview_mode --http-port=8079 --stop-after-init
```

Expect `0 failed, 0 error(s) of N tests`. Use a free HTTP port that is not your running server's. The mail test needs the `mail` app, so run it on a scratch database created with `-i mail,preview_mode --without-demo=all`. Browser tours need headless Chrome and skip without it.

If your venv's `python` lacks `babel` (this happened with a Python 3.14 venv), run the same command with Python 3.12: `PYTHONPATH=<venv>/lib/python3.12/site-packages /usr/bin/python3.12 odoo-bin ...`. On 17.0 it gives `0 failed, 0 error(s) of TESTCOUNT tests` on a database with `mail`.

Lint: `pre-commit run --all-files` (see `CONTRIBUTING.md`).

## Porting notes

This is the 17.0 branch, ported from 20.0. Version differences are marked `# PORT:`; find them with `grep -rn "PORT:" .`. On 17.0 they are:

- `__manifest__.py` and `security/`: `ir.model.access.csv` plus an `ir.rule` (20.0 has one `ir.access.csv` with a domain).
- `controllers/main.py`: route type `json` (20.0: `jsonrpc`).
- `models/recorder.py`: `_can_read` uses `check_access_rights` and `check_access_rule` (20.0: `has_access`); the old-value query is plain SQL (20.0: `odoo.tools.SQL`).
- `models/base.py`: delayed writes arrive in `_write(vals)` (20.0: `_write_multi(vals_list)`).
- `models/payload.py`: config parameters are read with `get_param` (20.0: `get_int/get_float/get_bool`); `call_kw` is imported from `odoo.api`.
- `models/res_users.py`: `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` (20.0: `user_writeable=True`).
- `models/formatting.py`: `format_datetime(..., dt_format=False)` so datetimes follow the user's language format.
- `models/rawwrites.py`: `RAW_UPDATE_OK`, the partner rank UPDATE of Accounting.
- JS: `/** @odoo-module **/` header, `reactive` and `useState` (Owl 2), `rpc` and `user` services, static `props`, `fa fa-eye` icon, `ListController.getStaticActionMenuItems` patch so Archive skips Odoo's question.
- Tours: `test: true`, `run: () => {}` on check-only steps, `/web#action=...` start URL.
- Tests: 17.0 field names (`acc_number`, `tax_id`, `detailed_type`, `reversal_move_id`, `groups_id`), `set_param`.

Ports are one pull request per version; see `CONTRIBUTING.md`.
