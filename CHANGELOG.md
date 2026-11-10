# Changelog

All notable changes to this module are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This is the 19.0 branch, ported from 20.0.

## [Unreleased] - 19.0

### Added
- Switch in the top bar that turns previews on and off per user.
- Preview popup for any button that changes data, in any app: New, Changed and Deleted rows with old and new values, and a Where column with the menu path.
- Debit/Credit table when the click creates a journal entry.
- Primary button with the clicked button's label, Go back, and Copy (plain text).
- Notification with links to the records created by a real run.
- Previews for list view Archive, Unarchive and Delete, and for status bar stage clicks.
- Queued emails are listed as not sent; amounts, numbers and dates are shown as the form shows them.
- "Preview unavailable" dialog with Run without preview, and an estimate note in the popup.
- Extension point `preview.mode.section` for third-party tables in the popup.
- System parameters `preview_mode.enabled`, `preview_mode.timeout` and `preview_mode.max_records`.
- One running preview per user at a time.
- Store page with screenshots, CI workflow, browser tour tests, OCA-style lint configuration, DCO section.

### Changed
- The preview summary uses real singular and plural wording.
- Relicensed from OPL-1 to LGPL-3.
- The toggle is visible on the white Enterprise top bar; the Where column keeps whole words on narrow screens.
- Queued email addresses are shown only when the user may read them.

### Safety
- Buttons that change the registry or configuration (module install and upgrade, Settings, models, fields, views) are never previewed.
- Raw SQL writes are detected and the preview is marked incomplete.
- Outgoing calls through `urllib` and `http.client` are blocked as well as `requests`.
- The preview request carries the user context; delayed writes (recomputed fields) are recorded.
- Unknown and abstract models are refused with one uniform error; the preview timeout is clamped to 1 to 120 seconds.
