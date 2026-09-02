---
name: trailhead
description: Use when you want a persistent "where are we" page for a long-running project — one screen answering what's next, where we left off, where we're going, and what this is, built from the repo's wayfinder map. Also use to refresh that page's judgment half after work lands. Triggers on "where are we", "where did I leave off", "build the trailhead", "refresh the trailhead", "what's the state of this project".
---

A wayfinder map is a good record and a poor dashboard: to answer "where are we" you have to read an issue body, page through child issues, and hold the blocked/unblocked graph in your head. Trailhead renders that into one page you can open any time.

## The two-file split

The page has a **collected** half and an **authored** half, and the split is the whole design.

| | Written by | Cost | Holds |
|---|---|---|---|
| `<state>.state.json` | `bin/trailhead` — fixed `gh` and `git` queries | free, ~2s | tickets, blocking edges, frontier, PR check health, commits, tree state |
| `<repo>/.trailhead/judgment.json` | this skill, or by hand | a session | the four answers, the route, the meters, the ranked actions, grouped findings |

**Never put a shell command in the judgment file for the script to run.** Meters carry values the session measured, not commands to re-measure. The script's query set is fixed on purpose: a page generator that executes strings out of a repo file is a code-execution seam, and nothing here needs one.

## Modes

### `build` — refresh the facts, keep the judgment

```bash
bin/trailhead build --open
```

Re-collects and re-renders. Cheap enough to run at every session boundary. If the judgment file is older than 7 days the page says so at the top rather than quietly serving stale advice.

This mode needs no session. Wire it into `/start` and `/wrap-up` directly.

### `review` — rewrite the judgment half

Do this when work has landed, the route has changed, or the staleness banner is showing.

1. **Read the map.** Its `## Destination` is "where are we going". Its re-charter or route prose is the `route` array — one step per phase, exactly one marked `"state": "here"`.
2. **Read the state file** at `~/.local/state/trailhead/<owner>__<repo>.state.json`. Frontier, blocking edges and PR health are already computed; do not re-derive them.
3. **Find what the tracker cannot tell you.** The high-value findings live in the gaps:
   - open PRs that are green and mergeable — finished work not landed;
   - tickets dispatched to agents and never closed;
   - blocking edges that contradict the map's current route;
   - issues filed *during* recent work, which are usually what the last session learned.
4. **Measure the meters yourself.** A meter is a number you checked this session with a citation in its note, not a guess.
5. **Rank the actions.** At most five, cheapest-unblocking first. Each carries a time estimate. Give the first one a copy-pasteable `cmd` when one exists.
6. **Write the four answers.** `next` is the one the reader came for — one sentence, an action, no preamble.
7. Write `.trailhead/judgment.json`, set `reviewed_at` to today, then run `build`.

## Answering order

The page renders in priority order, and it is not the order the questions get asked in:

1. **What's next?** — takes the blaze, full width, first
2. Where did we leave off?
3. Where are we going?
4. What is this?

Someone opening this page is disoriented. Orientation is what they need *second*; the action is what they came for.

## Wiring the bookends

- `/start` — run `build`, then read the page's four answers instead of re-deriving state.
- `/wrap-up` — run `build` after filing issues, so the next session opens onto current facts. Run `review` too if the session changed the route.

## Scope

One map per repo (`wayfinder:map`, open). More than one and `build` stops and asks which — that is the wayfinder skill's own one-active-map rule, enforced rather than assumed.
