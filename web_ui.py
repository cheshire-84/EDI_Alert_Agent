#!/usr/bin/env python3
# 8-Bit Agent - Local Web Dashboard (Flask + waitress, loopback-only)
"""Optional local web UI, bound to 127.0.0.1 only. Mirrors the same
add/edit/delete/refresh capabilities as the CLI and tray Dashboard - it
calls the exact same cli_add/cli_edit/cli_remove/check_nodes functions, so
there is no second copy of the business logic to keep in sync. It cannot
push real-time alerts like the tray (no desktop session to notify); that
gap is covered by Discord webhook alerts instead.

Deliberately never binds to 0.0.0.0 - this project's whole premise is a
personal, per-machine monitor, not a shared/networked service. Anyone who
wants LAN or remote access can put their own reverse proxy or SSH tunnel
in front of it; that is a decision the app should never make for them.
"""
import time
from flask import Flask, jsonify, request, Response

import edi_agent

DEFAULT_WEB_PORT = 7317


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>8-Bit Agent Dashboard</title>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #e2e8f0;
    --muted: #94a3b8; --blue: #3b82f6; --green: #2ecc71; --red: #e74c3c;
    --purple: #8b5cf6; --amber: #f59e0b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: "Inter", "Noto Sans", "Cantarell", "DejaVu Sans", sans-serif;
    padding: 24px;
  }
  h1 { font-size: 20px; margin: 0 0 4px 0; }
  .sub { color: var(--muted); font-size: 12px; margin-bottom: 20px; }
  .cards { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 12px 16px; min-width: 140px; border-left: 4px solid var(--accent, var(--blue));
  }
  .card .title { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
  .card .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 10px; overflow: hidden; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 13px; }
  th { color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }
  tr:last-child td { border-bottom: none; }
  .status-online { color: var(--green); font-weight: 600; }
  .status-offline { color: var(--red); font-weight: 600; }
  .actions { margin: 16px 0; display: flex; gap: 8px; align-items: center; }
  button {
    background: var(--border); color: var(--text); border: none; border-radius: 6px;
    padding: 8px 14px; font-size: 13px; cursor: pointer;
  }
  button.primary { background: var(--blue); color: white; }
  button.danger { background: var(--red); color: white; }
  button:hover { filter: brightness(1.15); }
  .row-actions button { padding: 4px 10px; font-size: 12px; margin-right: 4px; }
  .modal-backdrop {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,.55);
    align-items: center; justify-content: center; z-index: 50;
  }
  .modal-backdrop.open { display: flex; }
  .modal {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px; width: 360px; max-width: 90vw;
  }
  .modal h2 { margin: 0 0 14px 0; font-size: 16px; }
  .modal label { display: block; font-size: 12px; color: var(--muted); margin: 10px 0 4px; }
  .modal input {
    width: 100%; padding: 8px; border-radius: 6px; border: 1px solid var(--border);
    background: #0f172a; color: var(--text); font-size: 13px;
  }
  .modal .err { color: var(--red); font-size: 12px; margin-top: 8px; min-height: 14px; }
  .modal .btn-row { margin-top: 16px; display: flex; justify-content: flex-end; gap: 8px; }
  .toast-wrap { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 8px; z-index: 100; }
  .toast {
    background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--green);
    padding: 10px 14px; border-radius: 8px; font-size: 13px; min-width: 220px;
    box-shadow: 0 4px 12px rgba(0,0,0,.3);
  }
  .toast.error { border-left-color: var(--red); }
  .empty { color: var(--muted); padding: 20px; text-align: center; }
</style>
</head>
<body>
  <h1>8-Bit Agent</h1>
  <div class="sub">Local dashboard &middot; bound to 127.0.0.1 only &middot; v__VERSION__</div>

  <div class="cards">
    <div class="card" style="--accent: var(--blue)"><div class="title">Total Nodes</div><div class="value" id="m-total">0</div></div>
    <div class="card" style="--accent: var(--green)"><div class="title">Online</div><div class="value" id="m-online">0</div></div>
    <div class="card" style="--accent: var(--red)"><div class="title">Offline</div><div class="value" id="m-offline">0</div></div>
    <div class="card" style="--accent: var(--purple)"><div class="title">Avg Latency</div><div class="value" id="m-latency">--</div></div>
  </div>

  <div class="actions">
    <button class="primary" onclick="openAddModal()">Add Node</button>
    <button onclick="refreshNow()">Refresh Now</button>
    <span class="sub" id="last-refresh" style="margin:0;"></span>
  </div>

  <table id="node-table">
    <thead><tr>
      <th>Name</th><th>IP</th><th>Check</th><th>Status</th><th>Fails</th>
      <th>Interval</th><th>Latency</th><th>Last Checked</th><th></th>
    </tr></thead>
    <tbody id="node-tbody"></tbody>
  </table>

  <div class="modal-backdrop" id="node-modal">
    <div class="modal">
      <h2 id="node-modal-title">Add Node</h2>
      <input type="hidden" id="f-original-name">
      <label>Node Name</label>
      <input id="f-name" placeholder="e.g. plex">
      <label>IP Address</label>
      <input id="f-ip" placeholder="e.g. 10.1.1.99">
      <label>Port (blank = ICMP ping)</label>
      <input id="f-port" placeholder="e.g. 5432, 32400, 8006">
      <label>Check Interval (seconds)</label>
      <input id="f-interval" value="30">
      <label>Alert Threshold (failures)</label>
      <input id="f-threshold" value="2">
      <div class="err" id="node-modal-err"></div>
      <div class="btn-row">
        <button onclick="closeNodeModal()">Cancel</button>
        <button class="primary" onclick="submitNodeModal()">Save</button>
      </div>
    </div>
  </div>

  <div class="modal-backdrop" id="delete-modal">
    <div class="modal">
      <h2>Delete Node</h2>
      <p id="delete-modal-text" style="font-size:13px;"></p>
      <div class="btn-row">
        <button onclick="closeDeleteModal()">Cancel</button>
        <button class="danger" onclick="confirmDelete()">Delete</button>
      </div>
    </div>
  </div>

  <div class="toast-wrap" id="toast-wrap"></div>

<script>
let editingName = null;
let deleteTarget = null;

function toast(msg, isError) {
  const wrap = document.getElementById('toast-wrap');
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

async function api(path, opts) {
  const resp = await fetch(path, Object.assign({headers: {'Content-Type': 'application/json'}}, opts || {}));
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function fmtLatency(ms) { return ms === null || ms === undefined ? '--' : Math.round(ms) + ' ms'; }
function fmtChecked(ts) {
  if (!ts) return 'never';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString();
}

async function loadNodes() {
  const data = await api('/api/nodes');
  const nodes = data.nodes || {};
  const names = Object.keys(nodes);
  const tbody = document.getElementById('node-tbody');
  tbody.innerHTML = '';
  if (names.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">No nodes monitored yet. Click "Add Node" to get started.</td></tr>';
  }
  let online = 0, offline = 0;
  const latencies = [];
  for (const name of names) {
    const n = nodes[name];
    if (n.status === 'online') online++;
    if (n.status === 'offline') offline++;
    if (n.latency_ms !== null && n.latency_ms !== undefined) latencies.push(n.latency_ms);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${name}</td>
      <td>${n.ip}</td>
      <td>${n.port ? 'TCP:' + n.port : 'ping'}</td>
      <td class="status-${n.status}">${(n.status || 'unknown').toUpperCase()}</td>
      <td>${n.failures || 0}/${n.failure_threshold || 2}</td>
      <td>${n.check_interval || 30}s</td>
      <td>${fmtLatency(n.latency_ms)}</td>
      <td>${fmtChecked(n.last_checked)}</td>
      <td class="row-actions">
        <button onclick="openEditModal('${name}')">Edit</button>
        <button class="danger" onclick="openDeleteModal('${name}')">Delete</button>
      </td>`;
    tbody.appendChild(tr);
  }
  document.getElementById('m-total').textContent = names.length;
  document.getElementById('m-online').textContent = online;
  document.getElementById('m-offline').textContent = offline;
  document.getElementById('m-latency').textContent = latencies.length
    ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) + ' ms' : '--';
  document.getElementById('last-refresh').textContent = 'Updated ' + new Date().toLocaleTimeString();
}

function openAddModal() {
  editingName = null;
  document.getElementById('node-modal-title').textContent = 'Add Node';
  document.getElementById('f-name').disabled = false;
  document.getElementById('f-name').value = '';
  document.getElementById('f-ip').value = '';
  document.getElementById('f-port').value = '';
  document.getElementById('f-interval').value = '30';
  document.getElementById('f-threshold').value = '2';
  document.getElementById('node-modal-err').textContent = '';
  document.getElementById('node-modal').classList.add('open');
}

async function openEditModal(name) {
  const data = await api('/api/nodes');
  const n = data.nodes[name];
  editingName = name;
  document.getElementById('node-modal-title').textContent = 'Edit Node: ' + name;
  document.getElementById('f-name').disabled = true;
  document.getElementById('f-name').value = name;
  document.getElementById('f-ip').value = n.ip;
  document.getElementById('f-port').value = n.port || '';
  document.getElementById('f-interval').value = n.check_interval || 30;
  document.getElementById('f-threshold').value = n.failure_threshold || 2;
  document.getElementById('node-modal-err').textContent = '';
  document.getElementById('node-modal').classList.add('open');
}

function closeNodeModal() { document.getElementById('node-modal').classList.remove('open'); }

async function submitNodeModal() {
  const body = {
    name: document.getElementById('f-name').value.trim(),
    ip: document.getElementById('f-ip').value.trim(),
    port: document.getElementById('f-port').value.trim(),
    interval: document.getElementById('f-interval').value.trim(),
    threshold: document.getElementById('f-threshold').value.trim(),
  };
  const errEl = document.getElementById('node-modal-err');
  try {
    if (editingName) {
      await api('/api/nodes/' + encodeURIComponent(editingName), {method: 'PUT', body: JSON.stringify(body)});
      toast(`Updated '${editingName}'.`);
    } else {
      await api('/api/nodes', {method: 'POST', body: JSON.stringify(body)});
      toast(`Added '${body.name}'.`);
    }
    closeNodeModal();
    loadNodes();
  } catch (e) {
    errEl.textContent = e.message;
  }
}

function openDeleteModal(name) {
  deleteTarget = name;
  document.getElementById('delete-modal-text').textContent =
    `Remove '${name}' from monitoring? This cannot be undone.`;
  document.getElementById('delete-modal').classList.add('open');
}
function closeDeleteModal() { document.getElementById('delete-modal').classList.remove('open'); }

async function confirmDelete() {
  try {
    await api('/api/nodes/' + encodeURIComponent(deleteTarget), {method: 'DELETE'});
    toast(`Removed '${deleteTarget}'.`);
    closeDeleteModal();
    loadNodes();
  } catch (e) {
    toast(e.message, true);
    closeDeleteModal();
  }
}

async function refreshNow() {
  try {
    await api('/api/refresh', {method: 'POST'});
    toast('Refreshed.');
    loadNodes();
  } catch (e) {
    toast(e.message, true);
  }
}

loadNodes();
setInterval(loadNodes, 10000);
</script>
</body>
</html>
"""


def _parse_optional_int(text, field_name, minimum=None):
    """Returns (value, error) - mirrors the validation the GUI dialogs do
    before calling the shared cli_* functions."""
    text = (text or "").strip()
    if text == "":
        return None, None
    if not text.lstrip("-").isdigit():
        return None, f"{field_name} must be a number."
    value = int(text)
    if minimum is not None and value < minimum:
        return None, f"{field_name} must be at least {minimum}."
    return value, None


def create_web_app(monitor_app=None):
    """Builds the Flask app. monitor_app, when given, is the running
    MonitorApp instance so /api/refresh can reuse check_nodes() (which also
    fires desktop/Discord alerts) instead of a bare re-ping."""
    app = Flask(__name__)

    @app.get("/")
    def index():
        html = PAGE_TEMPLATE.replace("__VERSION__", edi_agent.__version__)
        return Response(html, mimetype="text/html")

    @app.get("/api/nodes")
    def list_nodes():
        cfg = edi_agent.load_config()
        return jsonify({"nodes": cfg.get("nodes", {})})

    @app.get("/api/history")
    def history():
        limit = request.args.get("limit", default=20, type=int)
        events = edi_agent.load_history()
        return jsonify({"events": list(reversed(events[-limit:]))})

    @app.post("/api/nodes")
    def add_node():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        ip = (body.get("ip") or "").strip()
        if not name:
            return jsonify({"error": "Node name cannot be blank."}), 400
        if name in edi_agent.load_config()["nodes"]:
            return jsonify({"error": f"A node named '{name}' already exists."}), 400
        if not edi_agent.is_valid_ip(ip):
            return jsonify({"error": f"'{ip}' is not a valid IP address."}), 400
        port, err = _parse_optional_int(body.get("port"), "Port")
        if err:
            return jsonify({"error": err}), 400
        if port is not None and not edi_agent.is_valid_port(port):
            return jsonify({"error": "Port must be between 1 and 65535."}), 400
        interval, err = _parse_optional_int(body.get("interval"), "Check interval")
        if err:
            return jsonify({"error": err}), 400
        if interval is not None and not edi_agent.is_valid_interval(interval):
            return jsonify({"error": "Check interval must be at least 5 seconds."}), 400
        threshold, err = _parse_optional_int(body.get("threshold"), "Alert threshold")
        if err:
            return jsonify({"error": err}), 400
        if threshold is not None and not edi_agent.is_valid_threshold(threshold):
            return jsonify({"error": "Alert threshold must be at least 1."}), 400

        edi_agent.cli_add(name, ip, port=port, interval=interval, threshold=threshold)
        if monitor_app:
            monitor_app.refresh_tray_icon(edi_agent.load_config())
        return jsonify({"ok": True})

    @app.put("/api/nodes/<name>")
    def edit_node(name):
        cfg = edi_agent.load_config()
        if name not in cfg["nodes"]:
            return jsonify({"error": f"Node '{name}' not found."}), 404
        body = request.get_json(silent=True) or {}
        ip = (body.get("ip") or "").strip()
        if not edi_agent.is_valid_ip(ip):
            return jsonify({"error": f"'{ip}' is not a valid IP address."}), 400
        port_text = (body.get("port") or "").strip()
        clear_port = port_text == ""
        port, err = _parse_optional_int(body.get("port"), "Port")
        if err:
            return jsonify({"error": err}), 400
        if port is not None and not edi_agent.is_valid_port(port):
            return jsonify({"error": "Port must be between 1 and 65535."}), 400
        interval, err = _parse_optional_int(body.get("interval"), "Check interval")
        if err:
            return jsonify({"error": err}), 400
        if interval is not None and not edi_agent.is_valid_interval(interval):
            return jsonify({"error": "Check interval must be at least 5 seconds."}), 400
        threshold, err = _parse_optional_int(body.get("threshold"), "Alert threshold")
        if err:
            return jsonify({"error": err}), 400
        if threshold is not None and not edi_agent.is_valid_threshold(threshold):
            return jsonify({"error": "Alert threshold must be at least 1."}), 400

        edi_agent.cli_edit(
            name, ip=ip, port=port, clear_port=clear_port,
            interval=interval, threshold=threshold,
        )
        if monitor_app:
            monitor_app.refresh_tray_icon(edi_agent.load_config())
        return jsonify({"ok": True})

    @app.delete("/api/nodes/<name>")
    def delete_node(name):
        if not edi_agent.cli_remove(name):
            return jsonify({"error": f"Node '{name}' not found."}), 404
        if monitor_app:
            monitor_app.refresh_tray_icon(edi_agent.load_config())
        return jsonify({"ok": True})

    @app.post("/api/refresh")
    def refresh():
        if monitor_app:
            monitor_app.check_nodes(force=True)
        else:
            cfg = edi_agent.load_config()
            results = edi_agent.ping_nodes_concurrently(cfg["nodes"])
            now = time.time()
            for name, info in cfg["nodes"].items():
                is_online, latency_ms = results.get(name, (False, None))
                info["status"] = "online" if is_online else "offline"
                info["last_checked"] = now
                info["latency_ms"] = latency_ms
            edi_agent.save_config(cfg)
        return jsonify({"ok": True})

    return app


def run_web_server(host="127.0.0.1", port=DEFAULT_WEB_PORT, monitor_app=None):
    """Blocking call - run on a background thread from the tray daemon, or
    directly for the standalone `edi-agent web` CLI command."""
    from waitress import serve
    app = create_web_app(monitor_app=monitor_app)
    serve(app, host=host, port=port, _quiet=True)
