# CLAUDE.md

Working memory for this project: what's shipped, what's in flight, what's
next, and a running checklist of changes. Update this file as part of any
non-trivial request — see **Changelog Checklist** at the bottom for the
per-request format.

## What this project is

**EDI Agent** — a lightweight LAN node monitoring daemon and PySide6 system
tray application for Fedora KDE Plasma. Checks local infrastructure nodes
(Proxmox, Plex, databases, etc.) via ICMP ping or TCP port connect, and
raises desktop notifications on status change. Full CLI (`edi-agent`) plus
a tray-docked GUI Dashboard, both backed by the same functions.

Core files: `edi_agent.py` (daemon, CLI, GUI, `main()` entry point),
`manual.py` (interactive help window), `style.py` (dark/light Qt
stylesheets), `pyproject.toml` (packaging), `install.sh` / `uninstall.sh`,
`tests/` (pytest suite), `man/` (man pages), `.github/workflows/tests.yml`
(CI).

## Local testing environment

- **pytest, offscreen Qt** (`QT_QPA_PLATFORM=offscreen`) — the default for
  everything: CLI logic, config/history persistence, GUI dialogs and
  widgets. No container needed for this; it's fast and already isolated
  from the real `~/.config/edi-alert-agent/` via `conftest.py`.
- **`podman` is installed on this host** (rootless, daemonless, Fedora's
  native container tool — confirmed working 2026-08-11, pulls
  `registry.fedoraproject.org/fedora:latest` fine). Available for the one
  thing pytest can't safely cover: running `install.sh`/`uninstall.sh` for
  real inside a disposable Fedora container, without touching the host's
  actual venv or live systemd user service. Not yet wired into a
  Containerfile/script — do that first if a session actually needs it,
  rather than assuming the plumbing exists.
- What a container **won't** help with: the system tray icon, DBus
  desktop notifications, and KDE Plasma-specific rendering all need a
  real desktop session (X11/Wayland + DBus session bus + a running
  StatusNotifier host) that a bare container doesn't have without
  nontrivial forwarding setup. That kind of testing still has to happen
  on the real host, as it has all along.

## Status: shipped (v1.0.0 → v1.7.0)

- **v1.0.1** — concurrent pinging (fixed UI-freezing sequential loop), IP
  validation, duplicate-node protection, `nodes.json` file locking,
  centralized `__version__`
- **v1.0.2** — failure counts in `list`/GUI, sortable status table,
  `uninstall.sh`
- **v1.0.3** — tray icon health badge (green/red, drawn at runtime)
- **v1.0.4** — ping latency + last-checked timestamp per node
- **v1.1.0** — optional TCP port health checks (`--port`), so a node can be
  monitored by an actual service handshake instead of just ICMP
- (unreleased commit) — pytest suite introduced, 24 tests, isolated from
  the real `nodes.json`/`history.json` via an autouse `conftest.py` fixture
- **v1.2.0** — `edi-agent edit` — update a node's IP/port in place
- **v1.3.0** — GUI edit dialog (double-click a row / "Edit Selected")
- **v1.4.0** — alert history (`edi-agent history`, GUI History dialog,
  `~/.config/edi-alert-agent/history.json`, capped at 200 events)
- **v1.5.0** — per-node `--interval` / `--threshold` overrides
- **v1.6.0** — GUI Dashboard redesign (metric summary cards, dark-glass
  theme) finished and shipped; full GUI CRUD (Add/Edit/Delete node
  buttons, all backed by the same validated CLI functions); fixed the "?"
  help button rendering blank, table header truncation, and a
  Windows/Mac-only font-family fallback; added `man/edi-agent.1` and this
  file
- **v1.7.0** — closed out every item that was in the "Known gaps" section
  below: CLI exit codes, a truly adaptive check scheduler (see below),
  a rotating log file, dark/light theme toggle, `pyproject.toml` packaging
  with a real `edi-agent` entry point, man page installed by `install.sh`,
  and a GitHub Actions CI workflow. Details in this version's Changelog
  Checklist entry.

## How the adaptive scheduler works (v1.7.0)

The daemon no longer polls on a fixed 30s `QTimer`. `check_nodes()` ends by
calling `schedule_next_check()`, which looks at every node's own
`check_interval` and `last_checked`, and re-arms a single-shot timer
(`self.next_check_timer`) for however long until the *soonest* node is
next due (floor 1s). This means `--interval 5` now genuinely checks a node
every 5 seconds instead of being silently rounded up to the old fixed tick.
Manual "Refresh Now" clicks call `check_nodes(force=True)`, which still
re-arms the same timer afterward rather than spawning a second parallel
schedule — important: don't reintroduce `QTimer.singleShot()` for this,
it would create exactly that bug (verified and fixed once already).

## Known gaps / rough edges

None currently tracked as open. If you find one, add it here rather than
just fixing it silently, so the next session has the context — even if
you also fix it in the same sitting, the entry plus its resolution in the
changelog is the record of what happened and why it mattered.

## Roadmap / ideas

Not prioritized — pull from here when picking the next task.

- [ ] Search/filter box in the Dashboard table (matters once fleets grow
      past a screenful)
- [ ] Per-node latency history / sparkline trend (small, last-N-checks
      graph) in the GUI — `latency_ms` isn't persisted over time yet,
      only the latest value
- [ ] Node grouping/tagging (e.g. "core", "media", "iot") with filtering
- [ ] Export/import the node registry (backup/restore, or share a starter
      config across machines)
- [ ] Per-node notification urgency / sound customization
- [ ] Config schema version field in `nodes.json`, with a migration path,
      now that the schema has grown organically across 7 minor versions
- [ ] "Follow system theme" option, if PySide6's `styleHints().colorScheme()`
      proves reliable enough across desktop environments — skipped for now
      in favor of a manual tray-menu toggle, which is simpler and doesn't
      depend on platform theme-detection quirks
- [ ] PyPI publishing / Fedora COPR or RPM packaging (the `pyproject.toml`
      groundwork is in place; see `man/edi-agent-packaging.7`) — needs
      the project owner's own PyPI/COPR credentials, not something to set
      up unilaterally
- [ ] Consider a read-only local web status page (Flask/FastAPI) for
      checking fleet health from a phone on the same LAN — bigger lift,
      only worth it if remote visibility becomes a real want
- [ ] `edi-agent list`/`history` could gain `--json` output for scripting,
      now that exit codes make the CLI more script-friendly generally

## Documentation map

- `README.md` — install, CLI reference, GUI overview, config file format,
  packaging, diagnostics
- `man/edi-agent.1` — man page for every CLI command (`man man/edi-agent.1`
  after install, or `man -l man/edi-agent.1` from the repo)
- `man/edi-agent-packaging.7` — how `pyproject.toml`/entry points/editable
  installs work here, written as a general packaging reference too
- `manual.py` — in-app interactive help window (`edi-agent help`)
- This file — status, roadmap, and change log

## Changelog Checklist

Append an entry here at the end of any session that changes code,
docs, or tests — check off what actually happened so this file stays a
reliable record. Newest entry on top. Keep entries short: what changed,
not why (the "why" belongs in this file's other sections if it's still
relevant, or is just obvious from the diff).

### 2026-08-11 (2) — Documented available local testing environment

- [x] Confirmed — `podman` already installed and working on this host
      (rootless, pulled/ran a Fedora container successfully); no need to
      install Docker separately
- [x] Added — "Local testing environment" section above, documenting
      podman's availability for `install.sh`/`uninstall.sh` testing and
      its limits (no tray/DBus/desktop testing in a bare container)
- Not done — no Containerfile or test script exists yet; this session
  only confirmed and documented capability, didn't build the harness

### 2026-08-11 — Closed out all "known gaps": exit codes, scheduler, logging, theme, packaging, CI

- [x] Added — `sys.exit(1)` on CLI validation/operation failures; `cli_add`/
      `cli_remove`/`cli_edit` now return `True`/`False` and `main()` acts on it
- [x] Fixed — check scheduler now adaptive (see section above) instead of a
      fixed 30s tick, so `--interval` below 30s is genuinely honored
- [x] Added — rotating log file (`~/.local/state/edi-alert-agent/edi-agent.log`,
      1MB × 3 backups) via `get_logger()`, test-isolated through `LOG_PATH`
      monkeypatching same as config/history
- [x] Added — previously-silent `except Exception` in `load_config`/
      `load_history` now log a warning instead of failing silently
- [x] Added — light theme (`LIGHT_GLASS_STYLE` in `style.py`) + tray-menu
      toggle; persisted to `~/.config/edi-alert-agent/settings.json`;
      defaults to dark
- [x] Added — `pyproject.toml` (setuptools, `py-modules`, dynamic version
      from `edi_agent.__version__`, `edi-agent = edi_agent:main` entry
      point); verified `pip install -e .` end-to-end in an isolated venv
- [x] Added — `edi_agent.py` gained a real `main()` function (previously
      all under `if __name__ == "__main__":`), required for the entry point
- [x] Updated — `install.sh` now does `pip install -e .` + symlinks the
      generated entry-point script, instead of hand-writing a bash wrapper;
      also installs the man page to `~/.local/share/man/man1/`
- [x] Updated — `uninstall.sh` removes the man page and offers to remove
      the log directory, mirroring the existing config-removal prompt
- [x] Added — `man/edi-agent-packaging.7`, explaining the packaging setup
      as a general worked example, per request
- [x] Added — `.github/workflows/tests.yml` — pytest on push/PR, Python
      3.11 and 3.12, headless Qt deps installed via apt
- [x] Added — 17 new tests (89 total): exit codes, logging, settings/theme
      round-trip, adaptive-scheduler timer math
- [x] Updated — README (Diagnostics, Development & Testing, new "Installing
      as a Package" section, Documentation), `man/edi-agent.1` (FILES,
      EXIT STATUS, interval wording), `manual.py` (theme toggle)
- Not run live: `install.sh`/`uninstall.sh` were validated by testing
  `pip install -e .` and the entry point in an isolated scratch venv, not
  by executing the scripts against the real project directory — they
  recreate the venv and touch the live systemd service, which needs the
  user to trigger deliberately

### 2026-07-26 — GUI dashboard fixes + CRUD, docs, CLAUDE.md
- [x] Added — man page (`man/edi-agent.1`)
- [x] Added — `CLAUDE.md` (this file)
- [x] Added — GUI "Add Node" dialog + button
- [x] Added — GUI "Delete Selected" button + confirmation
- [x] Added — 9 new tests for Add/Delete GUI flows (72 total)
- [x] Fixed — "?" help button rendering blank (padding/width conflict)
- [x] Fixed — table header text truncation ("LAST CHECKED" → "AST CHECKE")
- [x] Fixed — metric card font-family fallback (Segoe UI → Linux fonts)
- [x] Updated — metric cards given colored left-accent bars for a more
      unified look
- [x] Updated — Dashboard action bar button labels shortened (Add/Edit/
      Delete/History/Refresh Now) with tooltips, to fit the wider button
      row
- [x] Shipped as v1.6.0 (this entry originally listed pending items that
      were completed and tagged in the same session)
