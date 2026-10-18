"""The manifest seal: it must reject a changed document, and spare old schemas.

Two failure modes, both cheap to test and expensive to discover later. A seal
that passes when the governing document changed proves nothing. A seal that
fails every past run the moment a typo is fixed trains you to ignore it.

Everything here runs against a **copy** in a temporary directory. Proving that a
changed document is rejected must never require editing the sealed one.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_verifier():
    """Import the verifier script as a module.

    Registered in `sys.modules` before execution because `@dataclass` resolves
    its defining module through it; without that, building `Claim` raises.
    """
    spec = importlib.util.spec_from_file_location(
        "verify_results", ROOT / "scripts" / "verify_results.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_fake_repo(tmp_path: Path, verifier, *, schema: int) -> dict[str, Path]:
    """A miniature repository: the two sealed documents and one manifest."""
    documents = {}
    for field, name in verifier.SEALED_DOCUMENTS.items():
        path = tmp_path / name
        path.write_text(f"contents of {field}\n", encoding="utf-8")
        documents[field] = path

    manifest = {"schema_version": schema}
    for field in verifier.SCHEMA_REQUIREMENTS[schema]:
        manifest[field] = hashlib.sha256(
            documents[field].read_bytes()
        ).hexdigest()

    results = tmp_path / "reports" / "results"
    results.mkdir(parents=True)
    (results / "01_vertical_slice.json").write_text(
        json.dumps({"manifest": manifest}), encoding="utf-8"
    )
    return documents


def test_a_matching_seal_passes(tmp_path):
    verifier = load_verifier()
    build_fake_repo(tmp_path, verifier, schema=2)
    assert verifier.check_manifests(root=tmp_path) == []


def test_changing_one_byte_of_the_plan_is_rejected(tmp_path):
    """The integrity test, on a copy. The sealed document is never touched."""
    verifier = load_verifier()
    documents = build_fake_repo(tmp_path, verifier, schema=2)
    plan = documents["g1_mp_plan_sha256"]
    plan.write_bytes(plan.read_bytes().replace(b"contents", b"contentS"))

    failures = verifier.check_manifests(root=tmp_path)
    assert len(failures) == 1
    label, detail = failures[0]
    assert "g1_mp_plan_sha256" in label
    assert "changed since the run" in detail


def test_a_missing_document_is_rejected_not_skipped(tmp_path):
    verifier = load_verifier()
    documents = build_fake_repo(tmp_path, verifier, schema=2)
    documents["g1_mp_plan_sha256"].unlink()
    failures = verifier.check_manifests(root=tmp_path)
    assert any("not on disk" in detail for _, detail in failures)


def test_an_older_schema_is_verified_under_its_own_contract(tmp_path):
    """A schema-1 run carries no plan hash, and that is not a failure.

    This is the half that matters for honesty: requiring an old manifest to
    match a document edited after it would turn every past result red the
    moment a typo is fixed, and the rule would stop meaning anything.
    """
    verifier = load_verifier()
    build_fake_repo(tmp_path, verifier, schema=1)
    assert verifier.check_manifests(root=tmp_path) == []


def test_an_unknown_schema_fails_loudly_rather_than_passing(tmp_path):
    """A manifest from a future version must not be waved through."""
    verifier = load_verifier()
    build_fake_repo(tmp_path, verifier, schema=2)
    path = tmp_path / "reports" / "results" / "01_vertical_slice.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest"]["schema_version"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.check_manifests(root=tmp_path)
    assert any("unknown manifest schema_version 99" in detail for _, detail in failures)


def test_a_schema_that_requires_a_field_rejects_its_absence(tmp_path):
    verifier = load_verifier()
    build_fake_repo(tmp_path, verifier, schema=2)
    path = tmp_path / "reports" / "results" / "01_vertical_slice.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["manifest"]["g1_mp_plan_sha256"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.check_manifests(root=tmp_path)
    assert any("requires g1_mp_plan_sha256" in detail for _, detail in failures)


def test_the_real_repository_seals_both_governing_documents():
    """Exactly two .txt are sealed, and both exist. No copy involved: read-only."""
    verifier = load_verifier()
    assert set(verifier.SEALED_DOCUMENTS) == {"spec_sha256", "g1_mp_plan_sha256"}
    for name in verifier.SEALED_DOCUMENTS.values():
        assert (ROOT / name).exists(), f"{name} is sealed but not on disk"
