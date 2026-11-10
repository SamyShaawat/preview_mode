/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";

// A status bar click is not a button: it writes the stage when the form saves, so preview that write.
// PORT: 16 passes items as {id, name}; 20.0 as {value, label}. 16 patches take a name and use this._super.
patch(StatusBarField.prototype, "preview_mode.statusbar", {
    setup() {
        this._super(...arguments);
        this.previewMode = useService("preview_mode");
    },
    selectItem(item) {
        const { name, record } = this.props;
        const _super = this._super.bind(this);  // only valid during the synchronous call
        return this.previewMode.previewWrite(record, { [name]: item.id }, item.name, () =>
            _super(item)
        );
    },
});
