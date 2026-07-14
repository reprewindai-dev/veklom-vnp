from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_standalone_landing_labels_x402_settlement_evidence_live():
    source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "{ name: 'x402 settlement evidence', weight: 'Live' }" in source
    assert "{ name: 'x402 settlement evidence', weight: 'Connected' }" not in source


def test_vabp_does_not_fabricate_pgl_evidence_ids():
    source = (ROOT / "app" / "api" / "routers" / "vabp.py").read_text(encoding="utf-8")

    assert "ev_vabp_" not in source
    assert "Mocked evidence ID" not in source
