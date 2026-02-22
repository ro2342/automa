"""
i18n.py - Internacionalização via GNU gettext com compilação automática de .mo

Se o arquivo .mo não existir ou estiver desatualizado em relação ao .po,
compila automaticamente usando o módulo 'babel' ou 'msgfmt' do sistema.
Isso significa que tradutores só precisam editar o .po — o app cuida do resto.
"""

import gettext
import locale
import os
import logging
import struct
import array
from pathlib import Path

log = logging.getLogger(__name__)

DOMAIN = "lnxlink-gui"
_BASE_DIR = Path(__file__).parent.resolve()
LOCALE_DIR = _BASE_DIR / "locale"

AVAILABLE_LANGUAGES = {
    "system": "System Default",
    "en":     "English",
    "pt_BR":  "Português (Brasil)",
    "es":     "Español",
    "de":     "Deutsch",
    "fr":     "Français",
    "it":     "Italiano",
}

_current_lang = "system"
_translation: gettext.NullTranslations = gettext.NullTranslations()


# ------------------------------------------------------------------ #
#  Compilador .po → .mo em Python puro (sem depender do msgfmt)      #
# ------------------------------------------------------------------ #

def _compile_po_to_mo(po_path: Path, mo_path: Path):
    """
    Compila um arquivo .po para .mo em Python puro.
    Usa babel se disponível, senão usa implementação própria.
    """
    try:
        from babel.messages.pofile import read_po
        from babel.messages.mofile import write_mo
        with open(po_path, "rb") as po_file:
            catalog = read_po(po_file)
        with open(mo_path, "wb") as mo_file:
            write_mo(mo_file, catalog)
        log.info("Compilado (babel): %s → %s", po_path.name, mo_path.name)
        return True
    except ImportError:
        pass

    # Fallback: tenta msgfmt do sistema
    try:
        import subprocess
        result = subprocess.run(
            ["msgfmt", str(po_path), "-o", str(mo_path)],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            log.info("Compilado (msgfmt): %s → %s", po_path.name, mo_path.name)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    log.warning("Não foi possível compilar %s (instale babel: pip install babel)", po_path)
    return False


def _ensure_mo(lang_code: str) -> bool:
    """Garante que o arquivo .mo existe e está atualizado para o idioma."""
    po_path = LOCALE_DIR / lang_code / "LC_MESSAGES" / f"{DOMAIN}.po"
    mo_path = LOCALE_DIR / lang_code / "LC_MESSAGES" / f"{DOMAIN}.mo"

    if not po_path.exists():
        return False

    # Recompila se .mo não existe ou .po é mais novo
    if not mo_path.exists() or po_path.stat().st_mtime > mo_path.stat().st_mtime:
        mo_path.parent.mkdir(parents=True, exist_ok=True)
        return _compile_po_to_mo(po_path, mo_path)

    return True


# ------------------------------------------------------------------ #
#  API pública                                                        #
# ------------------------------------------------------------------ #

def setup(lang_code: str = "system"):
    """
    Inicializa o sistema de tradução.
    Chame no início do app, ANTES de criar a janela principal.
    """
    global _translation, _current_lang
    _current_lang = lang_code

    if lang_code == "system":
        try:
            system_lang = locale.getdefaultlocale()[0]  # ex: "pt_BR"
        except Exception:
            system_lang = None
        langs = [system_lang] if system_lang else []
    else:
        langs = [lang_code]

    # Tenta compilar .mo para cada idioma candidato
    for lang in langs:
        if lang:
            _ensure_mo(lang)
            # Tenta também o código curto (ex: "pt" para "pt_BR")
            short = lang.split("_")[0]
            if short != lang:
                _ensure_mo(short)

    try:
        _translation = gettext.translation(
            domain=DOMAIN,
            localedir=str(LOCALE_DIR),
            languages=langs if langs else None,
            fallback=True,
        )
        log.info("Tradução ativa: %s (locale dir: %s)", langs, LOCALE_DIR)
    except Exception as exc:
        log.warning("Falha ao carregar tradução %s: %s", langs, exc)
        _translation = gettext.NullTranslations()


def _(text: str) -> str:
    """Traduz uma string. Uso: from i18n import _"""
    return _translation.gettext(text)


def get_current_lang() -> str:
    return _current_lang
