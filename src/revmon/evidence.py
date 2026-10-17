"""Manifests, hashes and writes that cannot half-happen.

What makes a run auditable is not that it logged something: it is that a reader
can tie a number to the code, the configuration and the data version that
produced it, and can tell a real run from a replay of one.

Three properties this module exists to guarantee:

* **Atomic writes.** A result file is written to a temporary neighbour and
  renamed, so a crash leaves either the old file or the new one and never a
  truncated artefact that looks like evidence.
* **Immutability.** A prediction is written once. If the same cut, model and
  horizon come round again, the existing record is returned untouched: a
  forecast that gets rewritten when its label is revised is the exact failure
  this project studies.
* **Labelled modality.** Every record says whether it came from a real run, a
  historical replay, a controlled exercise or a proposal. A replay reconstructed
  today does not become a run that happened in the past by being stored next to
  one.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from revmon import sources

RESULTS = sources.ROOT / "reports" / "results"
FIGURES = sources.ROOT / "reports" / "figures"
PREDICTIONS = sources.ROOT / "reports" / "predictions"


class Modality:
    """What a record is. Never inferred, always written down."""

    OBSERVED_RUN = "observed_run"
    HISTORICAL_REPLAY = "historical_replay"
    CONTROLLED_EXERCISE = "controlled_exercise"
    PROPOSAL = "proposal"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(payload: Any) -> str:
    """Hash of a payload in canonical form, so key order cannot change it."""
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))


def sha256_path(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def sha256_tree(root: Path, pattern: str = "**/*.py") -> str:
    """One hash over a directory's sources, so a manifest can name the code.

    Sorted paths and relative names: a hash that depended on filesystem order or
    on where the repository is checked out would not be reproducible.
    """
    digest = hashlib.sha256()
    for path in sorted(root.glob(pattern)):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=sources.ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def write_json_atomic(path: Path, payload: object) -> Path:
    """Write via a temporary neighbour and rename. Never a partial artefact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    os.replace(temporary, path)
    return path


@dataclass
class RunManifest:
    """Everything needed to tie a result to what produced it."""

    run_id: str
    modality: str
    decision_as_of: str
    started_at: str
    code_sha: str
    code_tree_sha256: str
    lock_sha256: str | None
    spec_sha256: str | None
    runner: str
    config: dict[str, Any] = field(default_factory=dict)
    provenance: list[dict[str, str]] = field(default_factory=list)
    state: str = "started"
    errors: list[str] = field(default_factory=list)

    @classmethod
    def start(cls, *, decision_as_of: str, modality: str, config: dict) -> RunManifest:
        now = datetime.now(UTC)
        spec = sources.ROOT / "When_the_Past_Moves_Especificacion_Ejecutable_V3_3_2026.txt"
        return cls(
            run_id=f"{now.strftime('%Y%m%dT%H%M%SZ')}-{decision_as_of}",
            modality=modality,
            decision_as_of=decision_as_of,
            started_at=now.isoformat(),
            code_sha=git_commit(),
            code_tree_sha256=sha256_tree(sources.ROOT / "src"),
            lock_sha256=sha256_path(sources.ROOT / "uv.lock"),
            spec_sha256=sha256_path(spec),
            runner=os.environ.get("GITHUB_RUN_ID", "local"),
            config=config,
        )

    def as_dict(self) -> dict:
        return asdict(self)


def record_prediction(payload: dict) -> tuple[dict, bool]:
    """Persist a prediction once, and return the stored one if it already exists.

    The second element says whether this call wrote. A caller that gets `False`
    is looking at a forecast issued earlier, and that is the point: re-running a
    cut must not produce a new prediction, and a revised label must not change
    one already emitted.
    """
    path = PREDICTIONS / f"{payload['prediction_id']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), False
    write_json_atomic(path, payload)
    return payload, True
