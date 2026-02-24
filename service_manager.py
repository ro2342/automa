"""
service_manager.py - Controla o lnxlink.service via DBus (org.freedesktop.systemd1).

Usa GLib/Gio para comunicação DBus — funciona dentro do sandbox Flatpak
sem precisar de flatpak-spawn ou acesso direto ao systemctl.
"""

import logging
from enum import Enum, auto

from gi.repository import Gio, GLib

log = logging.getLogger(__name__)

SERVICE_NAME = "lnxlink.service"

# Constantes DBus do systemd
SYSTEMD_BUS   = "org.freedesktop.systemd1"
SYSTEMD_PATH  = "/org/freedesktop/systemd1"
SYSTEMD_IFACE = "org.freedesktop.systemd1.Manager"
UNIT_IFACE    = "org.freedesktop.systemd1.Unit"
PROPS_IFACE   = "org.freedesktop.DBus.Properties"


class ServiceStatus(Enum):
    RUNNING = auto()
    STOPPED = auto()
    FAILED  = auto()
    UNKNOWN = auto()


def _get_systemd() -> Gio.DBusProxy:
    """Retorna um proxy para o Manager do systemd do usuário."""
    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.NONE,
        None,
        SYSTEMD_BUS,
        SYSTEMD_PATH,
        SYSTEMD_IFACE,
        None,
    )


def _get_unit_proxy(unit_path: str) -> Gio.DBusProxy:
    """Retorna proxy de propriedades para uma unit."""
    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.NONE,
        None,
        SYSTEMD_BUS,
        unit_path,
        PROPS_IFACE,
        None,
    )


def _call(proxy: Gio.DBusProxy, method: str, params=None) -> GLib.Variant:
    """Chama um método DBus e retorna o resultado."""
    return proxy.call_sync(
        method,
        params,
        Gio.DBusCallFlags.NONE,
        10000,  # timeout ms
        None,
    )


class ServiceManager:

    def get_status(self) -> ServiceStatus:
        try:
            mgr       = _get_systemd()
            result    = _call(mgr, "GetUnit", GLib.Variant("(s)", (SERVICE_NAME,)))
            unit_path = result[0]
            props     = _get_unit_proxy(unit_path)
            state     = _call(props, "Get",
                              GLib.Variant("(ss)", (UNIT_IFACE, "ActiveState")))[0]
            if state == "active":
                return ServiceStatus.RUNNING
            elif state == "failed":
                return ServiceStatus.FAILED
            else:
                return ServiceStatus.STOPPED
        except GLib.Error as e:
            # GetUnit falha se o serviço nunca foi carregado
            if "NoSuchUnit" in str(e):
                return ServiceStatus.STOPPED
            log.error("get_status DBus error: %s", e)
            return ServiceStatus.UNKNOWN
        except Exception as exc:
            log.error("get_status error: %s", exc)
            return ServiceStatus.UNKNOWN

    def get_status_text(self) -> str:
        try:
            mgr       = _get_systemd()
            result    = _call(mgr, "GetUnit", GLib.Variant("(s)", (SERVICE_NAME,)))
            unit_path = result[0]
            props     = _get_unit_proxy(unit_path)

            active  = _call(props, "Get", GLib.Variant("(ss)", (UNIT_IFACE, "ActiveState")))[0]
            sub     = _call(props, "Get", GLib.Variant("(ss)", (UNIT_IFACE, "SubState")))[0]
            desc    = _call(props, "Get", GLib.Variant("(ss)", (UNIT_IFACE, "Description")))[0]

            return f"● {SERVICE_NAME} - {desc}\n   Active: {active} ({sub})"
        except Exception as exc:
            return f"Error: {exc}"

    def is_enabled(self) -> bool:
        try:
            mgr    = _get_systemd()
            result = _call(mgr, "GetUnitFileState",
                           GLib.Variant("(s)", (SERVICE_NAME,)))
            return result[0] == "enabled"
        except Exception:
            return False

    def start(self) -> tuple[bool, str]:
        return self._ctl("StartUnit")

    def stop(self) -> tuple[bool, str]:
        return self._ctl("StopUnit")

    def restart(self) -> tuple[bool, str]:
        return self._ctl("RestartUnit")

    def enable(self) -> tuple[bool, str]:
        try:
            mgr = _get_systemd()
            _call(mgr, "EnableUnitFiles",
                  GLib.Variant("(asbb)", ([SERVICE_NAME], False, False)))
            _call(mgr, "Reload", None)
            log.info("enable %s: OK", SERVICE_NAME)
            return True, ""
        except Exception as exc:
            log.warning("enable error: %s", exc)
            return False, str(exc)

    def disable(self) -> tuple[bool, str]:
        try:
            mgr = _get_systemd()
            _call(mgr, "DisableUnitFiles",
                  GLib.Variant("(asb)", ([SERVICE_NAME], False)))
            _call(mgr, "Reload", None)
            log.info("disable %s: OK", SERVICE_NAME)
            return True, ""
        except Exception as exc:
            log.warning("disable error: %s", exc)
            return False, str(exc)

    def _ctl(self, method: str) -> tuple[bool, str]:
        try:
            mgr = _get_systemd()
            _call(mgr, method, GLib.Variant("(ss)", (SERVICE_NAME, "replace")))
            log.info("%s %s: OK", method, SERVICE_NAME)
            return True, ""
        except Exception as exc:
            log.warning("%s error: %s", method, exc)
            return False, str(exc)
