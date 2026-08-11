# Frequently Asked Questions

These are the questions that keep coming up from people trying 8-Bit Agent
(formerly EDI Agent) on their own setups. Answered here directly rather than
left unaddressed in an issue thread somewhere.

## What is 8-Bit Agent, actually?

A **personal, per-machine** LAN monitor. You install it on a machine, you
tell it which of *your* infrastructure to watch (Proxmox box, Plex server,
a database, whatever), and it tells *you* — on that machine — when something
goes down or comes back. There's no central server, no shared account, no
"fleet" concept. If your partner wants to monitor their own projects, they
install their own copy on their own machine with their own node list. That's
the whole design, and it's deliberate — it's what makes this a lightweight
personal tool instead of a monitoring platform to operate and secure.

Everything below is in service of that goal, not a departure from it.

## Does the system tray work on GNOME (e.g. Ubuntu 24.04)?

Mostly, with one caveat: stock GNOME removed the tray/StatusNotifier area
entirely a few years back. KDE Plasma (this project's primary target) still
has it built in. On GNOME you'll need the
[AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/)
extension (or an equivalent) installed first — after that, the tray icon,
health badge, and menu all work the same way they do on KDE, since it's the
same Qt/PySide6 `QSystemTrayIcon` API underneath. This isn't called out
loudly enough in the README today; if you're on GNOME, install the extension
first and things should just work.

Other Linux desktops with a working StatusNotifier host (XFCE, Cinnamon,
etc.) should work out of the box, same as KDE.

## Does this work on Windows?

Not yet — today it's Linux-only. But **it does not need a rewrite** to get
there, and this is worth being specific about, because "not supported yet"
can sound bigger than it is. The app is already built on PySide6 (Qt6),
which has native cross-platform tray and window APIs. The actual
Linux-specific code is narrow:

- The `ping` command's flags (`-c`/`-W` on Linux, `-n`/`-w` on Windows)
- `notify-send` for desktop popups (Linux-only; Windows needs a different
  notification API, which Qt itself can provide)
- The systemd user service (Linux-only; Windows would use Task Scheduler,
  macOS would use launchd)

Everything else — the CLI, the config format, the Dashboard, the check
scheduler, Discord webhooks, and now the web dashboard — is already
platform-agnostic Python. Cross-platform desktop support is explicitly on
the roadmap (see `CLAUDE.md`), scheduled after the current web UI work,
specifically *because* it's a scoped, bounded task rather than an unknown
one.

## Should this have been written in .NET / some other stack instead?

No — a different language wouldn't have avoided the platform-specific glue
code above; every cross-platform tray-notifier project has some version of
"the ping command is different per OS" and "the notification API is
different per OS," regardless of what it's written in. Python + PySide6
already gives cross-platform GUI/tray primitives for free; the porting work
that remains is inherent to the problem, not a consequence of the language
choice.

## Do you have a Docker version with a web UI? Is one coming?

The **local web dashboard** (v1.9.0, bound to `127.0.0.1` only — see the
README) is a step toward this. It runs two ways:

- Automatically, alongside the tray daemon (`edi-agent gui`) — the normal
  desktop use case.
- Standalone, with no tray/desktop session at all: `edi-agent web`.

That second form is what makes a headless container a coherent idea for the
first time — previously the whole app assumed a real desktop session
(X11/Wayland + DBus + a StatusNotifier host), which a bare container simply
doesn't have. There's no official Containerfile yet, but `edi-agent web` is
the missing piece that was blocking it. If you want to run it in a
container today: install the package, skip the tray/systemd steps entirely,
and run `edi-agent web` as the container's entrypoint — you lose live
desktop pop-ups (no desktop session in a container), which is exactly what
Discord webhook alerts (`edi-agent webhook set <url>`) are for.

Note this only ever monitors from wherever the container runs — it's still
one node list per install, same as the desktop app. A "monitor everything
from one dashboard" mode is a different, bigger feature this project isn't
trying to become.

## Is the web dashboard exposed to my network?

No. It's hardcoded to bind `127.0.0.1` (loopback) only — there's no setting
to change that. If you want to check it from your phone or another machine,
put an SSH tunnel or your own reverse proxy in front of it; the app itself
will never make that decision on your behalf. This matches the project's
core premise (see the first question above): install it, it runs *there*,
for *you*.
