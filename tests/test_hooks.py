"""The hooks are what make the rules binding, so they are tested like code.

A guard that fails open is not a guard, and a guard that cries wolf teaches you
to ignore it. Both failure modes are cheap to test and expensive to discover
later, so each hook gets a test for what it must block and a test for what it
must let through. The second kind is not padding: the first version of the
single-door guard flagged a docstring and a `print`, and these tests are what
caught it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def correr(hook: str, evento: dict) -> tuple[int, str, str]:
    """Run a hook exactly as Claude Code does: event JSON on stdin."""
    proceso = subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(evento),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    return proceso.returncode, proceso.stdout, proceso.stderr


def cargar(hook: str):
    """Import a hook as a module, to test its detector without a subprocess."""
    spec = importlib.util.spec_from_file_location(hook.removesuffix(".py"), HOOKS / hook)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def bash(command: str) -> dict:
    return {
        "tool_name": "Bash",
        "hook_event_name": "PreToolUse",
        "tool_input": {"command": command},
    }


def decision(salida: str) -> str | None:
    if not salida.strip():
        return None
    return json.loads(salida).get("hookSpecificOutput", {}).get("permissionDecision")


# --- venv_guard: el entorno virtual es obligatorio ------------------------


def test_venv_guard_bloquea_el_python_global():
    _, salida, _ = correr("venv_guard.py", bash("python scripts/weekly_capture.py"))
    assert decision(salida) == "deny"


def test_venv_guard_permite_uv_run():
    _, salida, _ = correr("venv_guard.py", bash("uv run python scripts/weekly_capture.py"))
    assert decision(salida) is None


def test_venv_guard_permite_el_interprete_del_venv():
    _, salida, _ = correr("venv_guard.py", bash("./.venv/Scripts/python.exe -m pytest"))
    assert decision(salida) is None


def test_venv_guard_permite_crear_el_entorno():
    # Sin esta excepción el hook impediría construir el entorno que exige usar.
    _, salida, _ = correr("venv_guard.py", bash("python -m venv .venv"))
    assert decision(salida) is None


def test_venv_guard_no_confunde_una_version_con_una_invocacion():
    # Guarda contra el falso positivo: este hook mira el texto completo del
    # comando, heredocs incluidos, y «Python 3.11.9» ahí dentro es prosa.
    _, salida, _ = correr("venv_guard.py", bash("echo '(Python 3.11.9, uv 0.11.19)'"))
    assert decision(salida) is None


# El hook `freeze_guard.py` se retiró: vigilaba la capa equivocada. Hacía
# `re.search` sobre el texto del comando, así que bloqueaba escribir prosa que
# mencionara un nombre de archivo e impedía desarrollar los propios scripts de
# evaluación sobre datos de desarrollo. El control equivalente vive ahora en el
# dato: `panel.as_of_view` y los modos de `ReplayMode`, con la prueba de
# propiedades de `test_revisions.py` como garantía. Lo que falta —rechazar un
# corte confirmatorio sin acta cuyo hash coincida— es criterio de aceptación de
# G1 y está escrito en el contrato de `load_as_of`.


# --- puerta_unica: una sola ruta al dato ----------------------------------


def test_puerta_unica_esta_satisfecha_en_el_estado_actual():
    # Es el invariante vivo del repositorio, no un caso sintético: si alguien
    # abre una segunda ruta al dato, esta prueba falla antes que cualquier otra.
    codigo, salida, _ = correr(
        "puerta_unica.py",
        {"tool_name": "Edit", "hook_event_name": "PostToolUse", "tool_input": {}},
    )
    assert codigo == 0
    assert salida.strip() == "", salida


def test_puerta_unica_detecta_una_segunda_ruta(tmp_path: Path):
    puerta = cargar("puerta_unica.py")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "src" / "revmon").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "99_atajo.py").write_text(
        "import pandas as pd\n"
        'panel = pd.read_parquet("data/derived/panel.parquet")\n',
        encoding="utf-8",
    )

    fallas = puerta.revisar(tmp_path)

    assert len(fallas) == 1
    assert "99_atajo.py:2" in fallas[0]


def test_puerta_unica_no_marca_una_mencion_en_prosa(tmp_path: Path):
    puerta = cargar("puerta_unica.py")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "src" / "revmon").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "98_prosa.py").write_text(
        '"""Writes data/derived/panel.parquet."""\n'
        'print("cached versions under data/raw/hub_versions/")\n',
        encoding="utf-8",
    )

    assert puerta.revisar(tmp_path) == []


def test_puerta_unica_detecta_un_cliente_de_red_fuera_de_sources(tmp_path: Path):
    """La puerta única no es dónde se abre el socket: es quién puede hablar.

    Con un cliente de terceros las peticiones ocurren dentro de la librería, así
    que lo que se vigila es el import. Un script que importa `epidatpy` es una
    segunda puerta aunque no contenga una sola llamada HTTP.
    """
    puerta = cargar("puerta_unica.py")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "src" / "revmon").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "97_red.py").write_text(
        "import epidatpy\n\n\ndef main():\n    return epidatpy\n",
        encoding="utf-8",
    )

    fallas = puerta.revisar(tmp_path)

    assert len(fallas) == 1
    assert "97_red.py:1" in fallas[0]


def test_puerta_unica_permite_el_cliente_de_red_en_sources(tmp_path: Path):
    """Y la puerta legítima no se marca a sí misma."""
    puerta = cargar("puerta_unica.py")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "src" / "revmon").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src" / "revmon" / "sources.py").write_text(
        "import requests\nfrom epidatpy import EpiDataContext\n",
        encoding="utf-8",
    )

    assert puerta.revisar(tmp_path) == []


# --- estado_sesion: informa, nunca bloquea -------------------------------


def test_estado_sesion_devuelve_contexto_y_no_bloquea():
    codigo, salida, _ = correr(
        "estado_sesion.py",
        {"hook_event_name": "SessionStart", "source": "startup"},
    )
    assert codigo == 0
    contexto = json.loads(salida)["hookSpecificOutput"]["additionalContext"]
    assert "revision-aware-monitoring" in contexto
    assert "HANDOFF.md" in contexto
