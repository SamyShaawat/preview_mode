import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";

export class PreviewToggle extends Component {
    static template = "preview_mode.Toggle";

    setup() {
        this.preview = useService("preview_mode");
        // PORT: Owl 2 (Odoo 17 to 19) needs useState to re-render on a reactive; Owl 3 (Odoo 20) tracks reads itself.
        this.state = useState(this.preview.state);
    }
}

registry.category("systray").add("preview_mode.toggle", { Component: PreviewToggle, isDisplayed: () => Boolean(session.preview_mode_available) }, { sequence: 2 });
