"""Render collected facts + authored judgment into one static page.

The design lives entirely in templates/page.css. This module emits semantic
HTML and never inlines a style, so a design pass can iterate on the stylesheet
without touching Python.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

TONES = {"warn", "green", "hitl", "grey", "blaze"}


def e(text):
    return html.escape(str(text if text is not None else ""), quote=True)


def rich(text):
    """Escape, then re-admit a deliberately tiny inline vocabulary.

    Judgment files are written by hand and by the skill, and both want to mark a
    few words as emphasised or as code. Everything else stays escaped, so a
    ticket title carrying a stray angle bracket cannot reach the page as markup.
    """
    out = e(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r'<code class="mono">\1</code>', out)
    return out


def _days_since(iso):
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - then).days


def _fmt_date(iso):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%-d %b")
    except ValueError:
        return iso[:10]


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------


def masthead(state, judgment):
    m = state["map"]
    step = judgment.get("step_label", "")
    bits = [f'MAP <a href="{e(m["url"])}">#{m["number"]}</a>']
    if step:
        bits.append(e(step))
    bits.append(f'AS OF {datetime.now().strftime("%-d %b %Y").upper()}')
    return f"""<header class="masthead">
  <h1>Trailhead<span class="sep">/</span>{e(state["repo"].split("/")[-1])}</h1>
  <span class="meta mono">{" · ".join(bits)}</span>
</header>"""


def staleness(state, judgment):
    """Say plainly when the authored half has fallen behind the collected half."""
    reviewed = judgment.get("reviewed_at")
    if not reviewed:
        return ""
    age = _days_since(reviewed if "T" in reviewed else reviewed + "T00:00:00+00:00")
    if age is None or age < 7:
        return ""
    return f"""<div class="stale-banner" role="status">
  <strong>The judgment half is {age} days old.</strong>
  The facts below refreshed just now, but the four answers and the ranked actions
  were last reviewed {e(reviewed)}. Run <code class="mono">/trailhead review</code> before trusting them.
</div>"""


def _answer(question, body, cls=""):
    return (
        f'<div class="answer{cls}"><span class="q">{e(question)}</span>'
        f'<p class="a">{rich(body)}</p></div>'
    )


def answers(judgment):
    """The four questions, in priority order — DOM order is reading order.

    "What's next" leads and takes the blaze; the other three are orientation
    and sit underneath. Ordering here rather than with CSS `order` keeps the
    tab and screen-reader sequence honest.
    """
    a = judgment.get("answers") or {}
    if not a:
        return ""

    parts = []
    if a.get("next"):
        parts.append(_answer("What's next?", a["next"], " next"))

    orient = [
        ("Where did we leave off?", a.get("left_off")),
        ("Where are we going?", a.get("going")),
        ("What is this?", a.get("what")),
    ]
    cards = [_answer(q, body) for q, body in orient if body]
    if cards:
        parts.append(f'<div class="orientation">{"".join(cards)}</div>')

    if not parts:
        return ""
    return f'<div class="answers">{"".join(parts)}</div>'


def actions(judgment):
    acts = judgment.get("actions") or []
    if not acts:
        return ""
    rows = []
    for i, act in enumerate(acts[:5], start=1):
        cmd = (
            f'<span class="cmd mono">{e(act["cmd"])}</span>' if act.get("cmd") else ""
        )
        cost = f'<span class="cost mono">{e(act["cost"])}</span>' if act.get("cost") else ""
        detail = f'<p class="d">{rich(act["d"])}</p>' if act.get("d") else ""
        rows.append(
            f'<div class="act"><span class="n mono">{i:02d}</span>'
            f'<span class="h">{rich(act.get("h", ""))}</span>{cost}{detail}{cmd}</div>'
        )
    hint = judgment.get("actions_hint", "")
    return f"""<section>
  <h3 class="sec">Do this now{f'<span class="hint">{e(hint)}</span>' if hint else ""}</h3>
  <div class="donow">{"".join(rows)}</div>
</section>"""


def route(judgment):
    steps = judgment.get("route") or []
    if not steps:
        return ""
    items = []
    for s in steps:
        state_cls = s.get("state", "ahead")
        items.append(
            f'<li class="{e(state_cls)}"><span class="n mono">{int(s.get("n", 0)):02d}</span>'
            f'<span class="what">{rich(s.get("what", ""))}</span>'
            f'<span class="state">{e(s.get("tag", ""))}</span></li>'
        )
    hint = judgment.get("route_hint", "")
    return f"""<section>
  <h3 class="sec">The route{f'<span class="hint">{e(hint)}</span>' if hint else ""}</h3>
  <ol class="route">{"".join(items)}</ol>
</section>"""


def meters(judgment):
    ms = judgment.get("meters") or []
    if not ms:
        return ""
    cards = []
    for m in ms:
        kind = m.get("kind", "pending")
        pct = m.get("pct")
        if pct is None:
            try:
                pct = round(100 * float(m["value"]) / float(m["total"]), 1)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                pct = 100
        total = f'<small> / {e(m["total"])}</small>' if m.get("total") not in (None, "") else ""
        val_cls = " bad" if kind == "bad" else ""
        note = f'<p class="note">{rich(m["note"])}</p>' if m.get("note") else ""
        cards.append(
            f'<div class="meter"><div class="head">'
            f'<span class="name">{e(m.get("name", ""))}</span>'
            f'<span class="val{val_cls} mono">{e(m.get("value", ""))}{total}</span></div>'
            f'<div class="bar"><span class="{e(kind)}" style="width:{max(1.5, min(100, pct))}%"></span></div>'
            f"{note}</div>"
        )
    return f"""<section>
  <h3 class="sec">Where the numbers stand</h3>
  <div class="meters">{"".join(cards)}</div>
</section>"""


def _row(id_text, title, url=None, tag=None, tone="grey", note=None, hot=False):
    link = f'<a href="{e(url)}">{e(title)}</a>' if url else e(title)
    tone = tone if tone in TONES else "grey"
    tag_html = f'<span class="tag {tone}">{e(tag)}</span>' if tag else ""
    note_html = f'<span class="d">{rich(note)}</span>' if note else ""
    return (
        f'<div class="row{" hot" if hot else ""}"><span class="id mono">{e(id_text)}</span>'
        f'<span class="t">{link}</span>{tag_html}{note_html}</div>'
    )


def groups(judgment):
    gs = judgment.get("groups") or []
    if not gs:
        return ""
    out = []
    for g in gs:
        rows = "".join(
            _row(
                r.get("id", ""), r.get("title", ""), r.get("url"),
                r.get("tag"), r.get("tone", "grey"), r.get("note"),
                hot=bool(r.get("hot")),
            )
            for r in g.get("rows", [])[:5]
        )
        out.append(
            f'<div><h4>{e(g.get("title", ""))}</h4><div class="rows">{rows}</div></div>'
        )
    hint = judgment.get("groups_hint", "")
    title = judgment.get("groups_title", "Findings")
    return f"""<section>
  <h3 class="sec">{e(title)}{f'<span class="hint">{e(hint)}</span>' if hint else ""}</h3>
  <div class="split">{"".join(out)}</div>
</section>"""


def pull_requests(state):
    prs = state.get("prs") or []
    if not prs:
        return ""
    ready = [p for p in prs if p["ready"]]
    rest = [p for p in prs if not p["ready"]]

    def pr_row(p):
        tone = {"green": "green", "red": "warn", "pending": "grey", "none": "grey"}[p["health"]]
        if p["draft"]:
            tag, tone = "Draft", "grey"
        elif p["health"] == "red":
            tag = "Checks red"
        elif p["mergeable"] != "MERGEABLE":
            tag, tone = "Conflicts", "warn"
        else:
            tag = "Ready"
        age = _days_since(p["updated"])
        note = f"Last touched {_fmt_date(p['updated'])}"
        if age is not None and age > 7:
            note += f" — {age} days ago"
        # Only things standing in the way wear the alert border. A merge-ready
        # PR is good news — a red box around a green READY tag reads as alarm.
        return _row(f"#{p['number']}", p["title"], p["url"], tag, tone, note,
                    hot=p["health"] == "red" or p["mergeable"] == "CONFLICTING")

    blocks = []
    if ready:
        blocks.append(
            f'<div><h4>Merge-ready — {len(ready)} finished, not landed</h4>'
            f'<div class="rows">{"".join(pr_row(p) for p in ready[:5])}</div></div>'
        )
    if rest:
        blocks.append(
            f'<div><h4>Still moving</h4>'
            f'<div class="rows">{"".join(pr_row(p) for p in rest[:5])}</div></div>'
        )
    return f"""<section>
  <h3 class="sec">Open pull requests<span class="hint">collected live</span></h3>
  <div class="split">{"".join(blocks)}</div>
</section>"""


def frontier(state):
    by_num = {t["number"]: t for t in state["tickets"]}
    front = [by_num[n] for n in state["frontier"] if n in by_num]
    blocked = [
        t for t in state["tickets"]
        if t["state"] == "open" and any(b["state"] == "open" for b in t["blocked_by"])
    ]
    if not front and not blocked:
        return ""

    def ticket_row(t, hot=False, note=None):
        kind = (t["kind"] or "ticket").title()
        tone = {"Research": "green", "Grilling": "hitl", "Prototype": "hitl"}.get(kind, "grey")
        age = _days_since(t["updated"])
        if note is None and age is not None and age > 7:
            note = f"Untouched for {age} days"
        return _row(f"#{t['number']}", t["title"], t["url"], kind, tone, note, hot=hot)

    shown = front[:5]
    overflow = front[5:]

    parts = [f'<div class="rows">{"".join(ticket_row(t) for t in shown)}</div>']

    if overflow:
        parts.append(
            f'<details><summary>{len(overflow)} more on the frontier</summary>'
            f'<div class="inner">{"".join(ticket_row(t) for t in overflow)}</div></details>'
        )

    if blocked:
        rows = "".join(
            ticket_row(
                t, hot=True,
                note="Blocked by " + ", ".join(
                    f"#{b['number']}" for b in t["blocked_by"] if b["state"] == "open"
                ),
            )
            for t in blocked[:3]
        )
        parts.append(f'<h4 class="sub-h">Blocked</h4><div class="rows">{rows}</div>')

    hint = f"{len(front)} unclaimed and takeable"
    return f"""<section>
  <h3 class="sec">The frontier<span class="hint">{e(hint)}</span></h3>
  {"".join(parts)}
</section>"""


def workspace(state):
    g = state["git"]
    bits = []
    if g["branch"] and g["branch"] not in ("main", "master"):
        bits.append(f'On branch <code class="mono">{e(g["branch"])}</code>')
    if g["dirty_count"]:
        bits.append(f'<strong>{g["dirty_count"]} uncommitted files</strong>')
    if not bits:
        bits.append("Clean tree on the default branch")
    commits = "".join(
        f'<li><span class="mono">{e(c["date"])}</span> {e(c["subject"])}</li>'
        for c in g["commits"][:5]
    )
    return f"""<section>
  <h3 class="sec">Workspace<span class="hint">as this page was written</span></h3>
  <p class="workspace-state">{" · ".join(bits)}</p>
  <ol class="commits">{commits}</ol>
</section>"""


def footer(state, judgment):
    reviewed = judgment.get("reviewed_at")
    bits = [
        f'Facts collected from <a href="{e(state["map"]["url"])}">map #{state["map"]["number"]}</a> '
        f'and the live PR/issue queue'
    ]
    if reviewed:
        bits.append(f"Judgment reviewed {e(reviewed)}")
    bits.append(f'<span class="mono">Generated {e(state["generated_at"][:16].replace("T", " "))}Z</span>')
    return f'<footer>{"".join(f"<span>{b}</span>" for b in bits)}</footer>'


# --------------------------------------------------------------------------


def render(state, judgment):
    css = (TEMPLATES / "page.css").read_text(encoding="utf-8")
    skeleton = (TEMPLATES / "page.html").read_text(encoding="utf-8")

    body = "\n".join(
        part for part in [
            masthead(state, judgment),
            staleness(state, judgment),
            answers(judgment),
            actions(judgment),
            route(judgment),
            meters(judgment),
            groups(judgment),
            pull_requests(state),
            frontier(state),
            workspace(state),
            footer(state, judgment),
        ] if part
    )

    repo_name = state["repo"].split("/")[-1]
    title = judgment.get("title") or f"{repo_name} Trailhead"

    return (
        skeleton
        .replace("{{TITLE}}", e(title))
        .replace("{{CSS}}", css)
        .replace("{{BODY}}", body)
    )
