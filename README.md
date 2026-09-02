# trailhead

A persistent "where are we" page for a long-running project, built from the repo's
[wayfinder](https://github.com/mattpocock/skills) map.

A wayfinder map is a good record and a poor dashboard. To answer *where are we* you
have to read an issue body, page through its child issues, and hold the
blocked/unblocked graph in your head. Trailhead renders that into one screen that
answers four questions, in this order:

1. **What's next?**
2. Where did we leave off?
3. Where are we going?
4. What is this?

Someone opening the page is disoriented. Orientation is what they need second; the
action is what they came for.

## Install

Requires `python3` (stdlib only), [`gh`](https://cli.github.com/) authenticated, and `git`.

```bash
git clone https://github.com/<you>/trailhead.git
ln -s "$PWD/trailhead/bin/trailhead" /usr/local/bin/trailhead
```

## Use

```bash
cd ~/some/repo-with-a-wayfinder-map
trailhead build --open
```

Pages are written to `~/.local/state/trailhead/` (override with `TRAILHEAD_HOME`),
one per repo, plus an `index.html` listing them all. Nothing is written into the
project except the judgment file described below.

| Command | Does |
|---|---|
| `trailhead build` | collect + render (add `--open` to open it) |
| `trailhead collect` | refresh the collected facts only |
| `trailhead index` | rebuild the index of every rendered page |
| `trailhead where` | print the output path |

## The two-file split

The page has a collected half and an authored half.

**Collected** — `bin/trailhead` runs a fixed set of `gh` and `git` queries: the map's
child tickets, their blocking edges, the resulting frontier, open PRs with check
health, recent commits, tree state. Free, deterministic, no session needed. Run it at
every session boundary.

**Authored** — `<repo>/.trailhead/judgment.json` holds what needs judgment: the four
answers, the route, the meters, the ranked next actions. Written by the `/trailhead`
skill, or by hand. If it goes more than 7 days without review the page says so at the
top rather than quietly serving stale advice.

The judgment file never contains a command for the generator to run. Meters carry
values that were measured when the file was written, not instructions to re-measure.
A page generator that executes strings out of a repo file is a code-execution seam,
and nothing here needs one.

## Design

`templates/page.css` is the entire design — `lib/render.py` emits semantic HTML and
inlines no styles. Light and dark, no JavaScript, no build step.

The visual language is trail blazing: exactly one saturated blaze carries the single
next action, and everything else stays quiet, because a page you check while
disoriented should have one loud thing on it rather than six.

## Privacy

This repo is public; the pages it generates are not. Rendered output and collected
state live outside the repo entirely, and `.gitignore` keeps any stray copy out of
version control. A project's own `.trailhead/judgment.json` belongs to that project.
