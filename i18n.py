"""
i18n.py - Internacionalização via GNU gettext com compilação automática de .mo
"""

import gettext
import locale
import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DOMAIN = "lnxlink-gui"
_BASE_DIR = Path(__file__).parent.resolve()
LOCALE_DIR = _BASE_DIR / "locale"

# Apenas idiomas com arquivos .po reais
AVAILABLE_LANGUAGES = {
    "system": "System Default",
    "en":     "English",
    "pt_BR":  "Português (Brasil)",
}

_current_lang = "system"
_translation: gettext.NullTranslations = gettext.NullTranslations()


def _compile_po_to_mo(po_path: Path, mo_path: Path):
    try:
        from babel.messages.pofile import read_po
        from babel.messages.mofile import write_mo
        with open(po_path, "rb") as f:
            catalog = read_po(f)
        with open(mo_path, "wb") as f:
            write_mo(f, catalog)
        log.info("Compilado (babel): %s → %s", po_path.name, mo_path.name)
        return True
    except ImportError:
        pass
    try:
        import subprocess
        r = subprocess.run(["msgfmt", str(po_path), "-o", str(mo_path)],
                           capture_output=True, timeout=10)
        if r.returncode == 0:
            log.info("Compilado (msgfmt): %s → %s", po_path.name, mo_path.name)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    log.warning("Não foi possível compilar %s (instale babel: pip install babel)", po_path)
    return False


def _ensure_mo(lang_code: str) -> bool:
    po_path = LOCALE_DIR / lang_code / "LC_MESSAGES" / f"{DOMAIN}.po"
    mo_path = LOCALE_DIR / lang_code / "LC_MESSAGES" / f"{DOMAIN}.mo"
    if not po_path.exists():
        return False
    if not mo_path.exists() or po_path.stat().st_mtime > mo_path.stat().st_mtime:
        mo_path.parent.mkdir(parents=True, exist_ok=True)
        return _compile_po_to_mo(po_path, mo_path)
    return True


def setup(lang_code: str = "system"):
    global _translation, _current_lang
    _current_lang = lang_code

    if lang_code == "system":
        try:
            system_lang = locale.getdefaultlocale()[0]
        except Exception:
            system_lang = None
        langs = [system_lang] if system_lang else []
    else:
        langs = [lang_code]

    for lang in langs:
        if lang:
            _ensure_mo(lang)
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
        log.info("Tradução ativa: %s", langs)
    except Exception as exc:
        log.warning("Falha ao carregar tradução %s: %s", langs, exc)
        _translation = gettext.NullTranslations()


def _(text: str) -> str:
    return _translation.gettext(text)


def get_current_lang() -> str:
    return _current_lang
