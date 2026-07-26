import pytest

import edi_agent


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point CONFIG_PATH at a throwaway file so tests never touch the real
    ~/.config/edi-alert-agent/nodes.json."""
    fake_path = tmp_path / "nodes.json"
    monkeypatch.setattr(edi_agent, "CONFIG_PATH", fake_path)
    return fake_path
