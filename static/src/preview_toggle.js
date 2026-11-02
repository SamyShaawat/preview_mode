/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PreviewToggle extends Component {
    static template = "preview_mode.Toggle";
    static props = {};

    setup() {
        this.preview = useService("preview_mode");
        // PORT: Owl 2 (16 to 19) must subscribe to the shared state; Owl 3 (20) tracks it on its own.
        this.state = useState(this.preview.state);
    }
}

registry.category("systray").add("preview_mode.toggle", { Component: PreviewToggle }, { sequence: 2 });
