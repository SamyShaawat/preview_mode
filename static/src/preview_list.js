/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";

// List-view mass actions (Archive, Unarchive, Delete) call the ORM directly, not a button, so they
// bypass the button wrapper in preview_service.js. Preview them on every selected record.
// PORT: on 16 these live in ListController (toggleArchiveState, deleteConfirmationDialogProps,
// getActionMenuItems); 20.0 patches DynamicList (_toggleArchive, _deleteRecords).
patch(ListController.prototype, "preview_mode.list", {
    async toggleArchiveState(archive) {
        // this._super only lives during the synchronous part of the call: bind it before any await.
        const _super = this._super.bind(this);
        const preview = this.env.services.preview_mode;
        const resIds = preview && preview.state.enabled ? await this.model.root.getResIds(true) : [];
        if (!resIds.length) {
            return _super(archive);
        }
        return preview.guard(
            {
                model: this.props.resModel,
                method: archive ? "action_archive" : "action_unarchive",
                ids: resIds,
                context: [this.model.root.context],
                label: archive ? _t("Archive") : _t("Unarchive"),
            },
            () => _super(archive)
        );
    },

    // With Preview on, the popup is the confirmation: skip Odoo's own "Are you sure?" for Archive.
    // Delete keeps Odoo's dialog (a delete cannot be undone), then the preview follows it.
    getActionMenuItems() {
        const menus = this._super(...arguments);
        const preview = this.env.services.preview_mode;
        const archive = menus.other.find((item) => item.key === "archive");
        if (archive && preview) {
            // Checked at click time: the menu is built before the switch may have been turned on.
            const original = archive.callback;
            archive.callback = () =>
                preview.state.enabled ? this.toggleArchiveState(true) : original();
        }
        return menus;
    },

    get deleteConfirmationDialogProps() {
        const props = this._super();
        const preview = this.env.services.preview_mode;
        if (!preview || !preview.state.enabled) {
            return props;
        }
        const confirm = props.confirm;
        props.confirm = async () => {
            const resIds = await this.model.root.getResIds(true);
            if (!resIds.length) {
                return confirm();
            }
            return preview.guard(
                {
                    model: this.props.resModel,
                    method: "unlink",
                    ids: resIds,
                    context: [this.model.root.context],
                    label: _t("Delete"),
                },
                () => confirm()
            );
        };
        return props;
    },
});
