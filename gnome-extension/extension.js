/**
 * Automa GNOME Shell Extension
 * Ícone simbólico — dark/light automático via currentColor.
 * Compatível com GNOME Shell 45+
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const POLL_INTERVAL_MS = 10_000;

const AutomaIndicator = GObject.registerClass(
class AutomaIndicator extends PanelMenu.Button {

    _init(extensionPath) {
        super._init(0.0, 'Automa');
        this._extensionPath = extensionPath;

        // Ícone simbólico — GNOME recolore automaticamente dark/light
        const iconFile = Gio.File.new_for_path(`${extensionPath}/automa-icon-symbolic.svg`);
        const gicon    = new Gio.FileIcon({ file: iconFile });

        this._icon = new St.Icon({
            gicon,
            icon_size: 16,
            style_class: 'system-status-icon automa-icon automa-unknown',
        });

        this.add_child(this._icon);
        this._buildMenu();
        this._pollTimer = null;
        this._updateStatus();
        this._startPolling();
    }

    _buildMenu() {
        const title = new PopupMenu.PopupMenuItem('Automa', { reactive: false });
        title.label.style_class = 'automa-menu-title';
        this.menu.addMenuItem(title);

        this._statusItem = new PopupMenu.PopupMenuItem('Service: checking…', { reactive: false });
        this.menu.addMenuItem(this._statusItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._addAction('Open Automa', 'application-x-executable-symbolic', () => this._openApp());
        this._addAction('Start',       'media-playback-start-symbolic',      () => this._ctl('start'));
        this._addAction('Stop',        'media-playback-stop-symbolic',       () => this._ctl('stop'));
        this._addAction('Restart',     'view-refresh-symbolic',              () => this._ctl('restart'));

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addAction('Refresh',     'view-refresh-symbolic',              () => this._updateStatus());
    }

    _addAction(label, iconName, callback) {
        const item = new PopupMenu.PopupImageMenuItem(label, iconName);
        item.connect('activate', callback);
        this.menu.addMenuItem(item);
        return item;
    }

    _updateStatus() {
        this._runCmd(['systemctl', '--user', 'is-active', 'lnxlink.service'],
            (_ok, stdout) => this._applyState(stdout.trim()));
    }

    _applyState(state) {
        for (const cls of ['automa-running', 'automa-stopped', 'automa-failed', 'automa-unknown'])
            this._icon.remove_style_class_name(cls);

        const map = {
            active:   ['automa-running', 'Service: Running'],
            inactive: ['automa-stopped', 'Service: Stopped'],
            failed:   ['automa-failed',  'Service: Failed'],
        };
        const [cls, label] = map[state] ?? ['automa-unknown', 'Service: Unknown'];
        this._icon.add_style_class_name(cls);
        this._statusItem.label.set_text(label);
    }

    _ctl(action) {
        this._runCmd(['systemctl', '--user', action, 'lnxlink.service'], () =>
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1500, () => {
                this._updateStatus();
                return GLib.SOURCE_REMOVE;
            }));
    }

    _openApp() {
        try {
            const app = Gio.AppInfo.create_from_commandline(
                `python3 ${GLib.get_home_dir()}/lnxlink-gui/main.py`,
                'Automa', Gio.AppInfoCreateFlags.NONE);
            app.launch([], null);
        } catch (e) {
            console.error('Automa: failed to launch', e);
        }
    }

    _startPolling() {
        this._pollTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, POLL_INTERVAL_MS, () => {
            this._updateStatus();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopPolling() {
        if (this._pollTimer) {
            GLib.source_remove(this._pollTimer);
            this._pollTimer = null;
        }
    }

    _runCmd(argv, callback) {
        try {
            const proc = Gio.Subprocess.new(argv,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
            proc.communicate_utf8_async(null, null, (p, res) => {
                try {
                    const [, stdout] = p.communicate_utf8_finish(res);
                    callback(true, stdout ?? '');
                } catch (_) { callback(false, ''); }
            });
        } catch (_) { callback(false, ''); }
    }

    destroy() {
        this._stopPolling();
        super.destroy();
    }
});

export default class AutomaExtension extends Extension {
    enable() {
        this._indicator = new AutomaIndicator(this.path);
        Main.panel.addToStatusArea('automa-indicator', this._indicator, 1, 'right');
    }
    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
