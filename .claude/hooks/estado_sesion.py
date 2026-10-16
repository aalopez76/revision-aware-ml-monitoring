"""Hook SessionStart: imprime el estado mecánico del proyecto al arrancar.

El juicio sobre qué sigue vive en `HANDOFF.md`, que lo escribe una persona. Esto
es lo complementario: los hechos que se pueden leer del sistema de archivos y de
git sin opinar.

Existe porque esos hechos son los que más caro cuesta suponer mal, y porque un
HANDOFF puede quedarse viejo mientras el sistema de archivos no.

Protocolo: devuelve `additionalContext`. Nunca bloquea; si algo falla, calla.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

COMPUERTAS = {
    "00_source_feasibility.json": "G0 · viabilidad y procedencia de fuentes",
    "01_vertical_slice.json": "G1 · ciclo operacional completo",
    "02_decision_sensitivity.json": "G2 · sensibilidad de decisiones (N1)",
    "03_policy_value.json": "G3 · utilidad condicional (frontera de costo)",
}

ACTA = Path("reports") / "results" / "frozen_method.json"

# Fechas del régimen de reporte, verificadas. El universo elegible se declara
# desde el nuevo mandato; mezclar el periodo voluntario sería meter un cambio de
# cobertura dentro de la serie que se estudia.
MANDATO_REINICIADO = date(2024, 11, 1)


def raiz() -> Path | None:
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


def git(root: Path, *args: str) -> str:
    try:
        salida = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return salida.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def semanas_faltantes(semanales: list[Path]) -> int:
    """Semanas ISO transcurridas desde la primera corrida que no dejaron archivo.

    Es conciliación, no estadística: un hueco se cuenta para que se vea, y lo
    que significa cada hueco lo dictamina `/registro-semanal`.
    """
    if not semanales:
        return 0
    try:
        primero = semanales[0].stem
        anio, semana = int(primero[:4]), int(primero.split("W")[1])
        inicio = date.fromisocalendar(anio, semana, 1)
    except (ValueError, IndexError):
        return 0
    hoy = datetime.now(UTC).date()
    transcurridas = max(0, ((hoy - inicio).days // 7) + 1)
    return max(0, transcurridas - len(semanales))


def informe(root: Path) -> str:
    lineas = ["Estado mecánico de revision-aware-monitoring (leído del disco, no del HANDOFF):"]

    resultados = root / "reports" / "results"
    hechas = [etiqueta for nombre, etiqueta in COMPUERTAS.items() if (resultados / nombre).exists()]
    if hechas:
        lineas.append("  compuertas con artefacto: " + "; ".join(hechas))
    else:
        lineas.append(
            "  compuertas con artefacto: ninguna. Fase: antes de G0. "
            f"Universo elegible declarado desde {MANDATO_REINICIADO.isoformat()}"
        )

    acta = root / ACTA
    if acta.exists():
        try:
            datos = json.loads(acta.read_text(encoding="utf-8"))
            lineas.append(
                f"  método CONGELADO el {datos.get('frozen_at', '?')} "
                f"(commit {str(datos.get('project_commit_sha', '?'))[:12]}). "
                "La cohorte confirmatoria se evalúa una sola vez."
            )
        except (OSError, json.JSONDecodeError):
            lineas.append(f"  {ACTA.as_posix()} existe pero no se pudo leer — revísalo")
    else:
        lineas.append(
            "  método NO congelado. El control de la cohorte confirmatoria es el "
            "contrato as-of del dato, no un guardián por nombre de archivo"
        )

    semanales = sorted((root / "reports" / "weekly").glob("*.json"))
    if semanales:
        faltan = semanas_faltantes(semanales)
        detalle = f", {faltan} semanas sin archivo" if faltan else ", sin huecos"
        lineas.append(
            f"  evidencia operacional: {len(semanales)} capturas, "
            f"la última {semanales[-1].stem}{detalle}"
        )
    else:
        lineas.append(
            "  evidencia operacional: 0 capturas. Es lo único irrecuperable: un dato "
            "se reconsulta si la fuente lo conserva, una corrida que no ocurrió no"
        )

    clave = "configurada" if os.environ.get("DELPHI_EPIDATA_KEY", "").strip() else "AUSENTE"
    lineas.append(
        f"  clave de la API de Delphi: {clave} "
        "(sin ella el acceso es anónimo: 60 peticiones/hora)"
    )

    remoto = git(root, "remote", "-v")
    if not remoto:
        lineas.append(
            "  SIN REMOTO: la captura programada no ha podido correr nunca. En "
            "repositorio público GitHub además desactiva el cron tras 60 días sin actividad"
        )
    else:
        rama = git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?"
        pendientes = [x for x in git(root, "status", "--porcelain").splitlines() if x]
        lineas.append(f"  git: rama {rama}, {len(pendientes)} archivos sin commitear")

    lineas.append("  Lee HANDOFF.md antes de decidir qué sigue.")
    return "\n".join(lineas)


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    root = raiz()
    if root is None:
        return 0

    try:
        contexto = informe(root)
    except OSError:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": contexto,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
