"""
installer.py - Detecta, instala e configura o LNXlink completamente.

Etapas realizadas PELO APP, sem terminal:
  1. Detecta a distro Linux
  2. Instala dependências de sistema via pkexec (janela gráfica de senha)
  3. Instala pipx via pkexec
  4. Instala lnxlink via pipx (sem root)
  5. Cria ~/.config/lnxlink/config.yaml com valores padrão
  6. Cria ~/.config/systemd/user/lnxlink.service
  7. Habilita e inicia o serviço via systemctl --user
"""

import subprocess
import shutil
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Conteúdo do config.yaml padrão criado na primeira execução         #
# ------------------------------------------------------------------ #
DEFAULT_CONFIG_YAML = """\
mqtt:
  host: 127.0.0.1
  port: 1883
  auth:
    user: ""
    pass: ""
  discovery_prefix: homeassistant
  prefix: lnxlink

modules:
  exclude:
    - gpu
    - webcam

custom_commands: []
"""

# ------------------------------------------------------------------ #
#  Conteúdo do arquivo .service do systemd                            #
# ------------------------------------------------------------------ #
SYSTEMD_SERVICE = """\
[Unit]
Description=LNXlink MQTT Agent
After=network.target

[Service]
Type=simple
ExecStart={lnxlink_bin} -c {config_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


@dataclass
class Distro:
    name: str
    family: str


def detect_distro() -> Distro:
    """Lê /etc/os-release e identifica a distribuição Linux."""
    info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k] = v.strip('"')
    except FileNotFoundError:
        pass

    id_like = info.get("ID_LIKE", "").lower()
    distro_id = info.get("ID", "").lower()
    name = info.get("PRETTY_NAME", distro_id or "Linux")
    combined = distro_id + " " + id_like

    if any(x in combined for x in ["fedora", "rhel", "centos", "rocky", "alma"]):
        return Distro(name=name, family="fedora")
    if any(x in combined for x in ["debian", "ubuntu", "mint", "pop"]):
        return Distro(name=name, family="debian")
    if any(x in combined for x in ["arch", "manjaro", "endeavour"]):
        return Distro(name=name, family="arch")
    if any(x in combined for x in ["suse", "opensuse"]):
        return Distro(name=name, family="suse")
    if "alpine" in combined:
        return Distro(name=name, family="alpine")
    return Distro(name=name, family="unknown")


def is_lnxlink_installed() -> bool:
    """Verifica PATH padrão + ~/.local/bin (onde o pipx instala)."""
    if shutil.which("lnxlink"):
        return True
    return Path.home().joinpath(".local/bin/lnxlink").exists()


def is_pipx_installed() -> bool:
    if shutil.which("pipx"):
        return True
    return Path.home().joinpath(".local/bin/pipx").exists()


def get_pipx_bin() -> str:
    return shutil.which("pipx") or str(Path.home() / ".local/bin/pipx")


def get_lnxlink_bin() -> str:
    found = shutil.which("lnxlink")
    if found:
        return found
    local = Path.home() / ".local/bin/lnxlink"
    if local.exists():
        return str(local)
    # pipx instala no venv — tenta localizar
    venv = Path.home() / ".local/share/pipx/venvs/lnxlink/bin/lnxlink"
    if venv.exists():
        return str(venv)
    return str(local)


def is_service_installed() -> bool:
    """Verifica se o arquivo .service existe."""
    service_path = Path.home() / ".config/systemd/user/lnxlink.service"
    return service_path.exists()


def is_config_created() -> bool:
    """Verifica se o config.yaml do LNXlink existe."""
    return (Path.home() / ".config/lnxlink/config.yaml").exists()


# ------------------------------------------------------------------ #
#  Comandos por distro (pkexec = janela gráfica de senha do GNOME)   #
# ------------------------------------------------------------------ #

def _sys_deps_cmd(family: str) -> list[str] | None:
    cmds = {
        "fedora": ["pkexec", "dnf", "install", "-y",
                   "gcc", "cmake", "kernel-headers",
                   "python3-devel", "alsa-lib-devel", "portaudio-devel"],
        "debian": ["pkexec", "apt", "install", "-y",
                   "gcc", "cmake", "python3-dev",
                   "libasound2-dev", "portaudio19-dev"],
        "arch":   ["pkexec", "pacman", "-S", "--noconfirm",
                   "gcc", "cmake", "python-pyaudio"],
        "suse":   ["pkexec", "zypper", "install", "-y",
                   "gcc", "cmake", "python3-devel"],
        "alpine": ["pkexec", "apk", "add",
                   "gcc", "cmake", "linux-headers", "python3-dev"],
    }
    return cmds.get(family)


def _pipx_install_cmd(family: str) -> list[str]:
    cmds = {
        "fedora":  ["pkexec", "dnf", "install", "-y", "pipx"],
        "debian":  ["pkexec", "apt", "install", "-y", "pipx"],
        "arch":    ["pkexec", "pacman", "-S", "--noconfirm", "python-pipx"],
        "suse":    ["pkexec", "zypper", "install", "-y", "python3-pipx"],
        "alpine":  ["pkexec", "apk", "add", "pipx"],
    }
    return cmds.get(family, ["python3", "-m", "pip", "install", "--user", "pipx"])


# ------------------------------------------------------------------ #
#  Orquestrador principal                                             #
# ------------------------------------------------------------------ #

class LNXlinkInstaller:
    """
    Instala e configura o LNXlink completamente, sem nenhum terminal.
    progress_cb(mensagem, porcentagem) é chamado em cada etapa.
    """

    def __init__(self, progress_cb: Callable[[str, int], None] | None = None):
        self.progress_cb = progress_cb or (lambda m, p: None)
        self.distro = detect_distro()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _step(self, msg: str, pct: int):
        log.info("[%d%%] %s", pct, msg)
        self.progress_cb(msg, pct)

    def _run(self, cmd: list[str], name: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "").strip()
                log.error("%s falhou (rc=%d): %s", name, r.returncode, err)
                return False, err
            return True, ""
        except subprocess.TimeoutExpired:
            return False, f"Timeout: {name}"
        except FileNotFoundError as e:
            return False, f"Comando não encontrado: {e}"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------ #

    def install(self) -> tuple[bool, str]:
        try:
            from i18n import _
        except ImportError:
            _ = lambda x, **kw: x  # noqa

        self._step(f"Distro detectada: {self.distro.name}", 0)

        # ── Etapa 1: Dependências de sistema ──────────────────────────
        cmd = _sys_deps_cmd(self.distro.family)
        if cmd:
            self._step("Instalando dependências do sistema...", 10)
            ok, err = self._run(cmd, "deps")
            if not ok:
                log.warning("Deps falhou (continuando): %s", err)

        if self._cancelled:
            return False, "Cancelado."

        # ── Etapa 2: pipx ─────────────────────────────────────────────
        if not is_pipx_installed():
            self._step("Instalando pipx...", 25)
            ok, err = self._run(_pipx_install_cmd(self.distro.family), "pipx")
            if not ok:
                return False, f"Falha ao instalar pipx:\n{err}"
        else:
            self._step("pipx já instalado ✓", 25)

        if self._cancelled:
            return False, "Cancelado."

        # ── Etapa 3: LNXlink via pipx ─────────────────────────────────
        self._step("Instalando LNXlink via pipx...", 45)
        pipx = get_pipx_bin()
        ok, err = self._run([pipx, "install", "lnxlink"], "lnxlink-install")
        if not ok:
            # Tenta upgrade caso já esteja instalado
            ok, _ = self._run([pipx, "upgrade", "lnxlink"], "lnxlink-upgrade")
            if not ok:
                return False, (
                    f"Falha ao instalar LNXlink:\n{err}\n\n"
                    "Tente manualmente:\n  pipx install lnxlink"
                )

        if self._cancelled:
            return False, "Cancelado."

        # ── Etapa 4: Cria config.yaml padrão ─────────────────────────
        self._step("Criando configuração padrão...", 65)
        self._create_default_config()

        # ── Etapa 5: Cria e habilita o serviço systemd ───────────────
        self._step("Configurando serviço systemd...", 78)
        ok, err = self._create_systemd_service()
        if not ok:
            log.warning("Falha ao criar serviço (continuando): %s", err)

        if self._cancelled:
            return False, "Cancelado."

        # ── Etapa 6: Inicia o serviço ─────────────────────────────────
        self._step("Iniciando o serviço LNXlink...", 90)
        self._run(["systemctl", "--user", "daemon-reload"], "daemon-reload")
        self._run(["systemctl", "--user", "enable", "lnxlink.service"], "enable")
        self._run(["systemctl", "--user", "start",  "lnxlink.service"], "start")

        # ── Etapa 7: Verifica ─────────────────────────────────────────
        self._step("Verificando instalação...", 96)
        if not is_lnxlink_installed():
            return False, (
                "LNXlink instalado mas não encontrado no PATH.\n"
                "Adicione ao ~/.bashrc:\n"
                "  export PATH=$HOME/.local/bin:$PATH\n"
                "Depois reinicie o app."
            )

        self._step("LNXlink instalado e configurado com sucesso! ✓", 100)
        return True, "LNXlink instalado e configurado com sucesso! ✓"

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _create_default_config(self):
        """
        Cria ~/.config/lnxlink/config.yaml se não existir.
        Já exclui por padrão os módulos conhecidamente problemáticos.
        """
        config_path = Path.home() / ".config/lnxlink/config.yaml"
        if config_path.exists():
            log.info("config.yaml já existe — mantendo.")
            return
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Módulos problemáticos excluídos por padrão:
        # - webcam: usa OpenCV e falha com múltiplos /dev/video* (kernel 4.16+)
        # - wifi/wol: requerem sudo ethtool sem senha
        # - docker/steam: requerem software específico instalado
        default_exclude = ["webcam", "wifi", "wol", "docker", "steam"]

        content = f"""\
mqtt:
  host: 127.0.0.1
  server: 127.0.0.1
  port: 1883
  auth:
    user: ""
    pass: ""
  discovery_prefix: homeassistant
  prefix: lnxlink

# Módulos desabilitados (problemáticos em sistemas padrão):
exclude:
{chr(10).join(f'  - {m}' for m in default_exclude)}

custom_commands: []
update_interval: 5
"""
        config_path.write_text(content)
        log.info("config.yaml criado com exclude padrão: %s", default_exclude)

    def _create_systemd_service(self) -> tuple[bool, str]:
        """
        Cria ~/.config/systemd/user/lnxlink.service.
        Não usa root — o systemd do usuário aceita unidades em ~/.config/systemd/user/.
        """
        service_dir = Path.home() / ".config/systemd/user"
        service_path = service_dir / "lnxlink.service"

        lnxlink_bin  = get_lnxlink_bin()
        config_path  = str(Path.home() / ".config/lnxlink/config.yaml")

        service_dir.mkdir(parents=True, exist_ok=True)
        service_path.write_text(
            SYSTEMD_SERVICE.format(
                lnxlink_bin=lnxlink_bin,
                config_path=config_path,
            )
        )
        log.info("Serviço criado em %s", service_path)
        return True, ""
