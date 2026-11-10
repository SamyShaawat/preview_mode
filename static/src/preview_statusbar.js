import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";

// A status bar click is not a button: it writes the stage when the form saves, so preview that write.
patch(StatusBarField.prototype, {
    setup() {
        super.setup(...arguments);
        this.previewMode = useService("preview_mode");
    },
    selectItem(item) {
        const { name, record } = this.props;
        return this.previewMode.previewWrite(record, { [name]: item.value }, item.label, () =>
            super.selectItem(item)
        );
    },
});
