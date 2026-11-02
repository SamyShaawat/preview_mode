# Preview Mode: design

Date: 2026-11-02. Status: draft for approval. Technical module name: `preview_mode` (author's call).

## 1. Intent and why

An accountant is afraid of clicking Confirm on a vendor bill and posting wrong journal entries. Posting is hard to undo, so they want to see the result first. The same fear exists everywhere in Odoo: confirming a sales order creates deliveries, validating a transfer moves stock, and so on.

Preview Mode lets any user see what a button click would do before it does it. With the Preview mode toggle on, clicking a button that would change data opens a popup listing what would be created, changed or deleted, and where each change lands in Odoo's menus. The user then confirms for real or goes back. Nothing is saved during the preview.

The product is a paid app for the Odoo Store, for Community (and so Enterprise), versions 16.0, 17.0, 18.0, 19.0 and 20.0.

Audience: every user of every app. It is not an accounting module and not for accountants only. Sales, purchase, inventory, manufacturing, HR, CRM, project, and any third-party app all get the same preview on any button that changes data. The owner's example of the fear was an accountant posting wrong journal entries, and the journal entry view exists because that is the sharpest case, but it is one view among many, not the product's identity. Marketing, naming, screenshots and defaults must stay app-neutral.

## 2. Goals, non-goals, anti-goals

Goals
- Any button that changes data, in any app, can be previewed.
- The popup answers two questions: what would change, and where in Odoo it lands (in menu words, not model or table names).
- Any user, in any app, gets the same popup. When a click would create a journal entry, that entry is also shown as a Debit/Credit table, as an extra view for accounting clicks.
- After the user confirms, the result toast links to each created record.
- Works on Community, no Enterprise dependency. Same behaviour on 16.0 to 20.0.
- Easy to understand: no jargon, native Odoo look, Arabic (RTL) works.
- Zero effect on users or forms when Preview mode is off.

Non-goals
- No undo of real actions after they run.
- No simulation of external services (payment providers, e-invoicing, shipping carriers). They are detected and flagged, not simulated.
- No preview of printing, reports, imports, scheduled actions or server-side automations.
- No dashboard, history or audit log of previews.
- No Enterprise-only features.

Anti-goals (failure even if it technically works)
- A preview that saves anything, sends an email, or calls an outside service.
- A preview that burns real sequence numbers (invoice, delivery, etc.).
- A preview that says "all fine" when it could not fully run (a blocked external call, a separate database connection). It must say it is incomplete instead.
- A popup or toggle that looks like generic AI styling, or that overlaps, truncates or collides text.
- Slowing normal use when the toggle is off.

## 3. The user experience (decided by the owner unless marked)

Turning it on
- A **Preview mode** toggle button in the top bar (a systray item), always visible on every page and in the same place on Community and Enterprise. Click it to turn preview on, click it again to turn it off. It shows a clear state: pressed look and accent colour while on, plain while off, `aria-pressed`, a tooltip, and it works with the keyboard. Owner request 2026-11-02: a toggle button at the top of the page. The author put it in the systray (top bar, right side) because that is the stable, documented place for global toggles on 16 to 20; the left side of the bar differs between Community and Enterprise.
- Per user, remembered between sessions (author's call).

What counts as a button to preview
- Only buttons that change data. Smart buttons, Print, Open, filters and anything read-only behave normally with no popup.
- Mechanism (author's call, owner agreed in principle): with the toggle on, the click runs inside a rollback. If nothing real would be created, changed or deleted, the click runs normally and no popup appears. So no per-button list is needed.
- Records of transient (wizard) models are ignored when deciding. A click that only opens a wizard is not a change.
- In scope for v1: buttons that call a method on a model (`type="object"`), on forms, statusbars, list headers and inside wizards.

The popup (see mockups in section 9)
- Title: "Preview: <button label>", for example "Preview: Confirm". Repeats the clicked button's word.
- Subtext: "This is a preview. Nothing from this click has been saved yet."
- Order of content, top to bottom: warning banner (if any), one-sentence summary, a "What will happen" table, then a journal-entry lines table when one would be created.
- Warning banner is yellow, the only use of yellow. When the click would fail, wording is "Confirming will fail: <reason>", not just the reason. The Confirm button stays clickable (owner agreed: the real run is the authority and fails harmlessly).
- "What will happen" table: two columns, What and Where. Each row starts with New, Changed or Deleted. Changed values show the old value struck through then the new value.
- Where uses Odoo menu paths, for example "Accounting > Accounting > Journal Entries". The record the user is already on is "Here, on this <record type>". Records with no menu of their own are grouped under their parent. If no menu fits, plain record name.
- Journal entry lines: Account, Debit, Credit, with a Total row marked balanced. Shown when a new journal entry (`account.move`) would be created and the accounting app is installed. No dependency on accounting.
- Footer, left to right: primary button with the same word as the clicked button (for example "Confirm"), then "Go back". The primary button performs the real click. "Go back" instead of "Cancel" because many forms already have a Cancel that does something else.
- Header and footer are fixed. Only the middle scrolls, so the primary button is always visible.
- Long names wrap, numbers stay on one line right-aligned in a column that does not shrink, no absolute positioning. Layout mirrors in RTL using logical start/end. Mobile width: full-width dialog.
- Use Odoo's own dialog component, not custom positioning, so stacking order is handled by Odoo.
- Native Odoo look: one accent (Odoo purple `#714b67`), flat tables, no pills, no emoji, no gradients.

After the user confirms
- A toast: "<what> confirmed" with a list of created records, each a clickable link that opens the record.

## 4. How it works (author's calls, not yet agreed by the owner)

Interception
- With the toggle on, the web client adds a context flag to the button call. On the server a controller override of the button-call route runs the method in preview. Route name and shape differ by version and must be verified per branch (known route: `/web/dataset/call_button`).
- The real run (user presses Confirm in the popup) calls the same method with the same arguments. Its behaviour is unchanged. The one addition: the server also notes the ids and names of records created during that run, only to build the toast links. It changes and blocks nothing. Links come from the real run, never from the preview's rolled-back ids.
- Unsaved edits: the web client normally saves a dirty form before calling an object button. That save is kept as is (it is the user's own draft edit) and happens before the preview starts. The popup subtext therefore says "Nothing from this click has been saved yet", not "nothing saved". The popup shows only what the button itself would do. Previewing the save and the button together is out of scope.
- What counts as a change: ignore audit fields (`write_date`, `write_uid`, `create_date`, `create_uid`), `mail.tracking.value`, `mail.followers`, `mail.message` notes and logs, `ir.attachment`, and transient models. Emails that would be sent are shown as "Email to <recipient> (queued)". If everything else is empty, the click runs normally with no popup. Anything not on this ignore list counts and is shown. The builder may extend the list when a version shows noise, and must keep the list in one place.

Preview run
- Open a database savepoint, run the method as the current user (same access rights as the real run), collect changes, then always roll back to the savepoint, whatever happens.
- Change recorder: during the run, hook create, write and unlink on all models. Record model, record id/name, field, old value, new value, and for creates the record's displayed name and parent.
- Never commit. Any `commit()` during preview must be neutralised. Methods that open a separate database cursor cannot be rolled back; detect and report "Preview incomplete" instead of showing a false all-clear. Exact technique varies by version; the builder must prove it on each branch.
- Sequences: replace sequence number allocation during preview with a placeholder such as "(new)" so no real number is consumed.
- Emails: outgoing emails created during preview are listed as queued "not sent". Make sure nothing is actually sent.
- External calls: during preview, block outgoing HTTP calls from the Python process and report "would call <host>" as a warning. Treat that as incomplete.
- Files: attachment files written to the file store are left for Odoo's own garbage collection.

The "where" lookup
- For each changed model, find the menu entry whose window action opens that model, using menus the current user can see. Pick the nearest to the root by sequence. Cache per request. Fall back to the parent record's location, then to the plain record type name.

Frontend
- Python and the "where" logic are shared across versions. The frontend is separate per version: 16.0 uses OWL 1 with legacy widgets, 17.0 to 20.0 use OWL 2 with the new form controller. 20.0 is the reference, so its web client (plugin-based action code in `action_plugin.js`) is studied first and older versions are ported from it.

Security
- Available to internal users (base.group_user). Runs with the user's own rights, so preview can never show or do more than the real click. Menu paths only include menus the user can open.

## 5. Constraints

- Python 3 as required by each Odoo version; JavaScript following each version's web client.
- Depends on `base` and `web` only. Must install on Community.
- Must work on Odoo.sh (owner requirement, 2026-11-02): no external Python packages and no `requirements.txt`, no system or `subprocess` calls, no writes to the file system outside Odoo's own storage, all state in the database (several workers share no memory), no route marked `readonly`, no dependence on `odoo.conf` options or server flags, no Enterprise-only code. Odoo.sh users add the repo as a git submodule named `preview_mode`.
- Must work when installed next to Odoo Enterprise (owner requirement, 2026-11-02): it stays a Community module with no Enterprise dependency, but it must install and run with the Enterprise addons present. Enterprise's `web_enterprise` replaces parts of the web client (navbar, control panel), so UI hooks use stable, documented entry points and the Preview mode switch must render in both layouts.
- No allow-list or deny-list of any kind: once the module is installed and the Preview mode toggle is on, it works on every button that changes data, in every app (core, Enterprise, third-party or custom), for every internal user. No per-app, per-model, per-button or per-user configuration.
- Licence: OPL-1, the Odoo Proprietary License v1.0 (owner decision, 2026-11-02). Store review required per version. A paid listing also needs `price` and `currency` in the manifest.
- No commit or push by the assistant: the owner commits.

## 6. Repository and versions

- One private GitHub repo, `SamyShaawat/preview_mode` (same as the module's technical name, so a plain clone lands in the right folder), with branches `16.0`, `17.0`, `18.0`, `19.0`, `20.0`. The repo root is the Odoo module itself (the manifest is at the root), so a clone loads straight from an addons folder. (Owner approved on 2026-11-02, replacing the earlier nested-folder layout.)
- Each `odoo-X.0/addons/preview_mode` is a clone of that repo with branch `X.0` checked out, so the module shows up in all five without hand-edited copies. Add `preview_mode` to each Odoo checkout's `.git/info/exclude` so Odoo's own repo stays clean.
- Build order: 20.0 as the reference and default branch, then 19.0, 18.0, 17.0 and 16.0. Shared Python is ported by cherry-pick; frontend ported by hand.
- Checkouts: all five exist at `/media/samy/Home/My-Github/Odoo/odoo-X.0/`, each with `odoo-venv/` (Python 3.12) and `odoo.conf`. 16.0 and 20.0 were cloned from GitHub on 2026-11-02 like the other three.
- Manifest version format follows Odoo: `20.0.1.0.0`, and so on per branch.
- Done means: milestone 1 is 20.0 working end to end (toggle, popup, Where column, journal entry view, toast links, no commit, no email sent, no real sequence number burned). Each other version is done when its branch meets the same list. The Store release can go version by version. The `20.0` branch exists on GitHub (checked 2026-11-02), so no fallback is needed; if it later turns out unusable, drop 20.0 and say so.

## 7. Left to the builder

- The exact interception route and client patch per version; exact way to neutralise commits and separate cursors on each version.
- How to render changes for fields types (many2one, selection, monetary, many2many) readably.
- The module's internal structure, test approach, manifest texts, icon and Store screenshots.
- Python and Odoo setup details for the two new checkouts.

## 8. Open items for the owner

- Price and support policy per version.
- Whether to prefer false warnings over false all-clears. Author's call: yes. When unsure, show "Preview incomplete".

## 9. Mockups

Approved visuals were shown in a browser session (three screens: the popup with a Where column, after-Confirm toast with links, and a stress test with long names, 9-digit amounts, many lines and Arabic). The final popup contents are described in section 3. Mockup HTML files live in the brainstorm session folder under the scratchpad and are throwaway. Recreate them from section 3 if needed.

## 10. Calls the author made (check these)

1. Module name `preview_mode`.
2. Toggle state remembered per user.
3. Detecting "would change data" by running inside a rollback, with no per-button list.
4. v1 covers `type="object"` buttons only.
5. Wizard-only (transient) records ignored when deciding whether to show the popup.
6. External HTTP calls are blocked during preview and flagged as incomplete.
7. Sequences replaced by placeholders during preview.
8. Restricted to internal users, no extra group.
9. License OPL-1 (decided by the owner, no longer just a default).
10. Build order 20, 19, 18, 17, 16. Changed by the owner on 2026-11-02: 20.0 is the reference and the default branch (it was 19.0).
11. The real run records created ids only to build toast links; it changes nothing else.
12. A dirty form is saved normally before the preview; the popup says "Nothing from this click has been saved yet".
13. Default ignore list for what counts as a change (audit fields, tracking, followers, chatter notes, attachments, transient models).
14. 20.0 working end to end is milestone 1; the Store release can go version by version.
15. Odoo.sh compatibility is a hard requirement (owner, 2026-11-02): see section 5.
16. Enterprise compatibility is a hard requirement (owner, 2026-11-02): see section 5. Verified on the versions where Enterprise source is available.
17. The Preview mode control is a toggle button in the top bar (systray), per the owner's request on 2026-11-02; top-right systray rather than top-left is the author's call (see section 3).
