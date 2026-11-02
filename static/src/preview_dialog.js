import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class PreviewDialog extends Component {
    static template = "preview_mode.Dialog";
    static components = { Dialog };
    // PORT: Odoo 20 validates props with useProps(t...); 16 to 19 use static props.
    static props = {
        close: Function,
        title: String,
        confirmLabel: String,
        summary: { type: String, optional: true },
        warnings: Array,
        changes: Array,
        emails: Array,
        journal: Array,
        incomplete: Boolean,
        onConfirm: Function,
    };

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
