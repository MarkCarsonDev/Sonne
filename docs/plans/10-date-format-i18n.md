# 10 — Configurable date formats, i18n groundwork

**Size:** S/M · **Backlog #5** · **Breaking:** none by default

## Context

`'%B %d, %Y'` is hardcoded at every date-display site (`date_formatted`,
`date_posted`, `date_edited` in `_parse_post`; date archive titles use
English month names via `strftime('%B')`). A German site cannot exist.

## Design

1. New config `blog.date_format: '%B %d, %Y'` (strftime string) used for all
   three formatted post fields and archive month titles.
2. Month names: pure-strftime honors the process locale, which is fragile in
   builds. Provide `site.month_names:` (optional list of 12 strings) used by
   archive titles and a new Jinja filter `format_date(value, fmt=None)`
   that substitutes configured month names for `%B`. Default: English,
   exactly today's output.
3. RSS keeps RFC-822 English dates (spec requires them) — explicitly out of
   scope; add a code comment so nobody "fixes" it.
4. Templates get `format_date` so themes can render dates their own way
   without new post fields.

## Files

`sonne/processors/blog_processor.py`, `sonne/processors/template_processor.py`
(filter), `sonne/core/config.py` DEFAULT_CONFIG, schema, README, CHANGELOG.

## Tests

- default output identical to current pins;
- `blog.date_format: '%d.%m.%Y'` reflected in post fields and archives;
- `site.month_names` German list → archive title "März 2026";
- `format_date` filter usable from a template;
- RSS pubDate untouched by any of the above.
