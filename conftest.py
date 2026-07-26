import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import edi_agent


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the whole test session (Qt widgets need one)."""
    app = QApplication.instance() or QApplication([])
    yield app

@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point CONFIG_PATH at a throwaway file so tests never touch the real
    ~/.config/edi-alert-agent/nodes.json."""
    fake_path = tmp_path / "nodes.json"
    monkeypatch.setattr(edi_agent, "CONFIG_PATH", fake_path)
    return fake_path
