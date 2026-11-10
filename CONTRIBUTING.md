# Contributing to preview_mode

Be kind: see the [Code of Conduct](CODE_OF_CONDUCT.md). Questions go to [Discussions](https://github.com/SamyShaawat/preview_mode/discussions), bugs to [Issues](https://github.com/SamyShaawat/preview_mode/issues/new/choose), security reports to [SECURITY.md](SECURITY.md).

One repo, one branch per Odoo version: `16.0`, `17.0`, `18.0`, `19.0`, `20.0`. Each version branch is protected, so nothing lands on it except through a pull request.

## The rule

Every task, however small, is one pull request.

1. Branch from the version branch you are changing: `git switch -c <type>/<series>-<topic> <series>`.
2. Name it `<type>/<series>-<topic>`. Types: `feat`, `fix`, `docs`, `port`, `chore`. Examples: `feat/20.0-recorder`, `port/19.0-recorder`, `docs/20.0-workflow`. Never start a name with the series and a slash (`19.0/...`): git cannot have both a branch `19.0` and a branch `19.0/x`.
3. Commit with a short imperative subject. No Claude co-author line.
4. Push the topic branch and open a PR with base set to the series branch: `gh pr create --base <series>`.
5. Title starts with the series in brackets, for example `[20.0] Add change recorder`.
6. Fill in the PR template. The first section names the base branch and says the topic branch is deleted after merge.

## Outside contributions: DCO sign-off

Pull requests from people outside the project are accepted only if every commit carries a Developer Certificate of Origin sign-off (https://developercertificate.org/). It says you wrote the change or have the right to submit it under the project's LGPL-3 license. Add it with `git commit -s`, which appends:

    Signed-off-by: Your Name <you@example.com>

Use your real name and the email on your commits. A PR with unsigned commits is not merged; fix it with `git rebase --signoff <series>` and a force push to your topic branch.

## Code style

The repo follows OCA conventions with a minimal rule set: `.pre-commit-config.yaml` (isort, flake8, pylint-odoo, whitespace checks) with `.flake8`, `.isort.cfg` and `.pylintrc`. Run `pre-commit run --all-files` before opening the PR.

## The `PORT:` convention

The Python core is identical on every version. A difference between Odoo versions lives in one small place marked with a `# PORT:` comment that says what differs (route type, ACL file name, `user_writeable`, `has_access`, mail connect method). Do not scatter version checks; add one marked spot. No walrus `:=` (Odoo 16 runs Python 3.7).

## Running the module on each version

Clone the repo into `addons/preview_mode` of an `odoo-<series>` checkout on the branch of the same series. Then, from that checkout:

    ./odoo-bin -c odoo.conf -d <db> -i preview_mode --http-port=8079

Use a port other than your own server's. Restart after code changes and press Update Apps List, because the manifest is cached.

## Translations

User-facing strings use `_()` in Python and `_t()` in JavaScript, and `string=` / text nodes in XML. To add a language, export the module's terms from Settings > Translations > Export Translation (or `odoo-bin --i18n-export=preview_mode/i18n/<lang>.po -l <lang> -d <db> --modules=preview_mode`) and put the `.po` file in `i18n/`. Translate in a PR like any other change.

## Porting to other versions

A change made on `20.0` (the reference and default branch) is ported with one PR per version, never one PR for several. Cherry-pick the merged commit onto `port/<series>-<topic>` cut from that version's branch, fix the version differences, and open the PR with base `<series>`. Link the original PR in the body.

## Merging

Squash merge only. GitHub deletes the topic branch automatically after merge. If it ever does not, delete it by hand: `git push origin --delete <topic-branch>`.

## Before opening the PR

- Python tests for the touched task pass: `./odoo-venv/bin/python odoo-bin -c odoo.conf -d <db> -u preview_mode --test-tags /preview_mode --stop-after-init` and expect `0 failed, 0 error(s)` (run from the matching `odoo-<series>` folder).
- Manual steps from the implementation plan for that task have been run, with the results written in the PR.
- Nothing is committed that the task did not touch.
