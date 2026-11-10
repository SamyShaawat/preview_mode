# Looking for a second maintainer (ready to post)

Post this as a GitHub Discussion or issue on `SamyShaawat/preview_mode`, and/or on the Odoo forum and the OCA mailing list. Title suggestion: **Looking for a second maintainer for Preview Mode**.

---

Preview Mode is a free, open-source (LGPL-3) Odoo app that shows what a button click would create, change or delete, and where, before you commit to it. Turn the toggle on in the top bar, click Confirm, Validate or Post, and a popup lists the changes. Nothing is saved until you confirm. It works on every app and needs only `base` and `web`.

It runs on Odoo 17.0 to 20.0; the port to 16.0 is in progress. The goal is to submit it to the Odoo Community Association (OCA), which requires at least two maintainers. The repo already follows OCA conventions (pre-commit with isort, flake8 and pylint-odoo, DCO sign-off, LGPL-3).

**What a second maintainer does**
- Reviews and merges pull requests (every change goes through one, squash merge).
- Helps keep the version branches in step as ports land.
- Is named in `maintainers` in the manifest, and is on the module's OCA page once accepted.

**What you need**
- Comfortable with Odoo ORM and OWL, and with reviewing Python and JavaScript.
- A few hours a month.

Interested? Reply here, or open a pull request with a small fix to see how the workflow feels. See `CONTRIBUTING.md` first.
