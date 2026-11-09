# Manual QA, Task 6 open steps (Odoo 20.0), 2026-11-09

Setup: fresh DB `-i sale,stock,account,preview_mode --with-demo` on 20.0 (branch `origin/20.0` at a912eff), own server on port 8144, Chrome. All steps were done logged in as the demo user `demo` (id 5), an internal user with only Sales / User, Inventory / User and Accounting / Billing: no Settings, no Administrator group, no per-app setup for Preview Mode. Screenshots were kept by the tester (names below), not committed.

| Step | Result |
|---|---|
| 1b Toggle on Enterprise | NOT RUN |
| 4 Toggle off stops previews | PASS |
| 5 Print, smart button, wizard-opening button run without popup | PASS with one note (Print on a transfer) |
| 5b Preview on 3 apps as a plain user | PASS |

## 1b: NOT RUN
Needs Odoo Enterprise 20. No Enterprise 20 source exists on this machine (only 17, 18, 19), so nothing was faked.

## 4: toggle off stops previews: PASS
- Opened quotation S00003 (draft, Sales). Toggled Preview mode on (switch in the top bar, `aria-checked` true). Clicked Confirm: popup `Preview: Confirm` with the yellow banner, What/Where table, footer `Confirm | Go back | Copy`. Clicked Go back. DB: S00003 still `draft`, no transfer created. (screenshot `5b-sales-confirm-popup`)
- Clicked the switch again: `aria-checked` false, `res_users.preview_mode_enabled` false in the DB. Cleared the network log, clicked Confirm. No popup; requests were `call_button/sale.order/action_confirm`, `web_read`, `mail/store`. No `/preview_mode/run`. The order became Sales Order.

## 5: no popup for Print, smart button, wizard-opening buttons: PASS (note)
Toggle on for all of these.
- Smart button Delivery on S00003 (`action_view_delivery`): `/preview_mode/run` was called, no popup, the transfer list/form opened normally.
- Print as a report (record Actions menu > Print > Delivery Slip on WH/OUT/00018): no `/preview_mode/run`, no popup, report opened (HTML, because this machine has no wkhtmltopdf). (screenshot `5-report-print-no-popup`)
- Button Create Invoice on S00003 (opens a wizard): no popup, wizard opened. (screenshot `5-wizard-opens-no-popup`)
- Note, Print button on the transfer form (WH/OUT/00018): a popup `Preview: Print` appeared saying it will change 1 record, `Printed: True`. This is correct per the spec, because stock's `do_print_picking` really writes `printed = True`; Go back leaves it unchanged. It is not a bug, but it can surprise testers who expect "Print" to never show a popup. (screenshot `5-print-picking-popup`)
- Send on draft S00005 (`action_quotation_send`): no popup, but Odoo then showed `Invalid Operation: Unable to find the pdf engine` (no wkhtmltopdf here). Environment limit, the wizard was not reached, so Send is not counted as a wizard example. (screenshot `5-send-no-wkhtmltopdf`)

## 5b: any app, plain user: PASS
Same user `demo`, toggle on, nothing configured.
- Sales, Confirm on S00003: popup, see step 4. Summary: create 1 reference between stock documents, 1 stock move, 1 transfer, update 3 records.
- Inventory, Validate on WH/OUT/00018: popup `Preview: Validate`, 2 quants created, 7 records updated, rows `Changed` with struck-through old values, scrolling middle with pinned header and footer. Clicked the primary `Validate`: the transfer became Done. (screenshot `5b-inventory-validate-popup`)
- Accounting, Confirm (post) on a draft customer invoice (created by RPC as setup): popup `Preview: Confirm`, invoice becomes Posted with number INV/2026/00010 (the `(new)` placeholder logic did not consume the sequence), Where `Invoicing > Customers > Invoices`, journal entry section with Debit/Credit starts below the table. Go back: invoice still `draft` in the DB. (screenshot `5b-accounting-post-popup`)
- Bonus, failing click: Create Draft in the Create Invoice wizard on S00003 (nothing yet delivered) showed `Confirming will fail: ...` and Confirm stayed enabled, as designed. (screenshot `5-wizard-confirm-will-fail`)

## Observations (not fixed here, no change to code in this PR)
1. In the Sales Confirm popup, the sales order row has Where `Invoicing > Customers > Customers`, and the stock move and quant rows say `Inventory > Operations > Adjustments > Scrap`, which a user would not recognise as "where" a stock move lives. `locate()` picks the first visible menu with that model.
2. In the `Confirming will fail` popup the error text is shown twice (summary line and red banner).
3. The popup `Where` for the invoice's lines repeats `Invoicing > Customers > Invoices` for the move, line and a third row; the third (`Description: INV/...`) row is the payment-term line and has no distinct label.
4. After the real Validate the confirmation toast was not visible in a screenshot taken a moment later; not investigated, may have already closed.
5. The top-bar app name reads `Discuss` on the Sales and Inventory pages after loading a form by URL (stock Odoo behaviour on direct URL load, not Preview Mode).
