"""Hook PostToolUse(Edit|Write): comprueba que el dato siga teniendo una sola puerta.

`src/revmon/panel.py` es la única puerta al dato, e `io.py` la única que toca la
red. La razón no es orden: la cantidad central del proyecto es **qué se podía
saber y cuándo**, así que una segunda ruta al dato es una segunda definición de
esa cantidad — y es exactamente por donde entra un look-ahead sin que nadie lo
vea. Ver `.claude/rules/datos.md`.

Un invariante así se puede comprobar mecánicamente, así que lo comprueba un hook
en lugar de un recordatorio. Corre después de cada edición, cuesta milisegundos
y señala el archivo y la línea.

Protocolo: `{"decision": "block", "reason": ...}` devuelve el hallazgo al modelo.
La herramienta ya corrió; esto no deshace la edición, la reporta.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Las dos puertas legítimas, por su ruta relativa a la raíz.
EXENTOS = {
    Path("src/revmon/panel.py"),
    Path("src/revmon/sources.py"),
}

AMBITOS = (Path("scripts"), Path("src/revmon"))

# Se busca **la lectura**, no la mención. Una primera versión de este hook
# marcaba cualquier línea que dijera `data/`, y por eso señalaba un docstring y
# un mensaje de `print`: ruido que enseña a ignorar al guardián. Lo que de
# verdad abre una segunda puerta es una llamada que toca el archivo, así que eso
# es lo que se detecta.
HALLAZGOS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(read_parquet|to_parquet)\s*\("),
        "toca el parquet del panel: se obtiene con revmon.panel.load_panel()",
    ),
    (
        re.compile(r"\b(read_csv|read_table|read_fwf)\s*\("),
        "parsea una fuente cruda: eso vive en revmon.panel, no en un script",
    ),
    (
        re.compile(r"\bopen\s*\([^)]*\bdata\b"),
        "abre un archivo bajo data/ directamente",
    ),
    (
        re.compile(r"\b(sources\.RAW|sources\.CACHE|panel\.PANEL|panel\.DERIVED)\b"),
        "usa una ruta interna de otro módulo en lugar de su función pública",
    ),
    # La puerta única no es el lugar donde se abre el socket: es el módulo al que
    # se le permite hablar con la red. Con un cliente de terceros (epidatpy) las
    # peticiones ocurren dentro de la librería, así que lo que se vigila es quién
    # puede importarla. Un `import epidatpy` en un script es una segunda puerta
    # aunque no contenga una sola llamada HTTP.
    (
        re.compile(r"^\s*(?:from|import)\s+(epidatpy|requests|urllib|httpx)\b", re.MULTILINE),
        "importa un cliente de red: eso vive en revmon.sources y en ningún otro sitio",
    ),
)


def raiz() -> Path | None:
    """La raíz del proyecto, o None. No adivina: la reconoce o se rinde."""
    candidatas = []
    if env := os.environ.get("CLAUDE_PROJECT_DIR"):
        candidatas.append(Path(env))
    candidatas.append(Path.cwd())
    candidatas.extend(Path.cwd().parents)

    for candidata in candidatas:
        try:
            if (candidata / "pyproject.toml").exists() and (candidata / "src" / "revmon").is_dir():
                return candidata
        except OSError:
            continue
    return None


def revisar(root: Path) -> list[str]:
    fallas: list[str] = []
    for ambito in AMBITOS:
        for archivo in sorted((root / ambito).rglob("*.py")):
            relativo = archivo.relative_to(root)
            if relativo in EXENTOS:
                continue
            try:
                lineas = archivo.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for numero, linea in enumerate(lineas, start=1):
                if linea.lstrip().startswith("#"):
                    continue
                for patron, motivo in HALLAZGOS:
                    if patron.search(linea):
                        fallas.append(f"{relativo.as_posix()}:{numero} — {motivo}")
    return fallas


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    root = raiz()
    if root is None:
        return 0  # fuera del proyecto no hay invariante que comprobar

    fallas = revisar(root)
    if not fallas:
        return 0

    razon = (
        "La regla de la puerta única está rota (.claude/rules/datos.md).\n\n"
        + "\n".join(f"  {f}" for f in fallas)
        + "\n\nTodo acceso al dato pasa por src/revmon/panel.py, y toda llamada "
        "a la red por src/revmon/sources.py. Si hace falta un dato que el panel no "
        "expone, la corrección es ampliar el panel, no abrir una segunda ruta."
    )
    print(json.dumps({"decision": "block", "reason": razon}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
