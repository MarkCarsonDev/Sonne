# 01 — Jinja consolidation: one templating system

**Size:** L · **Absorbs backlog #8** · **Breaking:** removes never-functional syntax (deprecation warnings)

## Context

Sonne nominally has three-and-a-half content/templating mechanisms: Jinja2
templates, `{+}{var}` substitution, legacy `{-}{var}` (Mond) substitution, and
`{p}{# ... #}` embedded Python gated by `security.allow_embedded_python`.

Investigation (2026-07) established that **only Jinja actually runs**. The
entire `VariableManager.substitute_variables` method — which contains the
`{+}{}`/`{-}{}` regexes AND the embedded-Python `exec` — has no call site in
the build pipeline. The markers render literally; the security flag gates dead
code; the README documented behavior that never happened. Real sites have
already migrated themselves to Jinja without noticing.

The consolidation therefore has three parts: **delete** the dead subsystem,
**deliver** the one capability it promised (variables inside content files),
and **extend** the data-script hook so site authors can write real Python that
templates and content can call.

## Capability mapping (why nothing of value is lost)

| Author wants to… | Old (broken) way | New way |
|---|---|---|
| Show a variable in a template | `{+}{banner}` | `{{ banner }}` (already works) |
| Show a variable in a markdown page | `{+}{site.author}` (never worked) | `{{ author }}` with `content.render_jinja` / `jinja: true` |
| Loops/conditionals/filters in content | impossible | full Jinja: `{% for p in all_blog_posts %}…` |
| Set a variable from Python | `scripts/*.py` + `sonne_var(k, v)` | unchanged |
| Run Python inline in content | `{p}{# … #}` (never ran; unsandboxable) | write a function in a script, register it: `sonne_global('read_time', fn)` → `{{ read_time(content) }}`; or `sonne_filter('shout', fn)` → `{{ title \| shout }}` |
| Emit HTML from a variable | raw paste | `{{ banner \| safe }}` (explicit, same as templates today) |

Script-registered functions are strictly better than embedded Python: they
live in `.py` files (highlighting, linting, testable), run once per build in
a defined phase, and are callable from every template and every content file.

## Design decisions (settled)

1. **Content Jinja is opt-in.** New config `content.render_jinja: false`
   (default). Per-file front matter `jinja: true|false` overrides the site
   setting in both directions. Rationale: markdown containing literal
   `{{`/`{%` (code samples) must never break by surprise. `{% raw %}` blocks
   work for opted-in files that need literal braces.
2. **Delete, don't deprecate-and-keep, the dead machinery.**
   `substitute_variables` and its helpers are removed. `{+}{`, `{-}{`, and
   `{p}{#` markers found in content log ONE warning per file naming the Jinja
   equivalent (cheap regex scan during page/post processing).
3. **`security.allow_embedded_python` is removed** from `DEFAULT_CONFIG` and
   marked deprecated/no-op in the schema. A `REMOVED_CONFIG_KEYS` table in
   `sonne/core/deprecations.py` (new, alongside `DEPRECATED_CONFIG_KEYS`)
   warns once when a removed key is present in user config. `security.csp`
   is untouched.
4. **Script hooks:** the script namespace gains `sonne_filter(name, fn)` and
   `sonne_global(name, value_or_fn)` alongside `sonne_var`/`get_post`.
   VariableManager collects them (`self._custom_filters`, `_custom_globals`,
   reset in `load_variables`); SiteGenerator hands them to TemplateProcessor
   after `load_variables()` via a new `TemplateProcessor.register_extensions()`
   (mutating `jinja_env.filters` / `jinja_env.globals`). Names colliding with
   built-in filters log a warning and are ignored.
5. **Rendering pipeline placement:**
   - *Regular pages* (`_process_page` → `process_page`): variables are loaded
     by then. If Jinja is enabled for the file, render the raw content string
     through `jinja_env.from_string(raw).render(**context)` BEFORE markdown
     conversion (same context dict the page template gets). `from_string` on
     the shared env deliberately allows `{% include %}` of site templates —
     that's the shortcode story for free.
   - *Blog posts*: metadata collection (step 1) runs BEFORE data scripts
     (step 2), so parse-time Jinja would miss script vars. Instead, in
     `_render_posts` pass 1 — which runs after scripts — a Jinja-enabled post
     re-renders `raw_content` → Jinja → markdown → image tags, replacing
     `post['content']` BEFORE `_copy_post_images` does its size-attribute
     surgery. If the excerpt was auto-generated (no front-matter excerpt),
     regenerate it from the new HTML so `{{ }}` never leaks into excerpts.
   - Jinja render errors in content: log ERROR naming file + Jinja message,
     fall back to rendering the content un-Jinja'd (log-and-continue house
     style; `--strict` is a future flag).
6. **Autoescaping semantics match templates**: HTML-bearing variables need
   `| safe` in content exactly as in templates. Document prominently.

## Files

- `sonne/core/variable_manager.py` — delete `substitute_variables`; add
  filter/global collection; extend both script namespaces (main + footer).
- `sonne/processors/template_processor.py` — `render_content_jinja(raw, context)`
  helper; `register_extensions()`; wire into `process_page`/`process_markdown`
  path for pages; marker-warning scan.
- `sonne/processors/blog_processor.py` — pass-1 re-render for Jinja-enabled
  posts; excerpt regeneration.
- `sonne/core/site_generator.py` — pass extensions after `load_variables()`;
  compute per-page Jinja enablement (config default + front matter override).
- `sonne/core/config.py` — `content: {render_jinja: false}` in DEFAULT_CONFIG;
  drop `security.allow_embedded_python`; validate() warning removal.
- `sonne/core/deprecations.py` — `REMOVED_CONFIG_KEYS` mechanism.
- `sonne/schemas/sonne.schema.json`, `README.md`, `CHANGELOG.md` — lockstep.
- Bundled/showcase content that demos `{+}{site.year}` etc. → rewrite as
  Jinja examples (inside `{% raw %}` where they're teaching syntax);
  showcase-template opts in via `content.render_jinja: true`.
- Tests: replace `TestSubstitution` in `tests/unit/test_variable_manager.py`;
  new coverage listed below.

## Test plan

Unit/integration additions:
- default off: `{{ author }}` in a page renders literally;
- site-wide opt-in renders variables, loops, and `{% include %}` in a page;
- per-file `jinja: true` overrides site-off; `jinja: false` overrides site-on;
- blog post with Jinja sees SCRIPT variables (proves the pass-1 ordering);
- auto-excerpt of a Jinja post contains rendered text, not `{{ }}`;
- `sonne_filter`/`sonne_global` from a script usable in a template AND in
  opted-in content; collision with built-in filter warns and is ignored;
- `{+}{x}` in content logs a warning naming the file, once;
- config with `allow_embedded_python: true` logs a removed-key warning;
- Jinja syntax error in content: build completes, ERROR names the file.

## Compatibility

No functioning behavior changes: the removed syntaxes never executed. Sites
with markers in dead template files get warnings only when those files are
actually processed. CHANGELOG under **Removed** (dead syntax + config key)
and **Added** (`content.render_jinja`, `jinja:` front matter, `sonne_filter`,
`sonne_global`).
