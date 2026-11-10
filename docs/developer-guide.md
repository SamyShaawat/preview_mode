# Preview Mode: developer guide

## Architecture

The repo root is the module (`preview_mode`, depends on `base` and `web`).

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
| `models/res_users.py`, `models/ir_http.py` | The per-user flag `preview_mode_enabled` and its session value. |
| `static/src/preview_service.js` | Wraps `doActionButton`, calls `/preview_mode/run`, opens the popup or the "Preview unavailable" dialog, shows the toast. |
| `static/src/preview_list.js`, `preview_statusbar.js` | Previews for list Archive/Unarchive/Delete and status bar clicks. |
| `static/src/preview_dialog.*`, `preview_toggle.*`, `preview.scss` | Popup, top-bar switch, styles. |
| `tests/`, `static/tests/tours/` | Python tests and browser tours. |

Flow: the client sends model, method, ids and context to `/preview_mode/run`. The server runs the method under the user's rights inside a savepoint, flushes, reads the recorder, rolls back and returns JSON. The client decides on the flag `show`, never on an empty change list.

## Extension point

Another module can add a table to the popup. Make a small glue module that depends on `preview_mode` and on the app it describes; with `auto_install` it loads only when both are present.

`my_glue/__manifest__.py`:

```python
{
    'name': 'Preview Mode: Inventory impact',
    'version': '20.0.1.0.0',
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

From the `odoo-20.0` checkout, with the module in the addons path:

```bash
./odoo-venv/bin/python odoo-bin -c odoo.conf -d pm20 -u preview_mode \
  --test-tags /preview_mode --http-port=8079 --stop-after-init
```

Expect `0 failed, 0 error(s) of N tests`. Use a free HTTP port that is not your running server's. The mail test needs the `mail` app, so run it on a scratch database created with `-i mail,preview_mode --without-demo=all`. Browser tours need headless Chrome and skip without it.

If your venv's `python` lacks `babel` (this happened with a Python 3.14 venv), run the same command with Python 3.12: `PYTHONPATH=<venv>/lib/python3.12/site-packages /usr/bin/python3.12 odoo-bin ...`. I ran it that way on a `pm20` clone: `0 failed, 0 error(s) of 85 tests`.

Lint: `pre-commit run --all-files` (see `CONTRIBUTING.md`).

## Porting notes

Only 20.0 is supported today. Version differences are kept in places marked `# PORT:`; find them with `grep -rn "PORT:" .`. They cover, among others: the ACL file (`ir.access.csv` on 20, `ir.model.access.csv` before), the route type (`jsonrpc` on 19 and 20, `json` before), `user_writeable` against `SELF_WRITEABLE_FIELDS`, `has_access`, the config parameter getters, the `doActionButton` location in JS and the list method names in `preview_list.js`. Ports are one pull request per version; see `CONTRIBUTING.md`.
