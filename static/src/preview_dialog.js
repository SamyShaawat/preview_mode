import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class PreviewDialog extends Component {
    static template = "preview_mode.Dialog";
    static components = { Dialog };
    props = useProps({
        close: t.function(),
        title: t.string(),
        confirmLabel: t.string(),
        summary: t.string().optional(""),
        warnings: t.any(),
        changes: t.any(),
        emails: t.any(),
        journal: t.any(),
        incomplete: t.any(),
        onConfirm: t.function(),
    });

    setup() {
        this.notification = useService("notification");
    }

    // The popup as plain text, for a chat message, a ticket or an approval mail.
    get asText() {
        const p = this.props;
        const lines = [p.title, p.summary, ...p.warnings.map((w) => w.text)];
        for (const row of p.changes) {
            const kind = { new: _t("New"), changed: _t("Changed"), deleted: _t("Deleted") }[row.kind] || "";
            lines.push(`${["-", kind, row.what].filter(Boolean).join(" ")}${row.where ? ` (${row.where})` : ""}`);
            for (const f of row.fields) {
                lines.push(`    ${f.label}: ${f.old ? `${f.old} -> ` : ""}${f.new || _t("(empty)")}`);
            }
        }
        for (const move of p.journal) {
            lines.push(_t("Journal entry %s", move.move));
            for (const l of move.lines) {
                lines.push(`    ${l.account}  ${l.debit ? l.debit.toFixed(2) : ""}  ${l.credit ? l.credit.toFixed(2) : ""}`);
            }
        }
        for (const mail of p.emails) {
            lines.push(_t("Email (not sent): %(subject)s -> %(to)s", { subject: mail.subject, to: mail.to }));
        }
        if (p.incomplete) {
            lines.push(_t("Some effects could not be previewed and may still happen when you confirm."));
        }
        return lines.filter(Boolean).join("\n");
    }

    async copy() {
        try {
            await navigator.clipboard.writeText(this.asText);
            this.notification.add(_t("Preview copied."), { type: "success" });
        } catch {
            this.notification.add(_t("Could not copy the preview."), { type: "warning" });
        }
    }

    async confirm() {
        if (this.busy) {
            return;
        }
        this.busy = true;
        try {
            await this.props.onConfirm();
        } finally {
            this.props.close();
        }
    }

    back() {
        this.props.close();
    }
}
