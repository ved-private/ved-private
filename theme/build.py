#!/usr/bin/env python3
"""Profile theme builder.

Reads  theme/default.json  (the look you own)  and  theme/state.json  (a visitor's
temporary colour), then writes every SVG in assets/ and the README.md.

Run locally:        python3 theme/build.py
Used by the Action: .github/workflows/theme.yml  (issue / dispatch / schedule / push)
"""
import colorsys
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
THEME = ROOT / "theme"
SRC = THEME / "src"
ASSETS = ROOT / "assets"
MSG_FILE = pathlib.Path(os.environ.get("THEME_MSG_FILE", "/tmp/theme_msg.txt"))

# The source SVGs were drawn in this red. Every other colour is derived from it.
BASE_ACCENT = "ff1e3c"
BG_ROLE_MAX_L = 0.12          # near-black reds count as "background"
TEXT_MAIN = "f3dde0"          # main light text colour in the sources
TEXT_MUTED = {"b3949a": 0.45, "7d5d63": 0.70}   # how much background is mixed into muted text
STATIC = ["hero", "divider", "motto", "stack", "footer"]
SECTIONS = [("about", "ABOUT"), ("stack", "STACK"), ("theme", "THEME"), ("connect", "CONNECT")]
COOLDOWN_SECONDS = 90         # between two visitor changes
HEX_RE = re.compile(r"(?<!url\()#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

SWATCH_BODY = ("Press Submit new issue, nothing else to change. The profile recolours itself in "
               "about a minute (refresh the page), then goes back to default on its own.")
CUSTOM_BODY = ("Change the title to: theme: #RRGGBB   (example: theme: #00c2a8)\n"
               "Then press Submit new issue. Only the six-digit hex colour is read.")


# ---------------------------------------------------------------- colour maths
def norm(h):
    h = str(h).strip().lstrip("#").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-f]{6}", h):
        raise ValueError(f"not a hex colour: {h!r}")
    return h


def hls(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def to_hex(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, min(1, max(0, l)), min(1, max(0, s)))
    return "%02x%02x%02x" % tuple(round(v * 255) for v in (r, g, b))


def mix(a, b, share_b):
    ra = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    rb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "%02x%02x%02x" % tuple(round(x * (1 - share_b) + y * share_b) for x, y in zip(ra, rb))


class Theme:
    """accent = required. bg / text = optional overrides (None = follow the accent)."""

    def __init__(self, accent, bg=None, text=None):
        self.accent = norm(accent)
        self.bg = norm(bg) if bg else None
        self.text = norm(text) if text else None
        base_h, _base_l, base_s = hls(BASE_ACCENT)
        th, _tl, ts = hls(self.accent)
        self.dh = th - base_h          # hue turn
        self.ratio = ts / base_s       # saturation ratio (accent brightness is kept on purpose)
        self.identity = self.accent == BASE_ACCENT

    @property
    def tag(self):
        key = f"{self.accent}|{self.bg}|{self.text}".encode()
        return hashlib.sha1(key).hexdigest()[:6]

    def _bg_reference(self):
        return self.bg or self.color("0a0204")

    def color(self, h):
        h = norm(h)
        hue, l, s = hls(h)
        if s < 0.08:                                   # white / greys stay as they are
            return h
        if self.text and h == TEXT_MAIN:
            return self.text
        if self.text and h in TEXT_MUTED:
            return mix(self.text, self._bg_reference(), TEXT_MUTED[h])
        if self.bg and l <= BG_ROLE_MAX_L:
            bh, bl, bs = hls(self.bg)
            return to_hex(bh, min(l + (bl - 0.0196), 0.22), bs)
        if self.identity:
            return h
        return to_hex(hue + self.dh, l, s * self.ratio)

    def svg(self, text):
        def sub(m):
            new = self.color(m.group(0))
            return m.group(0) if new == norm(m.group(0)) else "#" + new
        return HEX_RE.sub(sub, text)

    def readme_colors(self, text):
        return re.sub(r"\{\{c:([0-9a-fA-F]{6})\}\}", lambda m: self.color(m.group(1)), text)


# ---------------------------------------------------------------- small helpers
def load(path, fallback=None):
    p = pathlib.Path(path)
    if not p.exists():
        return fallback
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    pathlib.Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_if_changed(path, text):
    p = pathlib.Path(path)
    if not p.exists() or p.read_text(encoding="utf-8") != text:
        p.write_text(text, encoding="utf-8")


def parse_request(title, presets):
    """'theme: ocean' | 'theme: #00c2a8' | 'theme: reset'  ->  ('set', hex, name) | ('reset',) | None"""
    title = (title or "").strip()[:40]
    m = re.fullmatch(r"theme:\s*(.+)", title, re.I)
    if not m:
        return None
    v = m.group(1).strip().lower()
    if v in ("reset", "default"):
        return ("reset",)
    if v in presets:
        return ("set", norm(presets[v]), v)
    m = re.fullmatch(r"#?([0-9a-f]{6})", v)
    if m:
        return ("set", m.group(1), "#" + m.group(1))
    return None


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse_time(s):
    try:
        return dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- svg pieces
def swatch_svg(color, on):
    ring = f'<circle cx="28" cy="28" r="24" fill="none" stroke="#{color}" stroke-width="3"/>' if on else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56" width="56" height="56">'
            f'{ring}<circle cx="28" cy="28" r="17" fill="#{color}" stroke="#f3dde0" stroke-opacity=".6" '
            f'stroke-width="2"/></svg>\n')


def custom_swatch_svg(on):
    ring = ('<circle cx="28" cy="28" r="24" fill="none" stroke="#f3dde0" stroke-width="3"/>' if on else "")
    stops = "".join(f'<stop offset="{i * 20}%" stop-color="{c}"/>' for i, c in
                    enumerate(["#ff1e3c", "#ffc21a", "#14c27a", "#1e90ff", "#8b5cf6", "#d946ef"]))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56" width="56" height="56">'
            f'<defs><linearGradient id="w" x1="0" y1="0" x2="1" y2="1">{stops}</linearGradient></defs>{ring}'
            '<circle cx="28" cy="28" r="17" fill="url(#w)" stroke="#f3dde0" stroke-opacity=".6" stroke-width="2"/>'
            '<path d="M28 21v14M21 28h14" stroke="#0a0204" stroke-opacity=".55" stroke-width="6" stroke-linecap="round"/>'
            '<path d="M28 21v14M21 28h14" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round"/></svg>\n')


def reset_swatch_svg():
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56" width="56" height="56">'
            '<circle cx="28" cy="28" r="17" fill="#0a0204" stroke="#f3dde0" stroke-opacity=".6" stroke-width="2"/>'
            '<path d="M35.5 24.5A9 9 0 1 0 37 30" fill="none" stroke="#f3dde0" stroke-width="3" stroke-linecap="round"/>'
            '<path d="M36.5 17.5v8h-8z" fill="#f3dde0"/></svg>\n')


def issue_url(repo, title, body):
    return f"https://github.com/{repo}/issues/new?title={quote(title)}&body={quote(body)}"


# ---------------------------------------------------------------- render
def render(theme, repo, default, presets, active_name):
    ASSETS.mkdir(exist_ok=True)
    tag = theme.tag
    keep = set()

    def emit(name, text):
        keep.add(name)
        write_if_changed(ASSETS / name, text)

    for n in STATIC:
        emit(f"{n}-{tag}.svg", theme.svg((SRC / f"{n}.svg").read_text(encoding="utf-8")))

    heading = (SRC / "heading.svg").read_text(encoding="utf-8")
    total = f"{len(SECTIONS):02d}"
    for i, (key, title) in enumerate(SECTIONS, 1):
        svg = heading.replace("{{TITLE}}", title).replace("{{N}}", f"{i:02d}").replace("{{TOTAL}}", total)
        emit(f"h-{key}-{tag}.svg", theme.svg(svg))

    emit(f"about-card-{tag}.svg", theme.svg((SRC / "about-card.svg").read_text(encoding="utf-8")))

    # swatches never change with the theme, so their names carry no tag
    links = []
    for name, hexv in presets.items():
        for state in ("on", "off"):
            emit(f"sw-{name}-{state}.svg", swatch_svg(norm(hexv), state == "on"))
        on = "on" if name == active_name else "off"
        links.append(f'<a href="{issue_url(repo, "theme: " + name, SWATCH_BODY)}">'
                     f'<img src="assets/sw-{name}-{on}.svg" width="46" alt="{name}" title="{name}"/></a>')
    custom_on = bool(active_name) and active_name.startswith("#")
    emit("sw-custom-on.svg", custom_swatch_svg(True))
    emit("sw-custom-off.svg", custom_swatch_svg(False))
    emit("sw-reset.svg", reset_swatch_svg())
    links.append(f'<a href="{issue_url(repo, "theme: #", CUSTOM_BODY)}"><img src="assets/sw-custom-'
                 f'{"on" if custom_on else "off"}.svg" width="46" alt="your own colour" title="your own colour"/></a>')
    links.append(f'<a href="{issue_url(repo, "theme: reset", SWATCH_BODY)}"><img src="assets/sw-reset.svg" '
                 f'width="46" alt="reset" title="back to default"/></a>')

    # drop assets from earlier themes
    for p in ASSETS.glob("*.svg"):
        if p.name not in keep:
            p.unlink()

    tpl = (THEME / "README.template.md").read_text(encoding="utf-8")
    shown = active_name or default["name"]
    readme = (tpl.replace("{{tag}}", tag)
                 .replace("{{swatches}}", "\n".join(links))
                 .replace("{{showing}}", shown)
                 .replace("{{default}}", default["name"])
                 .replace("{{hours}}", str(default.get("reset_after_hours", 12))))
    write_if_changed(ROOT / "README.md", theme.readme_colors(readme))


# ---------------------------------------------------------------- main
def main():
    event = os.environ.get("EVENT", "local")
    default = load(THEME / "default.json")
    presets = load(THEME / "presets.json")
    state = load(THEME / "state.json", {"accent": None, "name": None, "changed_at": None})
    repo = os.environ.get("GITHUB_REPOSITORY") or default["repo"]
    hours = float(default.get("reset_after_hours", 12))
    msg = None
    request = None

    if event == "issues":
        request = os.environ.get("ISSUE_TITLE", "")
    elif event == "workflow_dispatch":
        v = os.environ.get("INPUT_COLOUR", "").strip()
        request = f"theme: {v}" if v else None
    elif event == "schedule" and state.get("accent"):
        changed = parse_time(state.get("changed_at"))
        if changed is None or (now() - changed).total_seconds() > hours * 3600:
            state = {"accent": None, "name": None, "changed_at": None}

    if request is not None:
        res = parse_request(request, presets)
        names = ", ".join(presets)
        if res is None:
            msg = ("Could not read that title. Use `theme: <preset>`, `theme: #RRGGBB` or `theme: reset`.\n"
                   f"Presets: {names}.")
            if event != "issues":
                MSG_FILE.write_text(msg, encoding="utf-8")
                sys.exit(msg)
        else:
            changed = parse_time(state.get("changed_at"))
            wait = COOLDOWN_SECONDS - (now() - changed).total_seconds() if changed else 0
            if event == "issues" and res[0] == "set" and state.get("accent") and wait > 0:
                msg = f"Someone changed the colour a moment ago. Try again in about {int(wait) + 1} seconds."
            elif res[0] == "reset":
                state = {"accent": None, "name": None, "changed_at": None}
                msg = f"Back to the default look ({default['name']})."
            else:
                state = {"accent": res[1], "name": res[2], "changed_at": now().isoformat(timespec="seconds")}
                msg = (f"Done, the colour is now **{res[2]}**. Refresh the profile in about a minute. "
                       f"It returns to {default['name']} by itself after {hours:g} hours.")

    accent = state.get("accent") or default["accent"]
    theme = Theme(accent, default.get("bg"), default.get("text"))
    active = state.get("name") if state.get("accent") else default["name"]
    save(THEME / "state.json", state)
    render(theme, repo, default, presets, active)
    MSG_FILE.write_text(msg or "Nothing to change.", encoding="utf-8")
    print(f"theme built: accent #{theme.accent}, showing {active}, tag {theme.tag}")


if __name__ == "__main__":
    main()
