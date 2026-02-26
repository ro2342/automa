"""
config_manager.py - Lê e salva o config.yaml do LNXlink.

Estrutura real do LNXlink 2026.x:
  mqtt:
    server: 192.168.1.x   ← chave que o LNXlink lê (não 'host'!)
    host: 192.168.1.x     ← mantemos para compatibilidade
    port: 1883
    auth:
      user: ""
      pass: ""
  exclude:                ← nível RAIZ, não 'modules.exclude'
    - webcam
  custom_commands: []
"""

import logging
from pathlib import Path
from typing import Any

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    HAS_RUAMEL = True
except ImportError:
    HAS_RUAMEL = False
    import yaml
    logging.warning("ruamel.yaml não encontrado — usando PyYAML.")

log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "lnxlink" / "config.yaml"

KNOWN_SENSORS = {
    "battery":    ("Battery",        "Charge level and power state"),
    "cpu":        ("CPU Usage",      "Usage % per core"),
    "disk":       ("Disk Usage",     "Usage % per mount point"),
    "fan":        ("Fan Speed",      "RPM from hardware sensors"),
    "gpu":        ("GPU Usage",      "Usage % (requires compatible GPU)"),
    "idle":       ("Idle Status",    "Detects if the session is idle"),
    "media":      ("Media Player",   "Current track via MPRIS"),
    "memory":     ("Memory Usage",   "RAM and swap usage %"),
    "microphone": ("Microphone",     "Detects if mic is in use"),
    "monitor":    ("Monitor",        "Connected displays info"),
    "network":    ("Network Stats",  "Bytes sent/received per interface"),
    "notify":     ("Notifications",  "Send notifications from HA to desktop"),
    "power":      ("Power Profile",  "Active power profile"),
    "screen":     ("Screenshot",     "Take screenshots from HA"),
    "speakers":   ("Speaker Volume", "Current volume level"),
    "webcam":     ("Webcam In Use",  "Detects if any /dev/video* is being used"),
}


class ConfigManager:

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._data: Any = None
        if HAS_RUAMEL:
            self._yaml = YAML()
            self._yaml.preserve_quotes = True
            self._yaml.default_flow_style = False
            self._yaml.width = 120

    def load(self) -> bool:
        if not self.config_path.exists():
            self._data = {}
            return False
        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                self._data = (self._yaml.load(fh) if HAS_RUAMEL
                              else yaml.safe_load(fh)) or {}
            log.info("Config carregado de %s", self.config_path)
            return True
        except Exception as exc:
            log.error("Falha ao carregar config: %s", exc)
            self._data = {}
            return False

    def save(self) -> bool:
        if self._data is None:
            return False
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as fh:
                if HAS_RUAMEL:
                    self._yaml.dump(self._data, fh)
                else:
                    yaml.dump(self._data, fh,
                              default_flow_style=False, allow_unicode=True)
            log.info("Config salvo em %s", self.config_path)
            return True
        except Exception as exc:
            log.error("Falha ao salvar config: %s", exc)
            raise

    def _ensure_loaded(self):
        if self._data is None:
            self.load()

    def get(self, *keys, default=None):
        self._ensure_loaded()
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
            if node is default:
                return default
        return node

    def set(self, *keys_and_value):
        self._ensure_loaded()
        *keys, value = keys_and_value
        node = self._data
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = CommentedMap() if HAS_RUAMEL else {}
            node = node[k]
        node[keys[-1]] = value

    # ── MQTT ──────────────────────────────────────────────────────────

    def get_mqtt(self) -> dict:
        """
        Retorna as configurações MQTT.
        O LNXlink 2026.x lê 'mqtt.server' — nunca 'mqtt.host'.
        Garantimos que o host retornado nunca é string vazia.
        """
        server = str(self.get("mqtt", "server") or "").strip()
        host   = str(self.get("mqtt", "host")   or "").strip()

        # Usa o primeiro valor não-vazio e não-localhost entre server e host
        effective = ""
        for candidate in [server, host]:
            if candidate and candidate not in ("", "127.0.0.1", "localhost"):
                effective = candidate
                break
        if not effective:
            effective = server or host or "127.0.0.1"

        return {
            "host":             effective,
            "port":             int(self.get("mqtt", "port", default=1883) or 1883),
            "user":             str(self.get("mqtt", "auth", "user") or ""),
            "password":         str(self.get("mqtt", "auth", "pass") or ""),
            "discovery_prefix": str(self.get("mqtt", "discovery_prefix") or "homeassistant"),
            "prefix":           str(self.get("mqtt", "prefix") or "lnxlink"),
        }

    def set_mqtt(self, host: str, port: int, user: str, password: str,
                 discovery_prefix: str, prefix: str):
        """
        Salva configurações MQTT.
        Escreve em AMBAS as chaves 'host' e 'server' para compatibilidade.
        Nunca escreve string vazia — mantém o valor anterior se host estiver vazio.
        """
        if not host.strip():
            log.warning("set_mqtt chamado com host vazio — ignorando.")
            return
        self.set("mqtt", "host",             host.strip())
        self.set("mqtt", "server",           host.strip())  # chave que o LNXlink lê
        self.set("mqtt", "port",             int(port))
        self.set("mqtt", "auth", "user",     user)
        self.set("mqtt", "auth", "pass",     password)
        self.set("mqtt", "discovery_prefix", discovery_prefix or "homeassistant")
        self.set("mqtt", "prefix",           prefix or "lnxlink")

    # ── Sensores ──────────────────────────────────────────────────────

    def get_excluded_modules(self) -> list[str]:
        # LNXlink lê de modules.exclude — tenta primeiro lá
        excl = self.get("modules", "exclude", default=None)
        if excl is not None:
            return list(excl)
        # fallback: chave raiz "exclude" (formato antigo)
        excl = self.get("exclude", default=[])
        return list(excl) if excl else []

    def set_excluded_modules(self, excluded: list[str]):
        """Salva em modules.exclude — formato que o LNXlink 2026 lê."""
        self._ensure_loaded()
        if "modules" not in self._data or not isinstance(self._data["modules"], dict):
            self._data["modules"] = CommentedMap() if HAS_RUAMEL else {}
        self._data["modules"]["exclude"] = excluded
        # Remove chave raiz "exclude" antiga se existir
        if "exclude" in self._data:
            del self._data["exclude"]
        log.info("set_excluded_modules: %s", excluded)

    def is_sensor_enabled(self, sensor_key: str) -> bool:
        return sensor_key not in self.get_excluded_modules()

    def set_sensor_enabled(self, sensor_key: str, enabled: bool):
        excluded = self.get_excluded_modules()
        if enabled and sensor_key in excluded:
            excluded.remove(sensor_key)
        elif not enabled and sensor_key not in excluded:
            excluded.append(sensor_key)
        self.set_excluded_modules(excluded)

    # ── Comandos ──────────────────────────────────────────────────────

    def get_custom_commands(self) -> list[dict]:
        cmds = self.get("custom_commands", default=[])
        return list(cmds) if cmds else []

    def set_custom_commands(self, commands: list[dict]):
        self._ensure_loaded()
        self._data["custom_commands"] = commands
