/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";

export class PreviewToggle extends Component {
    static template = "preview_mode.Toggle";

    setup() {
        this.preview = useService("preview_mode");
        this.state = useState(this.preview.state);  // PORT: Owl 2 needs useState; 20.0 tracks the proxy itself
    }

    get available() {
        // PORT: Odoo 16's systray registry has no isDisplayed; the template hides the switch instead.
        return Boolean(session.preview_mode_available);
    }

    toggle() {
        return this.preview.toggle();
    }
}

registry.category("systray").add("preview_mode.toggle", { Component: PreviewToggle, isDisplayed: () => Boolean(session.preview_mode_available) }, { sequence: 2 });
