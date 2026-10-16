"""Hook PreToolUse(Bash): bloquea invocar Python o pip fuera del entorno virtual.

Este proyecto se desarrolla **siempre** dentro de `.venv`, administrado por
`uv` contra `uv.lock`. Esta máquina tiene un Python global en el PATH, así que
un `python script.py` escrito por descuido correría con otro intérprete y otras
dependencias — y una cifra producida con otras versiones no es la misma cifra.
El hook lo impide antes de que corra, en lugar de confiar en recordarlo.

Protocolo: lee el JSON del evento por stdin y responde con
`permissionDecision: "deny"` si detecta una invocación fuera del entorno.
Silencio y salida 0 en cualquier otro caso.
"""

from __future__ import annotations

import json
import re
import sys

# Invocación de python/pip en posición de comando: al inicio del segmento, o
# tras un operador de shell. **Sin IGNORECASE a propósito**: un comando se
# escribe en minúsculas, y «Python 3.11» con mayúscula es prosa — este hook
# también mira texto que va dentro de heredocs y mensajes de commit.
INVOCACION = re.compile(
    r"(?:^|[;&|(]|&&|\|\|)\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*"
    r"(python3?|pip3?|py)(?:\.exe)?\b(?P<resto>.*)",
)

# «python 3.11.9», «uv 0.11.19»: una versión no es una invocación. Sin esto el
# hook bloquea su propia documentación, y un guardián que grita en falso enseña
# a ignorarlo.
VERSION_EN_PROSA = re.compile(r"^\s*v?\d")

# Señales de que sí se está usando el entorno del proyecto.
ENTORNO = re.compile(r"\.venv[\\/]|\buv\s+(run|sync|venv|pip|lock|export)\b", re.IGNORECASE)

# Excepción de arranque: crear el propio entorno exige el Python global una vez.
# Sin esto el hook impediría construir el entorno que el hook exige usar.
ARRANQUE = re.compile(r"-m\s+venv\b|--version\b|-V\b|-m\s+ensurepip\b", re.IGNORECASE)


def segmentos(comando: str) -> list[str]:
    """Parte el comando en segmentos separados por operadores de shell."""
    return [s for s in re.split(r"&&|\|\||[;|]", comando) if s.strip()]


def main() -> int:
    try:
        evento = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # sin evento legible no hay comando que juzgar

    if evento.get("tool_name") != "Bash":
        return 0

    comando = str((evento.get("tool_input") or {}).get("command") or "")

    culpables = []
    for segmento in segmentos(comando):
        encontrado = INVOCACION.search(segmento)
        if encontrado is None:
            continue
        if VERSION_EN_PROSA.match(encontrado.group("resto")):
            continue
        if ENTORNO.search(segmento) or ARRANQUE.search(segmento):
            continue
        culpables.append(segmento.strip())

    if not culpables:
        return 0

    razon = (
        "Bloqueado: este proyecto corre exclusivamente dentro de .venv "
        "(hay un Python global en el PATH y usarlo daría otro intérprete y "
        "otras dependencias).\n"
        f"Segmento detectado: {culpables[0]}\n\n"
        "Reescríbelo con `uv run ...` o con ./.venv/Scripts/python.exe. "
        "Si el entorno no existe todavía: uv sync --locked --extra dev"
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": razon,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
