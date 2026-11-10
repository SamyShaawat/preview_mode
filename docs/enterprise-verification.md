# Enterprise verification (`web_enterprise`)

Preview Mode depends only on `base` and `web`. This page records what was checked with Odoo Enterprise installed and what the owner still has to check.

## Results

| Version | Enterprise source locally | Result | Notes |
|---|---|---|---|
| 16.0 | No | NOT RUN | No 16.0 Enterprise source on this machine. |
| 17.0 | Yes (`odoo-17.0/enterprise`) | PASS | See the 17.0 table below. |
| 18.0 | Yes (`odoo-18.0/enterprise`) | NOT RUN | Same. |
| 19.0 | Yes (`odoo-19.0/enterprise`) | PASS after the fix below (observed on a clone of `pm19e`, 19.0 branch code unchanged) | See details. |
| 20.0 | No | NOT RUN | No 20.0 Enterprise source. Static review only, see risks. |

### 17.0 + `web_enterprise`, observed in Chrome (own port, clone with `web_enterprise`, sale, account, stock, crm installed)

| Check | Result |
|---|---|
| Toggle visible in the top bar next to the company name | PASS |
| Click turns it on (purple track), state kept after navigation and reload | PASS |
| Popup on Sales Confirm: title, yellow banner, table, footer `Confirm` / `Go back` / `Copy` | PASS |
| Popup fits the window, body scrolls (invoice Confirm with a journal table) | PASS |
| Go back changes nothing (order stayed draft) | PASS |
| Console errors after load and reload | PASS (none) |
| Dark colour scheme, Arabic/RTL, phone width | NOT RUN |

### 19.0 + `web_enterprise`, observed in Chrome (own port, clone of `pm19e`)

| Check | Result |
|---|---|
| Toggle visible in the top bar (systray) | PASS (dark and light colour scheme) |
| Click turns it on, `aria-checked` becomes `true` | PASS |
| Reload keeps the state (stored per user) | PASS |
| Popup opens on a data-changing button (Scheduled Action > Run Manually), title, warning banner, footer `Run Manually` / `Go back` | PASS |
| Popup not clipped (dialog height equals window height, body not cut) | PASS |
| Console errors after load | PASS (none; the console was only tracked after the page had loaded, so load-time errors were not captured) |
| Toggle OFF state on the white Enterprise top bar (light scheme) | FAIL before the fix: white knob on a white-ish track, only the eye was visible. |
| Same, with `currentColor` colours (this PR) | PASS: grey track and dark knob visible, checked by injecting the new CSS into the page. |

Cause: `web_enterprise` sets `$o-navbar-background: $o-white` in the light scheme, while the toggle used fixed white colours made for a dark bar. The same fixed colours were in the 20.0 file. The fix in `static/src/preview.scss` uses `currentColor`, which follows the top bar text colour. The ON state (purple track, white knob) is unchanged. The 19.0 branch was not touched; it has the same SCSS and needs the same fix when ports are ordered.

### Static review for 20.0 (no Enterprise source)

- Systray entry is a plain `registry.category("systray")` item with the `o_nav_entry` class, the same hook Enterprise 17 to 19 uses. Low risk.
- Dialog is the stock `Dialog` component; Enterprise does not restyle dialogs in 17 to 19 (`web_enterprise` has no dialog SCSS besides its own promote-studio dialog). Low risk.
- Risk: colours in the toggle (fixed in this PR). Risk: Enterprise 20 may change the top bar markup or class names (`o_nav_entry`); the toggle works without that class but loses hover styling.
- Risk: dark colour scheme (`navbar.dark.scss`) sets text colour to light; `currentColor` handles it.

## Checklist for the owner

Run on a DB with Enterprise installed and Preview Mode installed. Use `?debug=1` only to reach Scheduled Actions.

For 20.0 (needs 20.0 Enterprise source on the addons path) and for 16.0 (needs 16.0 Enterprise):

1. Log in as admin. In the top bar, find the eye with the small switch. Expected: visible in the top right, next to the user menu.
2. Settings > Users & Companies > Users > your user > Preferences: set Colour scheme to Light, reload. Expected: the OFF switch shows a grey track with a dark knob (not invisible).
3. Same with Colour scheme Dark. Expected: light knob visible.
4. Click the switch. Expected: purple track, white knob, tooltip stays. Reload the page. Expected: still on.
5. Settings > Technical > Scheduled Actions > open any action > Run Manually (button). Expected: popup `Preview: Run Manually`, yellow banner, buttons `Run Manually` and `Go back`, nothing clipped, long text wraps.
6. Resize the window to phone width. Expected: popup fits, footer buttons visible, body scrolls.
7. Open the browser console. Expected: no red errors while doing steps 1 to 6.
8. Switch the language to Arabic. Expected: the knob slides from the right side and the popup mirrors.
9. Click `Go back`. Expected: nothing changed. Turn the switch off again.
10. Write PASS/FAIL per step in the table above and commit it.
