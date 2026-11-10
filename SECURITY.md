# Security policy

## Reporting a vulnerability

Report it privately: go to the repository's **Security** tab, then **Report a vulnerability** (GitHub private vulnerability reporting). Do not open a public issue or discussion. You get an answer through the same advisory thread; I aim to acknowledge within a week, and I will credit you in the advisory if you want.

## Supported versions

Security fixes are made on `20.0` first and ported to `19.0`, `18.0`, `17.0` and `16.0` as separate pull requests. See [SUPPORT.md](SUPPORT.md).

## In scope

The module promises that a preview changes nothing and exposes nothing. These count as vulnerabilities:

- A preview that saves, commits or sends something: a database write that survives the rollback, an email sent, an outgoing request made, a real sequence number consumed.
- A way around the rollback, for example code that commits through another connection.
- A user seeing data in the popup, the toast or `preview.mode.created` that their own rights and record rules do not allow.
- A user calling a private method, or a method on a model they cannot access, through `/preview_mode/run` or `/preview_mode/created`.
- Cross-user leaks of created-record ids, or a way to read another user's rows.
- Cross-site scripting through values shown in the popup.

## Out of scope

- A preview that differs from the real run (sequence numbers, time, random values, other users' changes). The popup says it is an estimate.
- Side effects the README lists as not covered, such as plain sockets or files written outside the database.
- The buttons excluded on purpose (module install and upgrade, Settings save, `ir.model`, `ir.model.fields`, `ir.ui.view`).
- Vulnerabilities in Odoo itself: report those to Odoo.
