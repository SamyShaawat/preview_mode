import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PreviewToggle extends Component {
    static template = "preview_mode.Toggle";
    static props = {};

    setup() {
        this.preview = useService("preview_mode");
    }
}

registry.category("systray").add("preview_mode.toggle", { Component: PreviewToggle }, { sequence: 2 });
