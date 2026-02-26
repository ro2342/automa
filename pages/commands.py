"""
pages/commands.py - CRUD para custom_commands. Todas as strings via i18n._().
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager
from icon_loader import make_icon
import i18n


class CommandRow(Adw.ActionRow):
    def __init__(self, cmd_data, on_edit, on_delete):
        super().__init__()
        self.cmd_data = cmd_data
        self._refresh()
        _ = i18n._
        edit_btn = Gtk.Button()
        edit_btn.set_child(make_icon("document-edit-symbolic"))
        edit_btn.set_valign(Gtk.Align.CENTER)
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", lambda _: on_edit(self))
        self.add_suffix(edit_btn)
        del_btn = Gtk.Button()
        del_btn.set_child(make_icon("user-trash-symbolic"))
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.add_css_class("destructive-action")
        del_btn.connect("clicked", lambda _: on_delete(self))
        self.add_suffix(del_btn)

    def _refresh(self):
        self.set_title(self.cmd_data.get("name", "(unnamed)"))
        cmd = self.cmd_data.get("command", "")
        self.set_subtitle(cmd[:80] + ("…" if len(cmd) > 80 else ""))


class CommandEditDialog(Adw.Dialog):
    def __init__(self, parent, cmd_data, on_save):
        super().__init__()
        _ = i18n._
        self.set_title(_("Edit Command") if cmd_data else _("Add Command"))
        self.set_content_width(480)
        self.on_save  = on_save
        self._data    = dict(cmd_data) if cmd_data else {"name": "", "command": ""}
        self._build_ui()

    def _build_ui(self):
        _ = i18n._
        tv = Adw.ToolbarView()
        self.set_child(tv)
        hb = Adw.HeaderBar()
        hb.set_show_start_title_buttons(False)
        hb.set_show_end_title_buttons(False)
        tv.add_top_bar(hb)

        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda _: self.close())
        hb.pack_start(cancel)

        save = Gtk.Button(label=_("Save"))
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        hb.pack_end(save)

        clamp = Adw.Clamp(maximum_size=480)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        tv.set_content(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(box)

        name_group = Adw.PreferencesGroup(
            title=_("Command Name"),
            description=_("Used as the MQTT topic slug. Use lowercase letters, numbers, and underscores only."),
        )
        box.append(name_group)
        self.name_entry = Adw.EntryRow(title=_("Name"))
        self.name_entry.set_text(self._data.get("name", ""))
        name_group.add(self.name_entry)

        cmd_group = Adw.PreferencesGroup(
            title=_("Bash Command"),
            description=_("The shell command executed when Home Assistant triggers this action."),
        )
        box.append(cmd_group)

        frame = Gtk.Frame()
        frame.add_css_class("card")
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(120)
        scroll.set_max_content_height(280)
        self.cmd_view = Gtk.TextView()
        self.cmd_view.set_monospace(True)
        self.cmd_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.cmd_view.set_margin_start(8)
        self.cmd_view.set_margin_end(8)
        self.cmd_view.set_margin_top(8)
        self.cmd_view.set_margin_bottom(8)
        self.cmd_view.get_buffer().set_text(self._data.get("command", ""))
        scroll.set_child(self.cmd_view)
        frame.set_child(scroll)
        cmd_group.add(frame)

    def _on_save(self, _):
        _ = i18n._
        name = self.name_entry.get_text().strip()
        if not name:
            self.name_entry.add_css_class("error")
            return
        buf = self.cmd_view.get_buffer()
        self._data["name"]    = name
        self._data["command"] = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        self.on_save(dict(self._data))
        self.close()


class CommandsPage(Gtk.Box):
    def __init__(self, config_manager: ConfigManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager = config_manager
        self._commands: list[dict] = []
        self._build_ui()
        self.connect("realize", lambda _: self._load())

    def _build_ui(self):
        _ = i18n._
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
            title=_("Commands are exposed to Home Assistant via MQTT and can be triggered as scripts or automations."),
            revealed=True,
        )
        outer.append(banner)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.set_margin_bottom(4)
        lbl = Gtk.Label(label=_("Custom Commands"))
        lbl.add_css_class("title-4")
        lbl.set_hexpand(True)
        lbl.set_halign(Gtk.Align.START)
        hdr.append(lbl)
        add_btn = Gtk.Button()
        _add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        _add_box.append(make_icon("list-add-symbolic"))
        _add_box.append(Gtk.Label(label=_("Add Command")))
        add_btn.set_child(_add_box)
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add)
        hdr.append(add_btn)
        outer.append(hdr)

        self.cmd_group = Adw.PreferencesGroup()
        outer.append(self.cmd_group)

        self.empty_label = Gtk.Label(
            label=_('No custom commands yet.\nClick "Add Command" to create one.')
        )
        self.empty_label.set_justify(Gtk.Justification.CENTER)
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_margin_top(32)
        outer.append(self.empty_label)

    def _load(self):
        self._commands = list(self.config_manager.get_custom_commands())
        self._refresh_list()

    def _refresh_list(self):
        rows = []
        child = self.cmd_group.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            if isinstance(child, Adw.ActionRow):
                rows.append(child)
            child = nxt
        for r in rows:
            self.cmd_group.remove(r)
        for cmd in self._commands:
            self.cmd_group.add(CommandRow(cmd, self._on_edit, self._on_delete))
        self.empty_label.set_visible(len(self._commands) == 0)

    def _on_add(self, _):
        CommandEditDialog(self, None, self._save_new).present(self)

    def _save_new(self, data):
        self._commands.append(data)
        self._refresh_list()

    def _on_edit(self, row):
        idx = self._commands.index(row.cmd_data)
        def _save(new):
            self._commands[idx] = new
            row.cmd_data = new
            row._refresh()
        CommandEditDialog(self, dict(row.cmd_data), _save).present(self)

    def _on_delete(self, row):
        _ = i18n._
        dlg = Adw.AlertDialog(
            heading=_("Delete Command?"),
            body=_('Delete "{name}"? This cannot be undone.').format(
                name=row.cmd_data.get("name", "")),
        )
        dlg.add_response("cancel", _("Cancel"))
        dlg.add_response("delete", _("Delete"))
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        def _resp(d, r):
            if r == "delete":
                self._commands = [c for c in self._commands if c is not row.cmd_data]
                self._refresh_list()
        dlg.connect("response", _resp)
        dlg.present(self)

    def apply_to_config(self):
        self.config_manager.set_custom_commands(list(self._commands))
