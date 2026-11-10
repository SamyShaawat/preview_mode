/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DynamicList } from "@web/model/relational_model/dynamic_list";
import { ListController } from "@web/views/list/list_controller";

// List-view mass actions (Archive, Unarchive, Delete) call the ORM directly, not a button, so they
// bypass the button wrapper in preview_service.js. Preview them on every selected record.
// PORT: _toggleArchive / _deleteRecords exist on Odoo 17 to 20 (16 has a different list model).
patch(DynamicList.prototype, {
    async _toggleArchive(isSelected, archive) {
        const preview = this.model.env.services.preview_mode;
        const resIds = preview?.state.enabled ? await this.getResIds(isSelected) : [];
        if (!resIds.length) {
            return super._toggleArchive(isSelected, archive);
        }
        return preview.guard(
            {
                model: this.resModel,
                method: archive ? "action_archive" : "action_unarchive",
                ids: resIds,
                context: [this.context],
                label: archive ? _t("Archive") : _t("Unarchive"),
            },
            () => super._toggleArchive(isSelected, archive)
        );
    },

    async _deleteRecords(records) {
        const preview = this.model.env.services.preview_mode;
        const resIds = preview?.state.enabled
            ? records.length
                ? records.map((r) => r.resId).filter(Boolean)
                : await this.getResIds(true)
            : [];
        if (!resIds.length) {
            return super._deleteRecords(records);
        }
        return preview.guard(
            { model: this.resModel, method: "unlink", ids: resIds, context: [this.context], label: _t("Delete") },
            () => super._deleteRecords(records)
        );
    },
});

// With Preview on, the popup is the confirmation: skip Odoo's own "Are you sure?" for Archive.
// Delete keeps Odoo's dialog (it is asked in a view hook, and a delete cannot be undone).
// PORT: Odoo 17 builds the sidebar items in the controller; Odoo 20 has toggleArchiveWithConfirmation on the list.
patch(ListController.prototype, {
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems(...arguments);
        if (items.archive) {
            const callback = items.archive.callback;
            items.archive.callback = () =>
                this.env.services.preview_mode?.state.enabled ? this.toggleArchiveState(true) : callback();
        }
        return items;
    },
});
