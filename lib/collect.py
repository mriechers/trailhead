"""Collect the mechanical facts about a repo's wayfinder map.

Everything here is derived from fixed `gh` and `git` queries. Nothing in this
module reads a command out of a config file and runs it — the repo-specific
judgment (meters, route, ranked actions) is authored by the /trailhead skill
into .trailhead/judgment.json instead. See CLAUDE.md, "The two-file split".
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone

MAP_LABEL = "wayfinder:map"
TICKET_LABEL_RE = re.compile(r"^wayfinder:(research|prototype|grilling|task)$")


class CollectError(RuntimeError):
    pass


def _run(args, cwd=None, check=True):
    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=90
    )
    if check and proc.returncode != 0:
        raise CollectError(f"{' '.join(args[:3])}… exited {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout


def _gh_json(args, cwd, default=None):
    try:
        out = _run(["gh", *args], cwd=cwd)
    except CollectError:
        return default
    out = out.strip()
    if not out:
        return default
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return default


def repo_slug(cwd):
    data = _gh_json(["repo", "view", "--json", "nameWithOwner"], cwd)
    if not data:
        raise CollectError("not a GitHub repo, or gh is not authenticated")
    return data["nameWithOwner"]


def find_map(cwd):
    """The one open issue labelled wayfinder:map. Zero or many is a caller problem."""
    maps = _gh_json(
        ["issue", "list", "--label", MAP_LABEL, "--state", "open",
         "--json", "number,title,url,body,updatedAt"],
        cwd, default=[],
    )
    return maps


def _destination(body):
    """First prose block under a `## Destination` heading."""
    if not body:
        return ""
    m = re.search(r"^##\s+Destination\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    # Collapse to a single paragraph; the page has room for a couple of lines.
    para = text.split("\n\n")[0]
    return re.sub(r"\s+", " ", para).strip()


def _section(body, heading):
    if not body:
        return []
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    if not m:
        return []
    items = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            items.append(re.sub(r"\s+", " ", line[2:]).strip())
    return items


def collect_tickets(cwd, repo, map_number):
    """Sub-issues of the map, with their blocking edges resolved."""
    subs = _gh_json(
        ["api", "--paginate", f"repos/{repo}/issues/{map_number}/sub_issues"],
        cwd, default=[],
    ) or []

    tickets = []
    for s in subs:
        labels = [l["name"] for l in s.get("labels", [])]
        kind = next(
            (m.group(1) for l in labels if (m := TICKET_LABEL_RE.match(l))), None
        )
        blockers = _gh_json(
            ["api", f"repos/{repo}/issues/{s['number']}/dependencies/blocked_by"],
            cwd, default=[],
        ) or []
        tickets.append({
            "number": s["number"],
            "title": s["title"],
            "url": s["html_url"],
            "state": s["state"],
            "kind": kind,
            "assignee": (s.get("assignee") or {}).get("login"),
            "updated": s.get("updated_at"),
            "blocked_by": [
                {"number": b["number"], "state": b["state"], "title": b["title"]}
                for b in blockers
            ],
        })
    return tickets


def frontier(tickets):
    """Open, unclaimed, with every blocker closed — the edge of the known."""
    out = []
    for t in tickets:
        if t["state"] != "open" or t["assignee"]:
            continue
        if any(b["state"] == "open" for b in t["blocked_by"]):
            continue
        out.append(t["number"])
    return out


def stale_edges(tickets):
    """Blocking edges pointing at an already-closed ticket.

    A closed blocker is not a bug on its own — it is how an edge retires. What
    this flags is the opposite shape: an OPEN ticket held by a blocker that is
    itself open, where the map's own route has since inverted the pair. We can't
    read the route from prose, so we surface every live edge and let the
    judgment file say which are wrong.
    """
    live = []
    for t in tickets:
        if t["state"] != "open":
            continue
        for b in t["blocked_by"]:
            if b["state"] == "open":
                live.append({"blocked": t["number"], "by": b["number"], "by_title": b["title"]})
    return live


def collect_prs(cwd):
    prs = _gh_json(
        ["pr", "list", "--state", "open", "--limit", "30",
         "--json", "number,title,url,isDraft,mergeable,updatedAt,statusCheckRollup"],
        cwd, default=[],
    ) or []

    out = []
    for p in prs:
        checks = p.get("statusCheckRollup") or []
        results = [(c.get("conclusion") or c.get("state") or "").upper() for c in checks]
        meaningful = [r for r in results if r not in ("", "SKIPPED", "NEUTRAL")]
        if any(r in ("FAILURE", "ERROR", "TIMED_OUT") for r in meaningful):
            health = "red"
        elif meaningful and all(r == "SUCCESS" for r in meaningful):
            health = "green"
        elif not meaningful:
            health = "none"
        else:
            health = "pending"
        out.append({
            "number": p["number"],
            "title": p["title"],
            "url": p["url"],
            "draft": p["isDraft"],
            "mergeable": p.get("mergeable"),
            "updated": p.get("updatedAt"),
            "health": health,
            "ready": (not p["isDraft"]) and p.get("mergeable") == "MERGEABLE" and health == "green",
        })
    return out


def collect_git(cwd):
    status = _run(["git", "status", "--short"], cwd=cwd, check=False)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, check=False).strip()
    log = _run(
        ["git", "log", "-6", "--date=short", "--format=%ad\t%s"], cwd=cwd, check=False
    )
    commits = []
    for line in log.splitlines():
        if "\t" in line:
            d, s = line.split("\t", 1)
            commits.append({"date": d, "subject": s})
    dirty = [l for l in status.splitlines() if l.strip()]
    return {
        "branch": branch,
        "dirty_count": len(dirty),
        "dirty": dirty[:12],
        "commits": commits,
    }


def collect_recent_issues(cwd, limit=8):
    issues = _gh_json(
        ["issue", "list", "--state", "open", "--limit", str(limit),
         "--json", "number,title,url,updatedAt,labels"],
        cwd, default=[],
    ) or []
    return [{
        "number": i["number"],
        "title": i["title"],
        "url": i["url"],
        "updated": i.get("updatedAt"),
        "labels": [l["name"] for l in i.get("labels", [])],
    } for i in issues]


def collect(cwd, map_number=None):
    repo = repo_slug(cwd)
    maps = find_map(cwd)

    if map_number is not None:
        chosen = next((m for m in maps if m["number"] == map_number), None)
        if chosen is None:
            data = _gh_json(
                ["issue", "view", str(map_number), "--json", "number,title,url,body,updatedAt"],
                cwd,
            )
            if not data:
                raise CollectError(f"issue #{map_number} not found in {repo}")
            chosen = data
    elif len(maps) == 1:
        chosen = maps[0]
    elif not maps:
        raise CollectError(
            f"no open issue labelled {MAP_LABEL} in {repo} — "
            f"chart one with /wayfinder, or pass --map <number>"
        )
    else:
        numbers = ", ".join(f"#{m['number']}" for m in maps)
        raise CollectError(
            f"{len(maps)} open maps in {repo} ({numbers}) — pass --map <number>. "
            f"Operating rule S1 says one active map per repo."
        )

    tickets = collect_tickets(cwd, repo, chosen["number"])

    return {
        "schema": 1,
        "repo": repo,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "map": {
            "number": chosen["number"],
            "title": chosen["title"],
            "url": chosen["url"],
            "updated": chosen.get("updatedAt"),
            "destination": _destination(chosen.get("body", "")),
            "not_yet_specified": _section(chosen.get("body", ""), "Not yet specified"),
            "decisions": _section(chosen.get("body", ""), "Decisions so far"),
        },
        "tickets": tickets,
        "frontier": frontier(tickets),
        "live_edges": stale_edges(tickets),
        "prs": collect_prs(cwd),
        "git": collect_git(cwd),
        "recent_issues": collect_recent_issues(cwd),
    }
