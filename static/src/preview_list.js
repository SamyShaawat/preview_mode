import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DynamicList } from "@web/model/relational_model/dynamic_list";

// List-view mass actions (Archive, Unarchive, Delete) call the ORM directly, not a button, so they
// bypass the button wrapper in preview_service.js. Preview them on every selected record.
// PORT: _toggleArchive / _deleteRecords are the Odoo 20 names; check them on 16 to 19.
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
