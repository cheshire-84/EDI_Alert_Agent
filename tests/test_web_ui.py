import pytest

import edi_agent
import web_ui


@pytest.fixture
def client():
    app = web_ui.create_web_app()
    app.testing = True
    return app.test_client()


def _add(name="plex", ip="10.1.1.99", port=None, interval=None, threshold=None):
    edi_agent.cli_add(name, ip, port=port, interval=interval, threshold=threshold)


# --- index / static page ---

def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"8-Bit Agent" in resp.data


# --- GET /api/nodes ---

def test_list_nodes_empty(client):
    resp = client.get("/api/nodes")
    assert resp.status_code == 200
    assert resp.get_json() == {"nodes": {}}


def test_list_nodes_returns_added_node(client):
    _add()
    resp = client.get("/api/nodes")
    data = resp.get_json()
    assert "plex" in data["nodes"]
    assert data["nodes"]["plex"]["ip"] == "10.1.1.99"


# --- POST /api/nodes (add) ---

def test_add_node_success(client):
    resp = client.post("/api/nodes", json={"name": "gateway", "ip": "10.1.1.1"})
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert "gateway" in edi_agent.load_config()["nodes"]


def test_add_node_blank_name_rejected(client):
    resp = client.post("/api/nodes", json={"name": "", "ip": "10.1.1.1"})
    assert resp.status_code == 400
    assert "blank" in resp.get_json()["error"]


def test_add_node_duplicate_rejected(client):
    _add()
    resp = client.post("/api/nodes", json={"name": "plex", "ip": "10.1.1.100"})
    assert resp.status_code == 400
    assert "already exists" in resp.get_json()["error"]


def test_add_node_invalid_ip_rejected(client):
    resp = client.post("/api/nodes", json={"name": "x", "ip": "not-an-ip"})
    assert resp.status_code == 400
    assert "not a valid IP" in resp.get_json()["error"]


def test_add_node_invalid_port_rejected(client):
    resp = client.post("/api/nodes", json={"name": "x", "ip": "10.1.1.1", "port": "999999"})
    assert resp.status_code == 400
    assert "Port" in resp.get_json()["error"]


def test_add_node_with_port_interval_threshold(client):
    resp = client.post("/api/nodes", json={
        "name": "db", "ip": "10.1.1.20", "port": "5432", "interval": "60", "threshold": "3",
    })
    assert resp.status_code == 200
    node = edi_agent.load_config()["nodes"]["db"]
    assert node["port"] == 5432
    assert node["check_interval"] == 60
    assert node["failure_threshold"] == 3


# --- PUT /api/nodes/<name> (edit) ---

def test_edit_node_success(client):
    _add()
    resp = client.put("/api/nodes/plex", json={"ip": "10.1.1.200"})
    assert resp.status_code == 200
    assert edi_agent.load_config()["nodes"]["plex"]["ip"] == "10.1.1.200"


def test_edit_node_not_found(client):
    resp = client.put("/api/nodes/ghost", json={"ip": "10.1.1.1"})
    assert resp.status_code == 404


def test_edit_node_clears_port_when_blank(client):
    _add(port=32400)
    resp = client.put("/api/nodes/plex", json={"ip": "10.1.1.99", "port": ""})
    assert resp.status_code == 200
    assert edi_agent.load_config()["nodes"]["plex"]["port"] is None


def test_edit_node_invalid_ip_rejected(client):
    _add()
    resp = client.put("/api/nodes/plex", json={"ip": "garbage"})
    assert resp.status_code == 400


# --- DELETE /api/nodes/<name> ---

def test_delete_node_success(client):
    _add()
    resp = client.delete("/api/nodes/plex")
    assert resp.status_code == 200
    assert "plex" not in edi_agent.load_config()["nodes"]


def test_delete_node_not_found(client):
    resp = client.delete("/api/nodes/ghost")
    assert resp.status_code == 404


# --- POST /api/refresh ---

def test_refresh_without_monitor_app_updates_status(client, monkeypatch):
    _add()
    monkeypatch.setattr(
        edi_agent, "ping_nodes_concurrently", lambda nodes: {n: (True, 1.0) for n in nodes}
    )
    resp = client.post("/api/refresh")
    assert resp.status_code == 200
    assert edi_agent.load_config()["nodes"]["plex"]["status"] == "online"


def test_refresh_uses_monitor_app_check_nodes_when_given():
    calls = []

    class FakeMonitor:
        def check_nodes(self, force=False):
            calls.append(force)

        def refresh_tray_icon(self, cfg):
            pass

    app = web_ui.create_web_app(monitor_app=FakeMonitor())
    app.testing = True
    client = app.test_client()
    resp = client.post("/api/refresh")
    assert resp.status_code == 200
    assert calls == [True]


# --- GET /api/history ---

def test_history_returns_events(client):
    edi_agent.record_history_event("plex", "offline", "down")
    edi_agent.record_history_event("plex", "online", "back")
    resp = client.get("/api/history?limit=1")
    data = resp.get_json()
    assert len(data["events"]) == 1
    assert data["events"][0]["event"] == "online"
