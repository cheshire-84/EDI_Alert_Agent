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
a tray-docked GUI dashboard.

Core files: `edi_agent.py` (daemon, CLI, GUI), `manual.py` (interactive
help window), `style.py` (Qt dark-glass stylesheet), `install.sh` /
`uninstall.sh`, `tests/` (pytest suite), `man/edi-agent.1` (man page).

## Status: shipped (v1.0.0 → v1.5.0)

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
- **v1.5.0** — per-node `--interval` / `--threshold` overrides; daemon tick
  became due-based instead of checking every node every 30s

## Status: in progress (this session, not yet tagged)

Picking up an uncommitted local rewrite of the GUI into an "Infrastructure
Dashboard" style (metric summary cards + `style.py` glass theme) and
finishing it out:

- [x] Fixed: "?" help button rendering as a blank square — global
      `QPushButton { padding: 8px 16px }` was consuming the entire 32px
      fixed-width button, leaving no room to draw the glyph. Gave it a
      dedicated `#IconButton` style with zero padding and a 32×32 fixed
      size.
- [x] Fixed: "LAST CHECKED" (and other) column headers truncating
      (rendered as "AST CHECKE") — table used uniform `Stretch` across all
      8 columns regardless of header text width. Switched to `Stretch` for
      Node Name/IP only, `ResizeToContents` for the rest, and widened the
      dialog.
- [x] Fixed: metric cards had a boxy/misaligned look, partly from a
      `font-family` list (`"Segoe UI", -apple-system, ...`) that doesn't
      resolve on Fedora — replaced with a Linux-appropriate fallback chain
      (Inter → Noto Sans → Cantarell → DejaVu Sans) and gave cards a
      colored left-accent bar instead of only coloring the number, for a
      more unified look.
- [x] Added: GUI "Add Node" dialog + button (name/IP/port/interval/
      threshold, full validation, duplicate-name check)
- [x] Added: GUI "Delete Selected" button with a confirm dialog
- [x] GUI can now fully do add/edit/delete — previously add/delete were
      CLI-only despite the GUI existing since v1.0.0
- [x] Tests for all of the above (72 total, up from 63)
- [ ] Ship as a version bump, update README, commit `style.py` (currently
      untracked but required by `edi_agent.py`)

## Known gaps / rough edges (not yet fixed)

- **CLI exit codes**: validation failures (`cli_add`, `cli_edit`, etc.)
  print `[!] ...` and return, but the process still exits 0. Anything
  scripting around `edi-agent` can't detect failure without parsing
  stdout. Should raise `sys.exit(1)` on failure paths in `__main__`.
- **30s minimum interval granularity**: `--interval` is honored via a
  due-check against `last_checked`, but the daemon's own tick is a fixed
  30s `QTimer`. An interval of 5s will still only actually run every 30s.
  Documented in code/man page but worth a real fix (variable tick, or at
  least a warning when `--interval` < the daemon's own tick rate).
- **No packaging**: install is a hand-rolled `venv` + bash wrapper +
  systemd unit via `install.sh`. No `pyproject.toml`, no PyPI/COPR/Flatpak
  packaging.
- **Man page not installed by `install.sh`**: `man/edi-agent.1` exists but
  nothing copies it into `MANPATH` on install.
- **No CI**: tests exist (pytest, 72 and counting) but nothing runs them
  automatically on push/PR.
- **No log file**: relies entirely on `journalctl --user -u
  edi-alert-agent.service` for diagnosis; no rotating app-level log.
- **Theme is hardcoded dark**: `style.py`'s `DARK_GLASS_STYLE` is applied
  unconditionally; no light-theme or "follow system theme" option.

## Roadmap / ideas

Carried over + new ideas for future sessions. Not prioritized — pull from
here when picking the next task.

- [ ] Fix CLI exit codes (see above) — cheap, high-value correctness fix
- [ ] `install.sh`/`uninstall.sh`: install/remove the man page
- [ ] GitHub Actions workflow: run `pytest` on push and PR
- [ ] Search/filter box in the Dashboard table (matters once fleets grow
      past a screenful)
- [ ] Per-node latency history / sparkline trend (small, last-N-checks
      graph) in the GUI — the data (`latency_ms` per check) isn't
      persisted over time yet, only the latest value
- [ ] Node grouping/tagging (e.g. "core", "media", "iot") with filtering
- [ ] Export/import the node registry (backup/restore, or share a starter
      config across machines)
- [ ] Per-node notification urgency / sound customization
- [ ] Config schema version field in `nodes.json`, with a migration path,
      now that the schema has grown organically across 5 minor versions
- [ ] Optional light theme / follow-system-theme toggle
- [ ] `pyproject.toml` packaging with proper console-script entry points,
      replacing the hand-rolled `~/.local/bin/edi-agent` wrapper
- [ ] Rotating log file under `~/.local/state/edi-alert-agent/` for
      history beyond what `journalctl` retains
- [ ] Consider a read-only local web status page (Flask/FastAPI) for
      checking fleet health from a phone on the same LAN — bigger lift,
      only worth it if remote visibility becomes a real want

## Documentation map

- `README.md` — install, CLI reference, GUI overview, config file format
- `man/edi-agent.1` — man page (`man ./man/edi-agent.1` or `man -l
  man/edi-agent.1`); not yet installed by `install.sh` (see gaps above)
- `manual.py` — in-app interactive help window (`edi-agent help`)
- This file — status, roadmap, and change log

## Changelog Checklist

Append an entry here at the end of any session that changes code,
docs, or tests — check off what actually happened so this file stays a
reliable record. Newest entry on top. Keep entries short: what changed,
not why (the "why" belongs in this file's other sections if it's still
relevant, or is just obvious from the diff).

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
- [ ] Pending — commit `style.py` (untracked, required by `edi_agent.py`)
- [ ] Pending — version bump + README update for this batch
