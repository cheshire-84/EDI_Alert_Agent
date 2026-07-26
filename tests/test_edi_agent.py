import time

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
