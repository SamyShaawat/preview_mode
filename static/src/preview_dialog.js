import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class PreviewDialog extends Component {
    static template = "preview_mode.Dialog";
    static components = { Dialog };
    // PORT: Owl 2 (Odoo 16 to 19) declares props with `static props`; Odoo 20 (Owl 3) uses useProps.
    static props = {
        close: Function,
        title: String,
        confirmLabel: String,
        summary: { type: String, optional: true },
        warnings: Array,
        changes: Array,
        emails: Array,
        journal: Array,
        sections: Array,
        incomplete: { type: Boolean, optional: true },
        onConfirm: Function,
    };

    setup() {
        this.notification = useService("notification");
    }

    // A failing click puts the same message in the summary and in a blocking warning: show it once.
    get showSummary() {
        const { summary, warnings } = this.props;
        return summary && !warnings.some((w) => w.blocking && summary.includes(w.text));
    }

    // The popup as plain text, for a chat message, a ticket or an approval mail.
    get asText() {
        const p = this.props;
        const lines = [p.title, this.showSummary && p.summary, ...p.warnings.map((w) => w.text)];
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
        for (const section of p.sections) {
            lines.push(section.title);
            lines.push(...section.rows.map((row) => `    ${row.join("  ")}`));
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
