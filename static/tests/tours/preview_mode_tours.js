import { registry } from "@web/core/registry";

const toggleOn = [
    { trigger: ".o_preview_toggle:not(.o_preview_on)", run: "click" },
    { trigger: ".o_preview_toggle.o_preview_on[aria-checked=true]" },
];

registry.category("web_tour.tours").add("preview_mode_toggle", {
    steps: () => [
        ...toggleOn,
        { trigger: ".o_preview_toggle.o_preview_on", run: "click" },
        { trigger: ".o_preview_toggle:not(.o_preview_on)[aria-checked=false]" },
    ],
});

registry.category("web_tour.tours").add("preview_mode_confirm", {
    steps: () => [
        ...toggleOn,
        { trigger: "button[name=copy]", run: "click" },
        { trigger: ".o_preview_mode_dialog .o_preview_table" },
        { trigger: ".o_preview_mode_dialog .btn-primary:contains(Duplicate Contact)", run: "click" },
        { trigger: ".o_notification:contains(Created) .o_notification_buttons button", run: "click" },
        { trigger: '.o_form_view:contains("Tour Partner (copy)")' },
    ],
});

registry.category("web_tour.tours").add("preview_mode_no_popup", {
    steps: () => [
        ...toggleOn,
        { trigger: "button[name=open_commercial_entity]", run: "click" },
        // The click ran normally: no preview dialog, the form is still shown.
        { trigger: ".o_form_view", run: () => {
            if (document.querySelector(".o_preview_mode_dialog")) {
                throw new Error("Preview popup must not open for a click that changes nothing");
            }
        } },
    ],
});

registry.category("web_tour.tours").add("preview_mode_switched_off", {
    steps: () => [
        // The form is loaded, the toggle is not in the top bar, and the button runs as in stock Odoo.
        { trigger: "button[name=copy]", run: () => {
            if (document.querySelector(".o_preview_toggle")) {
                throw new Error("The toggle must be hidden when preview_mode.enabled is False");
            }
        } },
        { trigger: "button[name=copy]", run: "click" },
        // No popup; the click ran for real (the test checks the copy exists).
        { trigger: ".o_form_view:not(.o_loading)", run: () => {
            if (document.querySelector(".o_preview_mode_dialog")) {
                throw new Error("No preview popup when preview_mode.enabled is False");
            }
        } },
    ],
});
