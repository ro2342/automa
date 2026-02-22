"""
service_manager.py - Gerencia o lnxlink.service do systemd --user.

IMPORTANTE: enable() e disable() NÃO iniciam/param o serviço.
Usamos 'systemctl --user enable' sem --now para não interferir
com o estado atual do serviço.
"""

import subprocess
import os
import logging
from enum import Enum, auto

log = logging.getLogger(__name__)

SERVICE_NAME = "lnxlink.service"
IS_FLATPAK   = bool(os.environ.get("FLATPAK_ID"))


class ServiceStatus(Enum):
    RUNNING = auto()
    STOPPED = auto()
    FAILED  = auto()
    UNKNOWN = auto()


def _build_cmd(args: list[str]) -> list[str]:
    if IS_FLATPAK:
        return ["flatpak-spawn", "--host"] + args
    return args


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    cmd = _build_cmd(args)
    log.debug("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10, **kwargs)


class ServiceManager:

    def get_status(self) -> ServiceStatus:
        try:
            result = _run(["systemctl", "--user", "is-active", SERVICE_NAME])
            state  = result.stdout.strip()
            if state == "active":
                return ServiceStatus.RUNNING
            elif state == "failed":
                return ServiceStatus.FAILED
            else:
                return ServiceStatus.STOPPED
        except subprocess.TimeoutExpired:
            return ServiceStatus.UNKNOWN
        except Exception as exc:
            log.error("get_status error: %s", exc)
            return ServiceStatus.UNKNOWN

    def get_status_text(self) -> str:
        try:
            result = _run(["systemctl", "--user", "status", SERVICE_NAME])
            return result.stdout or result.stderr or "(no output)"
        except Exception as exc:
            return f"Error: {exc}"

    def is_enabled(self) -> bool:
        try:
            result = _run(["systemctl", "--user", "is-enabled", SERVICE_NAME])
            return result.stdout.strip() == "enabled"
        except Exception:
            return False

    def start(self) -> tuple[bool, str]:
        return self._ctl("start")

    def stop(self) -> tuple[bool, str]:
        return self._ctl("stop")

    def restart(self) -> tuple[bool, str]:
        return self._ctl("restart")

    def enable(self) -> tuple[bool, str]:
        # SEM --now para não iniciar o serviço automaticamente
        return self._ctl("enable")

    def disable(self) -> tuple[bool, str]:
        # SEM --now para não parar o serviço automaticamente
        return self._ctl("disable")

    def _ctl(self, action: str) -> tuple[bool, str]:
        try:
            result  = _run(["systemctl", "--user", action, SERVICE_NAME])
            success = result.returncode == 0
            msg     = (result.stdout or result.stderr or "").strip()
            if success:
                log.info("systemctl %s %s: OK", action, SERVICE_NAME)
            else:
                log.warning("systemctl %s failed (rc=%d): %s",
                            action, result.returncode, msg)
            return success, msg
        except subprocess.TimeoutExpired:
            return False, "Timeout."
        except FileNotFoundError:
            return False, "systemctl not found."
        except Exception as exc:
            return False, str(exc)
