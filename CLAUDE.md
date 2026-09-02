# trailhead — repo conventions

Renders a repo's wayfinder map into a "where are we" page. See `README.md` for what it
does and `skills/trailhead/SKILL.md` for how the skill half works.

## Invariants

- **This repo is public. Nothing project-specific lives in it.** No captured maps, no
  rendered pages, no judgment files, no fixtures carrying real ticket text. Output goes
  to `~/.local/state/trailhead/`; `.gitignore` catches strays.
- **The generator never executes strings from a config file.** `lib/collect.py` runs a
  fixed set of `gh` and `git` argument vectors and nothing else. Repo-specific numbers
  reach the page as *values* in `judgment.json`, measured by the session that wrote
  them. If a feature seems to need "run this command per repo", it is the wrong feature.
- **The design is one file.** `templates/page.css`. `lib/render.py` emits semantic HTML
  and inlines no style. A design pass touches the stylesheet only.
- **Class names are an interface.** `render.py` and `page.css` agree on them; renaming
  one without the other silently unstyles a section. Both themes must be checked after
  any token change.
- **stdlib only.** No pip dependencies. The point is that it runs anywhere `gh` does.

## Accessibility floor

Text tokens are contrast-checked against every surface they sit on, worst case ≥4.5:1.
`--ink-3` is the tight one — it carries ticket ids, dates, hints and the footer, and it
sits on `--surface-2`. Re-check both themes before changing any neutral.

## Adding a section

1. Add a renderer to `lib/render.py` returning `""` when it has nothing to show.
2. Add it to the list in `render()` — order on the page is order in that list.
3. Style it in `templates/page.css`.
4. Rebuild against a real repo and check light, dark, and 390px before committing.
