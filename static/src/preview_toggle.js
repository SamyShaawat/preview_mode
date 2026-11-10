import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";

export class PreviewToggle extends Component {
    static template = "preview_mode.Toggle";

    setup() {
        this.preview = useService("preview_mode");
    }
}

registry.category("systray").add("preview_mode.toggle", { Component: PreviewToggle, isDisplayed: () => Boolean(session.preview_mode_available) }, { sequence: 2 });
