---
jinja: true
title: Jinja in Content — Live Demo
template: page.html
description: This page is rendered through Jinja before markdown conversion.
---

# Jinja in Content — Live Demo

This page has `jinja: true` in its front matter, so everything below is
computed at build time.

- The current year is **{{ year }}**.
- This site is *{{ title }}* by *{{ author }}*.
- This build's random number: **{{ build_number }}**.
- There are **{{ all_blog_posts | length }}** blog posts:
{% for post in all_blog_posts %}
  - [{{ post.title }}]({{ post.full_url }}) ({{ post.date_str }})
{% endfor %}

To show literal Jinja syntax on an opted-in page, wrap it in
raw/endraw tags — this is literal, not evaluated: {% raw %}`{{ year }}`{% endraw %}.
