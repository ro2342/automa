"""
pages/commands.py - CRUD interface for custom_commands in config.yaml.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager


class CommandRow(Adw.ActionRow):

    def __init__(self, cmd_data: dict, on_edit, on_delete):
        super().__init__()
        self.cmd_data = cmd_data
        self._refresh_display()

        edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
        edit_btn.set_valign(Gtk.Align.CENTER)
        edit_btn.add_css_class("flat")
        edit_btn.set_tooltip_text("Edit command")
        edit_btn.connect("clicked", lambda _: on_edit(self))
        self.add_suffix(edit_btn)

        del_btn = Gtk.Button(icon_name="user-trash-symbolic")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.set_tooltip_text("Delete command")
        del_btn.connect("clicked", lambda _: on_delete(self))
        self.add_suffix(del_btn)

    def _refresh_display(self):
        self.set_title(self.cmd_data.get("name", "(unnamed)"))
        cmd = self.cmd_data.get("command", "")
        self.set_subtitle(cmd[:80] + ("…" if len(cmd) > 80 else ""))


class CommandEditDialog(Adw.Dialog):

    def __init__(self, parent, cmd_data: dict | None, on_save):
        super().__init__()
        self.set_title("Edit Command" if cmd_data else "Add Command")
        self.set_content_width(480)
        self.on_save = on_save
        self._cmd_data = dict(cmd_data) if cmd_data else {"name": "", "command": ""}
        self._build_ui()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_start_title_buttons(False)
        header.set_show_end_title_buttons(False)
        toolbar_view.add_top_bar(header)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        clamp = Adw.Clamp(maximum_size=480)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        toolbar_view.set_content(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(box)

        name_group = Adw.PreferencesGroup(
            title="Command Name",
            description="Used as the MQTT topic slug. Use lowercase letters, numbers, and underscores only.",
        )
        box.append(name_group)

        self.name_entry = Adw.EntryRow(title="Name")
        self.name_entry.set_text(self._cmd_data.get("name", ""))
        name_group.add(self.name_entry)

        cmd_group = Adw.PreferencesGroup(
            title="Bash Command",
            description="The shell command executed when Home Assistant triggers this action.",
        )
        box.append(cmd_group)

        frame = Gtk.Frame()
        frame.add_css_class("card")
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(120)
        scroll.set_max_content_height(280)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.cmd_view = Gtk.TextView()
        self.cmd_view.set_monospace(True)
        self.cmd_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.cmd_view.set_margin_start(8)
        self.cmd_view.set_margin_end(8)
        self.cmd_view.set_margin_top(8)
        self.cmd_view.set_margin_bottom(8)
        self.cmd_view.get_buffer().set_text(self._cmd_data.get("command", ""))
        scroll.set_child(self.cmd_view)
        frame.set_child(scroll)
        cmd_group.add(frame)

    def _on_save(self, _btn):
        name = self.name_entry.get_text().strip()
        buf = self.cmd_view.get_buffer()
        command = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        if not name:
            self.name_entry.add_css_class("error")
            return
        self._cmd_data["name"] = name
        self._cmd_data["command"] = command
        self.on_save(dict(self._cmd_data))
        self.close()


class CommandsPage(Gtk.Box):

    def __init__(self, config_manager: ConfigManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager = config_manager
        self._commands: list[dict] = []
        self._build_ui()
        self.connect("realize", lambda _: self._load_commands())

    def _build_ui(self):
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        clamp = Adw.Clamp(maximum_size=700, tightening_threshold=500)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scroll.set_child(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(outer)

        banner = Adw.Banner(
            title="Commands are exposed to Home Assistant via MQTT and can be triggered as scripts or automations.",
            revealed=True,
        )
        outer.append(banner)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.set_margin_bottom(4)
        title_label = Gtk.Label(label="Custom Commands")
        title_label.add_css_class("title-4")
        title_label.set_hexpand(True)
        title_label.set_halign(Gtk.Align.START)
        hdr.append(title_label)

        add_btn = Gtk.Button(label="Add Command", icon_name="list-add-symbolic")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add)
        hdr.append(add_btn)
        outer.append(hdr)

        self.cmd_group = Adw.PreferencesGroup()
        outer.append(self.cmd_group)

        self.empty_label = Gtk.Label(
            label='No custom commands yet.\nClick "Add Command" to create one.'
        )
        self.empty_label.set_justify(Gtk.Justification.CENTER)
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_margin_top(32)
        outer.append(self.empty_label)

    def _load_commands(self):
        self._commands = list(self.config_manager.get_custom_commands())
        self._refresh_list()

    def _refresh_list(self):
        # Remove apenas AdwActionRow — não tenta remover elementos internos do grupo
        rows_to_remove = []
        child = self.cmd_group.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            if isinstance(child, Adw.ActionRow):
                rows_to_remove.append(child)
            child = next_child

        for row in rows_to_remove:
            self.cmd_group.remove(row)

        for cmd in self._commands:
            row = CommandRow(cmd, on_edit=self._on_edit_row, on_delete=self._on_delete_row)
            self.cmd_group.add(row)

        self.empty_label.set_visible(len(self._commands) == 0)

    def _on_add(self, _btn):
        dialog = CommandEditDialog(parent=self, cmd_data=None, on_save=self._save_new_command)
        dialog.present(self)

    def _save_new_command(self, cmd_data: dict):
        self._commands.append(cmd_data)
        self._refresh_list()

    def _on_edit_row(self, row: CommandRow):
        idx = self._commands.index(row.cmd_data)

        def _save_edit(new_data):
            self._commands[idx] = new_data
            row.cmd_data = new_data
            row._refresh_display()

        dialog = CommandEditDialog(parent=self, cmd_data=dict(row.cmd_data), on_save=_save_edit)
        dialog.present(self)

    def _on_delete_row(self, row: CommandRow):
        confirm = Adw.AlertDialog(
            heading="Delete Command?",
            body=f'Delete "{row.cmd_data.get("name", "")}"? This cannot be undone.',
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("delete", "Delete")
        confirm.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.set_default_response("cancel")

        def _on_response(dlg, response):
            if response == "delete":
                self._commands = [c for c in self._commands if c is not row.cmd_data]
                self._refresh_list()

        confirm.connect("response", _on_response)
        confirm.present(self)

    def apply_to_config(self):
        self.config_manager.set_custom_commands(list(self._commands))
