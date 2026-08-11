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
    """Point every persisted-state path (config, history, settings, log) at
    throwaway files so tests never touch the real ~/.config/edi-alert-agent/
    or ~/.local/state/edi-alert-agent/ files."""
    fake_config = tmp_path / "nodes.json"
    fake_history = tmp_path / "history.json"
    fake_settings = tmp_path / "settings.json"
    fake_log = tmp_path / "edi-agent.log"
    monkeypatch.setattr(edi_agent, "CONFIG_PATH", fake_config)
    monkeypatch.setattr(edi_agent, "HISTORY_PATH", fake_history)
    monkeypatch.setattr(edi_agent, "SETTINGS_PATH", fake_settings)
    monkeypatch.setattr(edi_agent, "LOG_PATH", fake_log)
    return fake_config
