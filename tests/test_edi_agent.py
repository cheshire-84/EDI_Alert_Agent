import sys
import time

import pytest

import edi_agent


# --- Validators ---

def test_is_valid_ip_accepts_ipv4():
    assert edi_agent.is_valid_ip("10.1.1.1") is True

def test_is_valid_ip_accepts_ipv6():
    assert edi_agent.is_valid_ip("::1") is True

def test_is_valid_ip_rejects_garbage():
    assert edi_agent.is_valid_ip("not-an-ip") is False
    assert edi_agent.is_valid_ip("999.999.999.999") is False

def test_is_valid_port_range():
    assert edi_agent.is_valid_port(1) is True
    assert edi_agent.is_valid_port(65535) is True
    assert edi_agent.is_valid_port(0) is False
    assert edi_agent.is_valid_port(65536) is False


# --- Formatters ---

def test_format_latency_with_value():
    assert edi_agent.format_latency(4.2) == "4 ms"

def test_format_latency_none():
    assert edi_agent.format_latency(None) == "--"

def test_format_last_checked_none_means_never():
    assert edi_agent.format_last_checked(None) == "never"

def test_format_last_checked_formats_timestamp():
    result = edi_agent.format_last_checked(time.time())
    assert len(result) == 8 and result.count(":") == 2

def test_format_check_method():
    assert edi_agent.format_check_method(None) == "ping"
    assert edi_agent.format_check_method(5432) == "TCP:5432"


# --- Config load/save round trip ---

def test_load_config_creates_empty_registry_when_missing():
    cfg = edi_agent.load_config()
    assert cfg == {"nodes": {}}

def test_save_and_load_round_trip():
    cfg = {"nodes": {"web": {"ip": "127.0.0.1", "status": "online"}}}
    edi_agent.save_config(cfg)
    assert edi_agent.load_config() == cfg


# --- check_target dispatch ---

def test_check_target_uses_ping_when_no_port(monkeypatch):
    monkeypatch.setattr(edi_agent, "ping_node", lambda ip: (True, 1.0))
    monkeypatch.setattr(edi_agent, "check_port", lambda ip, port, timeout=1: (False, None))
    assert edi_agent.check_target("10.0.0.1") == (True, 1.0)

def test_check_target_uses_port_when_given(monkeypatch):
    monkeypatch.setattr(edi_agent, "ping_node", lambda ip: (False, None))
    monkeypatch.setattr(edi_agent, "check_port", lambda ip, port, timeout=1: (True, 2.0))
    assert edi_agent.check_target("10.0.0.1", port=5432) == (True, 2.0)

def test_ping_nodes_concurrently_dispatches_per_node(monkeypatch):
    def fake_check_target(ip, port=None):
        return (ip == "1.1.1.1", 5.0 if ip == "1.1.1.1" else None)
    monkeypatch.setattr(edi_agent, "check_target", fake_check_target)

    nodes = {
        "good": {"ip": "1.1.1.1"},
        "bad": {"ip": "2.2.2.2", "port": 22},
    }
    results = edi_agent.ping_nodes_concurrently(nodes)
    assert results["good"] == (True, 5.0)
    assert results["bad"] == (False, None)

def test_ping_nodes_concurrently_empty():
    assert edi_agent.ping_nodes_concurrently({}) == {}


# --- CLI commands ---

def test_cli_add_rejects_invalid_ip(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("bad", "not-an-ip")
    cfg = edi_agent.load_config()
    assert "bad" not in cfg["nodes"]
    assert "not a valid IP" in capsys.readouterr().out

def test_cli_add_rejects_invalid_port(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", port=99999)
    cfg = edi_agent.load_config()
    assert "web" not in cfg["nodes"]
    assert "not a valid port" in capsys.readouterr().out

def test_cli_add_stores_node_with_port_and_latency(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 3.5))
    edi_agent.cli_add("plex", "10.0.0.5", port=32400)
    node = edi_agent.load_config()["nodes"]["plex"]
    assert node["ip"] == "10.0.0.5"
    assert node["port"] == 32400
    assert node["status"] == "online"
    assert node["latency_ms"] == 3.5
    assert node["last_checked"] > 0

def test_cli_add_duplicate_without_force_is_rejected(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    edi_agent.cli_add("web", "10.0.0.2")
    node = edi_agent.load_config()["nodes"]["web"]
    assert node["ip"] == "10.0.0.1"
    assert "already exists" in capsys.readouterr().out

def test_cli_add_duplicate_with_force_overwrites(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    edi_agent.cli_add("web", "10.0.0.2", force=True)
    node = edi_agent.load_config()["nodes"]["web"]
    assert node["ip"] == "10.0.0.2"

def test_cli_remove_deletes_existing_node(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    edi_agent.cli_remove("web")
    assert "web" not in edi_agent.load_config()["nodes"]

def test_cli_remove_missing_node_warns(capsys):
    edi_agent.cli_remove("ghost")
    assert "not found" in capsys.readouterr().out

def test_cli_list_empty_registry(capsys):
    edi_agent.cli_list()
    assert "No nodes currently monitored" in capsys.readouterr().out

def test_cli_list_shows_check_method_and_status(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 2.0))
    edi_agent.cli_add("plex", "10.0.0.5", port=32400)
    capsys.readouterr()  # discard cli_add's own output

    edi_agent.cli_list()
    out = capsys.readouterr().out
    assert "plex" in out
    assert "TCP:32400" in out
    assert "ONLINE" in out


# --- cli_edit ---

def test_cli_edit_missing_node_warns(capsys):
    edi_agent.cli_edit("ghost", ip="10.0.0.1")
    assert "not found" in capsys.readouterr().out

def test_cli_edit_no_changes_specified_warns(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    capsys.readouterr()
    edi_agent.cli_edit("web")
    assert "Nothing to update" in capsys.readouterr().out

def test_cli_edit_port_and_clear_port_conflict(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    capsys.readouterr()
    edi_agent.cli_edit("web", port=22, clear_port=True)
    assert "Cannot use --port and --clear-port together" in capsys.readouterr().out

def test_cli_edit_rejects_invalid_ip(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    capsys.readouterr()
    edi_agent.cli_edit("web", ip="not-an-ip")
    assert "not a valid IP" in capsys.readouterr().out
    assert edi_agent.load_config()["nodes"]["web"]["ip"] == "10.0.0.1"

def test_cli_edit_rejects_invalid_port(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    capsys.readouterr()
    edi_agent.cli_edit("web", port=70000)
    assert "not a valid port" in capsys.readouterr().out
    assert edi_agent.load_config()["nodes"]["web"].get("port") is None

def test_cli_edit_updates_ip_and_rechecks(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (False, None))
    edi_agent.cli_edit("web", ip="10.0.0.2")

    node = edi_agent.load_config()["nodes"]["web"]
    assert node["ip"] == "10.0.0.2"
    assert node["status"] == "offline"
    assert node["failures"] == 1

def test_cli_edit_adds_port_check(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("db", "10.0.0.5")

    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 3.0) if port == 5432 else (False, None))
    edi_agent.cli_edit("db", port=5432)

    node = edi_agent.load_config()["nodes"]["db"]
    assert node["port"] == 5432
    assert node["status"] == "online"
    assert node["latency_ms"] == 3.0

def test_cli_edit_clear_port_reverts_to_ping(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("db", "10.0.0.5", port=5432)

    edi_agent.cli_edit("db", clear_port=True)

    node = edi_agent.load_config()["nodes"]["db"]
    assert node["port"] is None


# --- EditNodeDialog (GUI) ---

def test_edit_dialog_saves_valid_changes(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 2.0))
    dialog = edi_agent.EditNodeDialog("web", edi_agent.load_config()["nodes"]["web"])
    dialog.ip_input.setText("10.0.0.2")
    dialog.port_input.setText("2222")
    dialog.on_save()

    node = edi_agent.load_config()["nodes"]["web"]
    assert node["ip"] == "10.0.0.2"
    assert node["port"] == 2222

def test_edit_dialog_rejects_invalid_ip_without_saving(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.EditNodeDialog("web", edi_agent.load_config()["nodes"]["web"])
    dialog.ip_input.setText("garbage")
    dialog.on_save()

    assert "not a valid IP" in dialog.error_label.text()
    assert edi_agent.load_config()["nodes"]["web"]["ip"] == "10.0.0.1"

def test_edit_dialog_rejects_non_numeric_port(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.EditNodeDialog("web", edi_agent.load_config()["nodes"]["web"])
    dialog.port_input.setText("not-a-port")
    dialog.on_save()

    assert "Port must be a number" in dialog.error_label.text()

def test_edit_dialog_blank_port_clears_existing_port(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("db", "10.0.0.5", port=5432)

    dialog = edi_agent.EditNodeDialog("db", edi_agent.load_config()["nodes"]["db"])
    dialog.port_input.setText("")
    dialog.on_save()

    assert edi_agent.load_config()["nodes"]["db"]["port"] is None


# --- Alert history ---

def test_load_history_empty_when_missing():
    assert edi_agent.load_history() == []

def test_record_history_event_appends():
    edi_agent.record_history_event("web", "offline", "web is down")
    events = edi_agent.load_history()
    assert len(events) == 1
    assert events[0]["node"] == "web"
    assert events[0]["event"] == "offline"
    assert events[0]["message"] == "web is down"
    assert events[0]["timestamp"] > 0

def test_record_history_event_trims_to_max_entries(monkeypatch):
    monkeypatch.setattr(edi_agent, "MAX_HISTORY_ENTRIES", 5)
    for i in range(8):
        edi_agent.record_history_event(f"node{i}", "offline", f"event {i}")
    events = edi_agent.load_history()
    assert len(events) == 5
    # Oldest events should have been dropped, newest kept
    assert events[-1]["node"] == "node7"
    assert events[0]["node"] == "node3"

def test_format_history_timestamp_none():
    assert edi_agent.format_history_timestamp(None) == "unknown"

def test_format_history_timestamp_formats():
    result = edi_agent.format_history_timestamp(time.time())
    assert len(result) == 19  # "YYYY-MM-DD HH:MM:SS"

def test_cli_history_empty(capsys):
    edi_agent.cli_history()
    assert "No alert history yet" in capsys.readouterr().out

def test_cli_history_shows_recent_events_newest_first(capsys):
    edi_agent.record_history_event("web", "offline", "web is down")
    edi_agent.record_history_event("web", "online", "web is back")
    capsys.readouterr()

    edi_agent.cli_history()
    out = capsys.readouterr().out
    offline_pos = out.find("OFFLINE")
    online_pos = out.find("ONLINE")
    assert offline_pos != -1 and online_pos != -1
    assert online_pos < offline_pos  # newest (online) listed first

def test_cli_history_respects_limit(capsys):
    for i in range(5):
        edi_agent.record_history_event(f"node{i}", "offline", f"event {i}")
    capsys.readouterr()

    edi_agent.cli_history(limit=2)
    out = capsys.readouterr().out
    assert "node4" in out and "node3" in out
    assert "node0" not in out

def test_check_nodes_records_history_on_offline_and_recovery(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    app = _make_bare_monitor_app(qapp)

    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (False, None))
    app.check_nodes(force=True)
    app.check_nodes(force=True)  # second consecutive failure trips the 2-strike threshold

    events = edi_agent.load_history()
    assert len(events) == 1
    assert events[0]["event"] == "offline"

    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    app.check_nodes(force=True)

    events = edi_agent.load_history()
    assert len(events) == 2
    assert events[1]["event"] == "online"


# --- HistoryDialog (GUI) ---

def test_history_dialog_shows_events(qapp):
    edi_agent.record_history_event("web", "offline", "web is down")
    edi_agent.record_history_event("web", "online", "web is back")

    dialog = edi_agent.HistoryDialog()
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 1).text() == "web"

def test_history_dialog_clear_history(qapp, monkeypatch):
    edi_agent.record_history_event("web", "offline", "web is down")
    dialog = edi_agent.HistoryDialog()
    assert dialog.table.rowCount() == 1

    monkeypatch.setattr(edi_agent.QMessageBox, "question", lambda *a, **k: edi_agent.QMessageBox.Yes)
    dialog.clear_history()

    assert dialog.table.rowCount() == 0
    assert edi_agent.load_history() == []


# --- Per-node interval / threshold ---

def test_is_valid_interval():
    assert edi_agent.is_valid_interval(5) is True
    assert edi_agent.is_valid_interval(30) is True
    assert edi_agent.is_valid_interval(4) is False

def test_is_valid_threshold():
    assert edi_agent.is_valid_threshold(1) is True
    assert edi_agent.is_valid_threshold(0) is False

def test_format_failures():
    assert edi_agent.format_failures(1, 3) == "1/3"

def test_format_interval():
    assert edi_agent.format_interval(45) == "45s"

def test_cli_add_defaults_interval_and_threshold(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    node = edi_agent.load_config()["nodes"]["web"]
    assert node["check_interval"] == edi_agent.DEFAULT_CHECK_INTERVAL
    assert node["failure_threshold"] == edi_agent.DEFAULT_FAILURE_THRESHOLD

def test_cli_add_custom_interval_and_threshold(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", interval=60, threshold=1)
    node = edi_agent.load_config()["nodes"]["web"]
    assert node["check_interval"] == 60
    assert node["failure_threshold"] == 1

def test_cli_add_rejects_too_small_interval(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", interval=1)
    assert "web" not in edi_agent.load_config()["nodes"]
    assert "not a valid interval" in capsys.readouterr().out

def test_cli_add_rejects_zero_threshold(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", threshold=0)
    assert "web" not in edi_agent.load_config()["nodes"]
    assert "not a valid threshold" in capsys.readouterr().out

def test_cli_edit_updates_interval_and_threshold(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    edi_agent.cli_edit("web", interval=120, threshold=5)
    node = edi_agent.load_config()["nodes"]["web"]
    assert node["check_interval"] == 120
    assert node["failure_threshold"] == 5

def test_cli_edit_rejects_invalid_interval(capsys, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    capsys.readouterr()
    edi_agent.cli_edit("web", interval=2)
    assert "not a valid interval" in capsys.readouterr().out
    assert edi_agent.load_config()["nodes"]["web"]["check_interval"] == edi_agent.DEFAULT_CHECK_INTERVAL

def _make_bare_monitor_app(qapp):
    from edi_agent import load_base_tray_pixmap, build_badged_icon
    from PySide6.QtGui import QIcon, QColor
    from PySide6.QtWidgets import QSystemTrayIcon
    from PySide6.QtCore import QTimer

    app = edi_agent.MonitorApp.__new__(edi_agent.MonitorApp)
    app.dialog = None
    base = load_base_tray_pixmap()
    app.icon_neutral = QIcon(base)
    app.icon_online = build_badged_icon(base, QColor("#2ecc71"))
    app.icon_offline = build_badged_icon(base, QColor("#e74c3c"))
    app.tray = QSystemTrayIcon()
    app.next_check_timer = QTimer()
    app.next_check_timer.setSingleShot(True)
    app.next_check_timer.timeout.connect(app.check_nodes)
    return app

def test_check_nodes_skips_node_not_yet_due(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", interval=3600)  # due in an hour
    original_last_checked = edi_agent.load_config()["nodes"]["web"]["last_checked"]

    app = _make_bare_monitor_app(qapp)
    call_count = {"n": 0}
    def counting_check(ip, port=None):
        call_count["n"] += 1
        return (False, None)
    monkeypatch.setattr(edi_agent, "check_target", counting_check)

    app.check_nodes()  # not forced, node isn't due yet

    assert call_count["n"] == 0
    assert edi_agent.load_config()["nodes"]["web"]["last_checked"] == original_last_checked

def test_check_nodes_force_bypasses_due_check(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", interval=3600)

    app = _make_bare_monitor_app(qapp)
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 2.0))
    app.check_nodes(force=True)

    node = edi_agent.load_config()["nodes"]["web"]
    assert node["latency_ms"] == 2.0

def test_check_nodes_respects_custom_threshold(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1", threshold=1)  # alert on first failure

    app = _make_bare_monitor_app(qapp)
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (False, None))
    app.check_nodes(force=True)

    node = edi_agent.load_config()["nodes"]["web"]
    assert node["status"] == "offline"
    events = edi_agent.load_history()
    assert len(events) == 1
    assert events[0]["event"] == "offline"


# --- EditNodeDialog interval/threshold validation ---

def test_edit_dialog_rejects_non_numeric_interval(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.EditNodeDialog("web", edi_agent.load_config()["nodes"]["web"])
    dialog.interval_input.setText("not-a-number")
    dialog.on_save()
    assert "Check interval must be a number" in dialog.error_label.text()

def test_edit_dialog_rejects_too_small_interval(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.EditNodeDialog("web", edi_agent.load_config()["nodes"]["web"])
    dialog.interval_input.setText("1")
    dialog.on_save()
    assert "at least 5 seconds" in dialog.error_label.text()

def test_edit_dialog_saves_custom_threshold(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.EditNodeDialog("web", edi_agent.load_config()["nodes"]["web"])
    dialog.threshold_input.setText("5")
    dialog.on_save()

    node = edi_agent.load_config()["nodes"]["web"]
    assert node["failure_threshold"] == 5


# --- AddNodeDialog (GUI) ---

def test_add_dialog_creates_node(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))

    dialog = edi_agent.AddNodeDialog()
    dialog.name_input.setText("plex")
    dialog.ip_input.setText("10.0.0.5")
    dialog.port_input.setText("32400")
    dialog.on_save()

    node = edi_agent.load_config()["nodes"]["plex"]
    assert node["ip"] == "10.0.0.5"
    assert node["port"] == 32400

def test_add_dialog_rejects_blank_name(qapp):
    dialog = edi_agent.AddNodeDialog()
    dialog.ip_input.setText("10.0.0.5")
    dialog.on_save()
    assert "cannot be blank" in dialog.error_label.text()
    assert edi_agent.load_config()["nodes"] == {}

def test_add_dialog_rejects_duplicate_name(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.AddNodeDialog()
    dialog.name_input.setText("web")
    dialog.ip_input.setText("10.0.0.2")
    dialog.on_save()

    assert "already exists" in dialog.error_label.text()
    assert edi_agent.load_config()["nodes"]["web"]["ip"] == "10.0.0.1"

def test_add_dialog_rejects_invalid_ip(qapp):
    dialog = edi_agent.AddNodeDialog()
    dialog.name_input.setText("web")
    dialog.ip_input.setText("not-an-ip")
    dialog.on_save()
    assert "not a valid IP" in dialog.error_label.text()
    assert edi_agent.load_config()["nodes"] == {}

def test_add_dialog_defaults_interval_and_threshold(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))

    dialog = edi_agent.AddNodeDialog()
    dialog.name_input.setText("web")
    dialog.ip_input.setText("10.0.0.1")
    dialog.on_save()

    node = edi_agent.load_config()["nodes"]["web"]
    assert node["check_interval"] == edi_agent.DEFAULT_CHECK_INTERVAL
    assert node["failure_threshold"] == edi_agent.DEFAULT_FAILURE_THRESHOLD


# --- NodeManagerDialog delete flow (GUI) ---

def test_delete_selected_removes_node_on_confirm(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.NodeManagerDialog()
    dialog.table.selectRow(0)
    monkeypatch.setattr(edi_agent.QMessageBox, "question", lambda *a, **k: edi_agent.QMessageBox.Yes)
    dialog.delete_selected()

    assert "web" not in edi_agent.load_config()["nodes"]
    assert dialog.table.rowCount() == 0

def test_delete_selected_keeps_node_on_cancel(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.NodeManagerDialog()
    dialog.table.selectRow(0)
    monkeypatch.setattr(edi_agent.QMessageBox, "question", lambda *a, **k: edi_agent.QMessageBox.No)
    dialog.delete_selected()

    assert "web" in edi_agent.load_config()["nodes"]

def test_delete_selected_no_row_selected_is_noop(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")

    dialog = edi_agent.NodeManagerDialog()
    dialog.table.clearSelection()
    dialog.table.setCurrentCell(-1, -1)
    dialog.delete_selected()

    assert "web" in edi_agent.load_config()["nodes"]


# --- NodeManagerDialog metric cards ---

def test_metric_cards_reflect_node_counts(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 5.0))
    edi_agent.cli_add("web", "10.0.0.1")
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (False, None))
    edi_agent.cli_add("db", "10.0.0.2")

    dialog = edi_agent.NodeManagerDialog()
    assert dialog.card_total.findChild(edi_agent.QLabel, "Val_TotalNodes").text() == "2"
    assert dialog.card_online.findChild(edi_agent.QLabel, "Val_Online").text() == "1"
    assert dialog.card_offline.findChild(edi_agent.QLabel, "Val_Offline").text() == "1"


# --- CLI return values / exit codes ---

def test_cli_add_returns_true_on_success(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    assert edi_agent.cli_add("web", "10.0.0.1") is True

def test_cli_add_returns_false_on_invalid_ip():
    assert edi_agent.cli_add("web", "not-an-ip") is False

def test_cli_remove_returns_true_when_removed(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    assert edi_agent.cli_remove("web") is True

def test_cli_remove_returns_false_when_missing():
    assert edi_agent.cli_remove("ghost") is False

def test_cli_edit_returns_true_on_success(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    assert edi_agent.cli_edit("web", ip="10.0.0.2") is True

def test_cli_edit_returns_false_on_missing_node():
    assert edi_agent.cli_edit("ghost", ip="10.0.0.1") is False

def test_main_exits_nonzero_on_validation_failure(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["edi-agent", "add", "web", "not-an-ip"])
    with pytest.raises(SystemExit) as exc_info:
        edi_agent.main()
    assert exc_info.value.code == 1

def test_main_does_not_exit_on_success(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    monkeypatch.setattr(sys, "argv", ["edi-agent", "add", "web", "10.0.0.1"])
    edi_agent.main()  # should not raise
    assert "web" in edi_agent.load_config()["nodes"]

def test_main_does_not_exit_for_list_command(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["edi-agent", "list"])
    edi_agent.main()  # should not raise even with no nodes
    assert "No nodes currently monitored" in capsys.readouterr().out


# --- Logging ---

def test_get_logger_writes_to_log_path():
    logger = edi_agent.get_logger()
    logger.info("test message")
    for handler in logger.handlers:
        handler.flush()
    assert edi_agent.LOG_PATH.exists()
    assert "test message" in edi_agent.LOG_PATH.read_text()

def test_cli_add_writes_log_entry(monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("web", "10.0.0.1")
    for handler in edi_agent.get_logger().handlers:
        handler.flush()
    assert "web" in edi_agent.LOG_PATH.read_text()


# --- Settings / theme ---

def test_load_settings_defaults_to_dark():
    assert edi_agent.load_settings() == {"theme": "dark"}

def test_save_and_load_settings_round_trip():
    edi_agent.save_settings({"theme": "light"})
    assert edi_agent.load_settings()["theme"] == "light"

def test_get_theme_stylesheet_dark_and_light():
    assert edi_agent.get_theme_stylesheet("dark") == edi_agent.DARK_GLASS_STYLE
    assert edi_agent.get_theme_stylesheet("light") == edi_agent.LIGHT_GLASS_STYLE
    assert edi_agent.get_theme_stylesheet("bogus") == edi_agent.DARK_GLASS_STYLE

def test_toggle_theme_switches_and_persists(qapp, monkeypatch):
    app = _make_bare_monitor_app(qapp)
    app.app = qapp
    app.theme = "dark"
    app.theme_action = edi_agent.QPushButton()  # stand-in with .setText()

    app.toggle_theme()

    assert app.theme == "light"
    assert edi_agent.load_settings()["theme"] == "light"

    app.toggle_theme()
    assert app.theme == "dark"
    assert edi_agent.load_settings()["theme"] == "dark"


# --- Adaptive check scheduling ---

def test_schedule_next_check_uses_shortest_remaining_interval(qapp, monkeypatch):
    monkeypatch.setattr(edi_agent, "check_target", lambda ip, port=None: (True, 1.0))
    edi_agent.cli_add("slow", "10.0.0.1", interval=3600)
    edi_agent.cli_add("fast", "10.0.0.2", interval=5)

    app = _make_bare_monitor_app(qapp)
    app.schedule_next_check()

    # The "fast" node (interval=5s, just checked) should dominate scheduling,
    # so the next tick should be soon, not up to an hour away.
    assert app.next_check_timer.interval() <= 5000

def test_schedule_next_check_defaults_when_no_nodes(qapp):
    app = _make_bare_monitor_app(qapp)
    app.schedule_next_check()
    assert app.next_check_timer.interval() == edi_agent.DEFAULT_CHECK_INTERVAL * 1000
