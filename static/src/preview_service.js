/** @odoo-module **/
import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { makeContext } from "@web/core/context";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PreviewDialog } from "./preview_dialog";

// PORT: the button click is `action.doActionButton` (action_service.js on 16 to 19, action_plugin.js on 20).

// Unpredictable token, or null when no secure random source exists (never a guessable one).
function newToken() {
    const c = globalThis.crypto;
    if (c?.randomUUID) {
        return c.randomUUID();
    }
    if (c?.getRandomValues) {
        return Array.from(c.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
    }
    return null;
}

// The button's text without Odoo's keyboard-hint overlay (shown while Alt is held).
function buttonText(button) {
    const clone = button.cloneNode(true);
    clone.querySelectorAll(".o_web_hotkey_overlay").forEach((el) => el.remove());
    return clone.textContent.trim();
}

export const previewService = {
    // PORT: Odoo 17 has `rpc` and `user` services; 18 and later export an `rpc` function and a `user` object.
    dependencies: ["action", "dialog", "notification", "orm", "rpc", "user"],
    start(env, { action, dialog, notification, orm, rpc, user }) {
        // PORT: `reactive` (Owl 2, Odoo 16 to 19); Odoo 20 uses `proxy` (Owl 3).
        const state = reactive({ enabled: Boolean(session.preview_mode_enabled) });
        const original = action.doActionButton.bind(action);
        // Button params carry no visible text, so remember the last clicked button for the label.
        let lastButton = null;
        document.addEventListener("click", (ev) => (lastButton = ev.target.closest?.("button")), true);

        async function showCreated(token) {
            const created = await rpc("/preview_mode/created", { token });
            if (!created.length) {
                return;
            }
            notification.add(_t("Created:"), {
                type: "success",
                sticky: true,
                buttons: created.map((rec) => ({
                    name: rec.name,
                    onClick: () => action.doAction({
                        type: "ir.actions.act_window",
                        res_model: rec.model,
                        res_id: rec.res_id,
                        views: [[false, "form"]],
                    }),
                })),
            });
        }

        // Preview one click: `req` = {model, method, ids, args, context, label}; `run(token)` is the real run.
        // Resolves after the user confirms (and run finished) or goes back.
        async function guard(req, run) {
            const { label } = req;
            let result;
            try {
                result = await rpc("/preview_mode/run", {
                    model: req.model,
                    method: req.method,
                    res_ids: req.ids,
                    args: req.args || [],
                    kwargs: { context: makeContext([user.context, ...req.context]) },
                    label,
                });
            } catch {
                // The preview itself failed: say so and let the user decide; the real run is never silent.
                return new Promise((resolve) => {
                    dialog.add(ConfirmationDialog, {
                        title: _t("Preview unavailable"),
                        body: _t("The preview could not be built, so nothing is known about what %s will do.", label),
                        confirmLabel: _t("Run without preview"),
                        confirm: () => resolve(run()),
                        cancelLabel: _t("Go back"),
                        cancel: () => resolve(),
                    });
                });
            }
            if (!result.show) {
                if (result.notice) {
                    notification.add(result.notice, { type: "info" });
                }
                return run();
            }
            await new Promise((resolve) => {
                let settled = false;
                const done = () => {
                    settled = true;
                    resolve();
                };
                dialog.add(
                    PreviewDialog,
                    {
                        title: _t("Preview: %s", label),
                        confirmLabel: label,
                        summary: result.summary,
                        warnings: result.warnings,
                        changes: result.changes,
                        emails: result.emails,
                        journal: result.journal,
                        sections: result.sections || [],
                        incomplete: result.incomplete,
                        onConfirm: async () => {
                            try {
                                await run(newToken());
                            } finally {
                                done();
                            }
                        },
                    },
                    { onClose: () => !settled && done() }
                );
            });
        }

        action.doActionButton = async function (params, options) {
            if (!state.enabled || params.type !== "object" || params.special || !params.name) {
                return original(params, options);
            }
            let extra = [];
            if (params.args) {
                try {
                    extra = JSON.parse(params.args.replace(/'/g, '"'));
                } catch {
                    extra = [];
                }
            }
            // The clicked button's own text; falls back to the method name.
            const label =
                params.string ||
                (lastButton?.name === params.name && buttonText(lastButton)) ||
                params.name;
            return guard(
                {
                    model: params.resModel,
                    method: params.name,
                    ids: params.resId ? [params.resId] : params.resIds || [],
                    args: extra,
                    context: [params.context, params.buttonContext],
                    label,
                },
                async (token) => {
                    await original(
                        token ? { ...params, context: { ...(params.context || {}), preview_mode_token: token } } : params,
                        options
                    );
                    if (token) {
                        await showCreated(token);
                    }
                }
            );
        };

        return {
            state,
            guard,
            // A status bar click saves the record with the new stage: preview that write, then run `run`.
            previewWrite(record, values, label, run) {
                if (!state.enabled || !record.resId) {
                    return run();
                }
                return guard(
                    { model: record.resModel, method: "write", ids: [record.resId], args: [values], context: [], label },
                    () => run()
                );
            },
            async toggle() {
                const enabled = !state.enabled;
                await orm.write("res.users", [user.userId], { preview_mode_enabled: enabled });
                state.enabled = enabled;
            },
        };
    },
};

registry.category("services").add("preview_mode", previewService);
