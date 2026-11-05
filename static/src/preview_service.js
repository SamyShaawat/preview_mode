import { proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { makeContext } from "@web/core/context";
import { _t } from "@web/core/l10n/translation";
import { PreviewDialog } from "./preview_dialog";

// PORT: on Odoo 16 to 19 the button click is `action.doActionButton` in action_service.js;
// on 20.0 it lives in webclient/actions/action_plugin.js and is still reached as `action.doActionButton`.

function newToken() {
    return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// The button's text without Odoo's keyboard-hint overlay (shown while Alt is held).
function buttonText(button) {
    const clone = button.cloneNode(true);
    clone.querySelectorAll(".o_web_hotkey_overlay").forEach((el) => el.remove());
    return clone.textContent.trim();
}

export const previewService = {
    dependencies: ["action", "dialog", "notification", "orm"],
    start(env, { action, dialog, notification, orm }) {
        const state = proxy({ enabled: Boolean(session.preview_mode_enabled) });
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

        action.doActionButton = async function (params, options) {
            if (!state.enabled || params.type !== "object" || params.special || !params.name) {
                return original(params, options);
            }
            const ids = params.resId ? [params.resId] : params.resIds || [];
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
            let result;
            try {
                result = await rpc("/preview_mode/run", {
                    model: params.resModel,
                    method: params.name,
                    res_ids: ids,
                    args: extra,
                    kwargs: { context: makeContext([user.context, params.context, params.buttonContext]) },
                    label,
                });
            } catch {
                // The preview itself failed: behave like stock Odoo, the real run decides.
                return original(params, options);
            }
            if (!result.show) {
                return original(params, options);
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
                        incomplete: result.incomplete,
                        onConfirm: async () => {
                            const token = newToken();
                            try {
                                await original(
                                    { ...params, context: { ...(params.context || {}), preview_mode_token: token } },
                                    options
                                );
                                await showCreated(token);
                            } finally {
                                done();
                            }
                        },
                    },
                    { onClose: () => !settled && done() }
                );
            });
        };

        return {
            state,
            async toggle() {
                const enabled = !state.enabled;
                await orm.write("res.users", [user.userId], { preview_mode_enabled: enabled });
                state.enabled = enabled;
            },
        };
    },
};

registry.category("services").add("preview_mode", previewService);
