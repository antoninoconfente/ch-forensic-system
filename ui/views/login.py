"""Pantalla de acceso editorial — Supabase Auth."""

from nicegui import ui

from auth.supabase_auth import is_authenticated, sign_in_with_email, sign_up_with_email
from ui.theme import EDITORIAL_CSS, editorial_button


def build_login_page() -> None:
    ui.add_head_html(EDITORIAL_CSS)
    ui.page_title("Acceso — CH Curiosities Hunter")

    if is_authenticated():
        ui.navigate.to("/")
        return

    mode = {"value": "sign_in"}

    with ui.column().classes(
        "w-full min-h-screen items-center justify-center px-4 md:px-10 py-16 gap-0"
    ):
        with ui.column().classes(
            "w-full max-w-md gap-8 border border-[#B8B2A4] bg-[#F3EFE6] px-10 py-12"
        ):
            with ui.column().classes("w-full gap-2 items-center text-center"):
                ui.html(
                    "<span class='micro-coord'>PRIVATE ARCHIVE · ACCESO RESTRINGIDO</span>"
                )
                ui.html(
                    "<h1 class='masthead-title text-center m-0 text-3xl md:text-4xl leading-tight'>"
                    "CH CURIOSITIES HUNTER — PRIVATE ARCHIVE"
                    "</h1>"
                )
                ui.html(
                    "<p class='micro-coord mt-2 mb-0 text-[#625E57]'>"
                    "Identificación editorial para expedientes y galería"
                    "</p>"
                )

            with ui.row().classes("w-full justify-center gap-6 border-b border-[#141413] pb-3"):
                sign_in_tab = ui.element("button").classes("editorial-tab editorial-tab-active")
                with sign_in_tab:
                    ui.html("<span>ACCEDER</span>")
                sign_up_tab = ui.element("button").classes("editorial-tab")
                with sign_up_tab:
                    ui.html("<span>REGISTRAR NUEVO MIEMBRO</span>")

            email_in = ui.input(label="Email", placeholder="curator@ch.archive").classes(
                "w-full px-2 border border-[#141413]"
            )
            password_in = ui.input(
                label="Contraseña",
                placeholder="••••••••",
                password=True,
                password_toggle_button=True,
            ).classes("w-full px-2 border border-[#141413]")

            invite_box = ui.column().classes("w-full gap-2 hidden")
            with invite_box:
                invite_in = ui.input(
                    label="Código de invitación",
                    placeholder="CH-ARCHIVE-2026",
                ).classes("w-full px-2 border border-[#141413]")
                ui.html(
                    "<p class='micro-coord m-0 text-[#625E57]'>"
                    "Solo miembros invitados pueden crear una cuenta."
                    "</p>"
                )

            status = ui.label("").classes("micro-coord text-[#8c6d28] hidden")

            def submit():
                status.text = ""
                status.classes(add="hidden")
                try:
                    if mode["value"] == "sign_up":
                        result = sign_up_with_email(
                            email_in.value or "",
                            password_in.value or "",
                            invite_in.value or "",
                        )
                        if result.get("status") == "pending_confirmation":
                            ui.notify(
                                "Cuenta creada. Confirme el email si Supabase lo exige y acceda.",
                                type="positive",
                            )
                            set_mode_sign_in()
                            return
                        ui.notify("Registro completado. Bienvenido al archivo.", type="positive")
                    else:
                        sign_in_with_email(email_in.value or "", password_in.value or "")
                        ui.notify("Acceso concedido al archivo privado.", type="positive")
                    ui.navigate.to("/")
                except ValueError as exc:
                    ui.notify(str(exc), type="negative")
                    status.text = str(exc)
                    status.classes(remove="hidden")
                except Exception as exc:
                    ui.notify("No se pudo verificar el acceso.", type="negative")
                    status.text = str(exc)
                    status.classes(remove="hidden")

            email_in.on("keydown.enter", lambda: submit())
            password_in.on("keydown.enter", lambda: submit())

            action_row = ui.row().classes("w-full justify-end pt-2")
            action_buttons = {"sign_in": None, "sign_up": None}

            def render_action_buttons():
                action_row.clear()
                with action_row:
                    action_buttons["sign_in"] = editorial_button(
                        "ACCEDER AL ARCHIVO",
                        on_click=submit,
                    )
                    action_buttons["sign_up"] = editorial_button(
                        "CREAR CUENTA DE MIEMBRO",
                        on_click=submit,
                    )
                    if mode["value"] == "sign_up":
                        action_buttons["sign_in"].classes(add="hidden")
                    else:
                        action_buttons["sign_up"].classes(add="hidden")

            def set_mode_sign_in():
                mode["value"] = "sign_in"
                sign_in_tab.classes(replace="editorial-tab editorial-tab-active")
                sign_up_tab.classes(replace="editorial-tab")
                invite_box.classes(add="hidden")
                render_action_buttons()

            def set_mode_sign_up():
                mode["value"] = "sign_up"
                sign_up_tab.classes(replace="editorial-tab editorial-tab-active")
                sign_in_tab.classes(replace="editorial-tab")
                invite_box.classes(remove="hidden")
                render_action_buttons()

            sign_in_tab.on("click", lambda _: set_mode_sign_in())
            sign_up_tab.on("click", lambda _: set_mode_sign_up())
            render_action_buttons()