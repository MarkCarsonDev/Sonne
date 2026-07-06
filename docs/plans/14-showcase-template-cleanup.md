# 14 — Showcase & bundled template cleanup

**Size:** S · **Backlog #14** · **Breaking:** none (templates are scaffolding) · **good first issue**

## Context

`sonne/examples/showcase-template` predates several conventions: its nav
hardcodes `.html` URLs (`/features.html`, `/blog/index.html`), it omits
`url_style` (silently inheriting `prod: clean`), and its content
demonstrates `{+}{}` syntax that never worked. Separately, the bundled
`blog` template enables the categories taxonomy by default but ships no
`category.html`/`categories.html`, so every fresh blog site logs
"Template not found" warnings.

## Design

1. Showcase: directory-style nav URLs (`/features/`), explicit
   `url_style: {prod: directory, dev: directory}` matching the bundled
   templates, `content.render_jinja: true` (after plan 01) with content
   examples rewritten to real Jinja.
2. Bundled blog template: add `category.html` + `categories.html` (copy the
   tag templates, swap labels) so the default scaffold builds warning-free.
3. Add a scaffold-quality test: `sonne new -t blog` + build logs **zero
   warnings** (caplog assertion) — this pins the "fresh site is clean"
   property for every template going forward; parametrize across all four
   templates.

## Files

`sonne/examples/showcase-template/**`, `sonne/templates/blog/templates/`,
`tests/integration/test_cli.py` (or new `test_scaffolds.py`), CHANGELOG.

## Tests

The zero-warnings scaffold test above is the deliverable; everything else is
content editing verified by it.
