import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

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
