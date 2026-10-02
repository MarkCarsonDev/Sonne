# Sonne

[![CI](https://github.com/MarkCarsonDev/Sonne/actions/workflows/ci.yml/badge.svg)](https://github.com/MarkCarsonDev/Sonne/actions/workflows/ci.yml)

Sonne is a static site generator for small, light websites. It turns Markdown and Jinja2 templates into plain HTML, and it includes:

- a blog: dated posts, tags, categories, date archives, pagination and an RSS feed;
- an image pipeline that resizes, converts and optionally dithers images, with a toggle so visitors can see the original;
- data files and Python data scripts that feed variables to templates;
- accessibility checks on every build.

It needs Python 3.9 or newer and runs on Windows, macOS and Linux.

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Content](#content)
- [Images](#images)
- [Templates](#templates)
- [Data and variables](#data-and-variables)
- [Configuration](#configuration)
- [Commands](#commands)
- [Accessibility](#accessibility)
- [Deployment](#deployment)
- [Security](#security)
- [Contributing](#contributing)

## Install

Sonne is not published on PyPI. The `sonne` package there is an unrelated project, so `pip install sonne` installs something else. Install from the repository:

```bash
pip install git+https://github.com/MarkCarsonDev/Sonne.git
```

## Quick start

```bash
sonne new -p my-site -t blog
cd my-site
sonne build        # writes the site to output/
sonne serve        # builds, then serves http://localhost:8000
```

`sonne new` copies one of four starter templates:

| Template | What you get |
|----------|--------------|
| `minimal` | Two pages and a base template (the default). |
| `blog` | A blog with posts, tags, categories and a feed. |
| `portfolio` | Project pages, a filterable portfolio and a blog. |
| `solar` | A dithered theme with data scripts for battery and weather status. |

`sonne serve` rebuilds the site when a file under the content, templates, static, data or scripts folders changes, or the config file. It does not refresh the browser; reload the page to see the change.

A site looks like this:

```
my-site/
├── sonne.yaml      configuration
├── content/        pages, blog posts and their images
├── templates/      Jinja2 templates
├── static/         copied to the output as-is
├── data/           JSON, YAML and CSV data files (optional)
├── scripts/        Python data scripts (optional)
└── output/         the built site
```

## Content

### Pages

Every `.md`, `.markdown`, `.html` and `.htm` file under `content/` becomes a page. Files and folders whose names start with a dot are skipped. Where a page is written, and how it is linked, depends on [`url_style`](#url-styles-and-environments).

A page can start with front matter: YAML between `---` lines, or JSON between `;;;` lines.

```markdown
---
title: About
template: page.html
description: Who we are
---

## Our story

Body text in Markdown.
```

| Key | Meaning |
|-----|---------|
| `title` | Page title. In [`all_pages`](#pages-and-posts) it defaults to the file name. |
| `template` | Template to render the page with. Markdown pages default to `page.html`. |
| `jinja` | `true` or `false`: render this file through Jinja first (see [Jinja in content](#jinja-in-content)). |

Every other key is passed to the template as `page.<key>`.

An HTML page is only rendered through a template when its front matter names one. Without `template`, its content is written inside a bare page.

Markdown is converted with Python-Markdown and these extensions: tables, fenced code, table of contents, smart quotes, footnotes, attribute lists, definition lists, abbreviations and sane lists. The set is fixed.

### Blog posts

Markdown files under `content/blog/` (see `blog.directory`) are posts.

```markdown
---
title: My Blog Post
date: 2025-04-01
author: Jane Doe
tags: [web development, tutorial]
categories: [coding]
excerpt: An optional summary of this post
cover_img: cover.jpg
cover_alt: A hand-drawn map of the island
---

Post content here.
```

| Key | Meaning |
|-----|---------|
| `title` | Post title. Default: `Untitled`. |
| `date` | Publish date, `YYYY-MM-DD`. Without it, Sonne uses a `YYYY-MM-DD-` prefix in the file name, then the file's creation time. |
| `modified` | Last-edited date. Default: the file's modification time. |
| `author` | Default: `site.author`. |
| `slug` | URL slug. Default: made from the title, or from the file name without its date prefix. |
| `tags`, `categories` | A list, or one string separated by commas or spaces. Names that differ only in case share one page. |
| `excerpt` | Summary used in listings and the feed. `description` works too. Default: the first `blog.excerpt_length` characters of the text. |
| `draft` | `true` leaves the post out. So does putting the file in a `_drafts` folder inside the blog directory. `blog.include_drafts` publishes both. |
| `template` | Default: `blog.template`. |
| `cover_img` | Cover image. A path relative to the post is resized and dithered like the post's other images; a path starting with `/` is used as written. |
| `cover_alt` | Alt text for the cover. Leave it out when the cover is decorative. |
| `cover_crop`, `cover_rotate` | Crop the cover to a ratio (`16:9`) or rotate it clockwise by a number of degrees. |
| `jinja` | As for pages. |

A post's URL is the blog directory plus `blog.url_pattern`, which may use `{year}`, `{month}`, `{day}` and `{slug}`. With the defaults, `content/blog/2025-04-01-my-post.md` is published at `/blog/2025/04/01/my-blog-post`.

Sonne also generates:

| Page | URL (default settings) | Template |
|------|------------------------|----------|
| Post index, paginated | `/blog`, `/blog/page/2` | `blog_list.html` |
| One tag or category | `/blog/tags/<slug>`, `/blog/categories/<slug>` | `tag.html`, `category.html` |
| All tags or categories | `/blog/tags`, `/blog/categories` | `tags.html`, `categories.html` |
| Year, month and day archives | `/blog/2025`, `/blog/2025/04`, `/blog/2025/04/01` | `archive.html` |
| RSS feed | `/feed.xml` | none |

A site that has no template of one of these names gets Sonne's [built-in one](#built-in-templates).

With `blog.enabled: false`, files in the blog folder are rendered as ordinary pages.

### Jinja in content

Content files can be rendered through Jinja before Markdown conversion, which gives them variables, loops, filters and `{% include %}`. It is off by default. Turn it on for the whole site:

```yaml
content:
  render_jinja: true
```

or for one file, in its front matter (this wins over the site setting either way):

```yaml
---
title: My Post
jinja: true
---
```

Then:

```markdown
This site has {{ all_blog_posts | length }} posts.

{% for member in data.team %}
- **{{ member.name }}**, {{ member.role }}
{% endfor %}
```

- Content is not autoescaped, because its output is Markdown source. Variables that hold HTML are inserted as they are, without `| safe`.
- For a file with literal `{{` in code samples, set `jinja: false` or wrap the sample in `{% raw %}...{% endraw %}`.
- The older `{+}{variable}`, `{-}{variable}` and `{p}{# ... #}` syntaxes no longer exist. The build warns when it finds them in content.

## Images

Sonne handles images in three places. Remote images and SVGs are never processed.

**`static/images/`.** Each image is published at its own URL: `static/images/logo.png` is `/images/logo.png`. With dithering on, a dithered PNG is written to `/images/dithered/logo.png`.

**Images under `content/`.** Each image is written to `/assets/images/` at every width in `images.sizes` and in every format in `images.formats`, named `<name>_<width>_original.<format>`. With dithering on, dithered copies named `<name>_<width>.<format>` are added for `images.dither_sizes` and `images.dither_formats`. With the default settings, `content/photos/boat.jpg` gives:

```
/assets/images/boat_1200_original.webp    boat_1200_original.png
/assets/images/boat_800_original.webp     boat_800_original.png
/assets/images/boat_400_original.webp     boat_400_original.png
/assets/images/boat_400.webp              (dithered)
```

Images are never enlarged, and an animated GIF becomes a single frame. Files are named by the image's file name alone. When two images have the same file name, the second gets its folder in the name as well (`content/trips/boat.jpg` becomes `trips-boat_400.webp`) and the build warns; give the files different names to choose the names yourself.

**Images in a blog post.** An image a post refers to by a relative path (`![A boat](boat.jpg)`) is copied next to the published post, at most `images.blog_original_max_width` wide. With dithering on, a dithered PNG goes to `dithered/boat.png` beside it, at most `images.blog_dithered_max_width` wide, and the image is shown in a `<figure>` with a caption and a "view original" button. The caption is the image's title, or its alt text. The title can also carry transforms after a `|`:

```markdown
![A boat](boat.jpg "Leaving the harbour | crop=16:9 rotate=90")
```

On a regular page, refer to an image by its published URL (`/images/logo.png`, `/assets/images/boat_800_original.webp`). A relative image path in a regular page is not copied to the output.

`images.only_used: true` processes only the images that content or templates refer to.

### Dithering

`images.dither` is on by default; the `blog`, `portfolio` and `minimal` starter templates turn it off in their `sonne.yaml`. When it is on:

- Every `<img>` whose `src` is an image the build dithered is pointed at the dithered copy, and the original's URL is kept in `data-original-src`. Either URL of the pair works as the `src`.
- Each of those images gets a button that switches it to the original. Blog post figures have their "view original" button.
- Pages load `/css/dithering.css` and `/js/dithering.js`. The build adds them to any page that does not link them already.
- References outside `<img>` tags, such as CSS `url()`, `og:image` and the feed, keep pointing at the original.

Visitors can also choose to always see the originals; see [Dithered images and the "original images" setting](#dithered-images-and-the-original-images-setting).

Copies of static images named `/images/<name>_original.<ext>` are still written for sites built with Sonne 0.4. They will be removed in 0.6.0; link to `/images/<name>.<ext>` instead.

## Templates

Templates are Jinja2 files in `templates/`. A template gets:

| Variable | Contents |
|----------|----------|
| `content` | The page body as HTML. |
| `page` | The current page (see below). |
| `site` | The `site` section of the config, plus `site.year`, `site.build_time`, `site.generator_version` and `site.footer.custom`. |
| `data` | [Data files and script variables](#data-files). |
| `all_pages`, `all_blog_posts`, `tags`, `categories` | [Pages and posts](#pages-and-posts). |

Files in `static/` are copied to the root of the output, so `static/css/main.css` is linked as `/css/main.css`.

A small base template and page template:

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="{{ site.language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% if page.title %}{{ page.title }} - {% endif %}{{ site.title }}</title>
    <link rel="stylesheet" href="/css/main.css">
</head>
<body>
    <nav aria-label="Main">
        {% for item in site.nav %}
        <a href="{{ item.url }}"{% if page.url == item.url %} aria-current="page"{% endif %}>{{ item.text }}</a>
        {% endfor %}
    </nav>
    <main id="main">{% block content %}{% endblock %}</main>
    <footer>&copy; {{ site.year }} {{ site.author }}</footer>
</body>
</html>
```

```html
<!-- templates/page.html -->
{% extends "base.html" %}
{% block content %}
<h1>{{ page.title }}</h1>
{{ content }}
{% endblock %}
```

The starter templates are fuller examples; run `sonne new` and read the `templates/` folder it creates.

### The `page` variable

On a regular page, `page` is the page's front matter plus `page.url` and `page.source_path`.

On a post, `page` is the post's front matter plus the keys below. Where a front matter key has the same name as one of them, the value below wins.

| Key | Contents |
|-----|----------|
| `title`, `author`, `slug`, `excerpt`, `featured` | From the front matter, with the defaults above. |
| `tags`, `categories` | Lists of names. |
| `date`, `modified` | `datetime` values. |
| `date_str` | The date as `2025-04-01`. |
| `date_formatted`, `date_posted`, `date_edited` | Dates as `April 01, 2025` (`date_edited` is the modified date). |
| `url` | The post's URL. |
| `prev_post`, `next_post` | The next newer and next older post, each with `title` and `url`, or nothing at either end. |
| `related_posts` | Up to three posts, ranked by shared tags. |
| `cover_img`, `cover_alt` | As written in the front matter. |
| `cover_img_dithered`, `cover_img_original` | Paths of the published cover, relative to the post, when the cover is a file beside the post. |
| `metadata` | The post's front matter as written. |

On the generated blog pages:

| Page | `page` keys |
|------|-------------|
| Post index | `posts`, and `pagination` with `current`, `total`, `has_prev`, `has_next`, `prev_url`, `next_url` |
| One tag or category | `tag` or `category`, `tag_slug` or `category_slug`, `posts` |
| All tags or categories | `tags` or `categories`: each name mapped to its `name`, `slug` and `posts` |
| Archive | `posts`, `archive_type` (`year`, `month` or `day`), `archive_year`, `archive_month`, `archive_month_name`, `archive_day` |

All of them also have `title` and `url`. Posts in these lists have the keys in the table above, except that a post's link is `post.full_url`.

```html
{% for post in page.posts %}
<article>
    <h2><a href="{{ post.full_url }}">{{ post.title }}</a></h2>
    <time datetime="{{ post.date_str }}">{{ post.date_formatted }}</time>
    <p>{{ post.excerpt }}</p>
    {% for tag in post.tags %}<a href="{{ tag_url(tag) }}">{{ tag }}</a> {% endfor %}
</article>
{% endfor %}
```

### Functions and filters

Use these functions for links to blog pages. They follow `blog.directory` and `url_style`, and build slugs the way Sonne does. Do not build tag URLs by hand: a tag such as "Q&A Night" has a slug that `lower` and `replace` do not reproduce.

| Function | Returns the URL of |
|----------|--------------------|
| `blog_url()`, `blog_url(2)` | The post index, or one of its pages. |
| `tag_url("name")`, `tag_url()` | A tag's page, or the list of all tags. |
| `category_url("name")`, `category_url()` | A category's page, or the list of all categories. |
| `archive_url(2025)`, `archive_url(2025, 4)`, `archive_url(2025, 4, 1)` | A year, month or day archive. |

`dithering_enabled` is `true` when `images.dither` is on.

| Filter | Result |
|--------|--------|
| `slugify` | The slug Sonne uses in URLs: `{{ "Q&A Night" \| slugify }}` is `qa-night`. |
| `date` | A date formatted with a `strftime` pattern: `{{ page.date \| date("%d %b %Y") }}`. |
| `markdown` | Markdown text converted to HTML. |
| `word_count` | The number of words. |
| `truncate_words` | The first 30 words, or `truncate_words(n)`. |
| `process_image` | An `<img>` tag: `{{ "/images/logo.png" \| process_image("Logo") }}`. |

Data scripts can [add filters and functions](#script-api).

### Built-in templates

Sonne ships `blog_list.html`, `tag.html`, `tags.html`, `category.html`, `categories.html` and `archive.html`. They are used when the site has no template of that name, and they render inside the site's `base.html` (its `content` block), or a plain page if there is none. To replace one, add a template with the same name to `templates/`.

A page whose template is missing or fails to render is written as a plain page, and the build logs the problem.

## Data and variables

### Data files

Each JSON, YAML or CSV file in `data/` (including subfolders) is available in templates as `data.<file name>`. A CSV file is a list of rows.

```html
<!-- data/authors.yaml:  alice: Alice A. -->
By {{ data.authors.alice }}
{% for book in data.books %}{{ book.title }}{% endfor %}  {# data/books.csv #}
```

Variables set by data scripts are in `data` too, as `data.<name>`.

Before the `data` namespace, the keys of a mapping data file were merged into `site` and script variables had no prefix, so a script variable `weather` replaced `site.weather`. A template that still uses such a name gets a build warning that says where the value is now. To keep the old names while you update templates, set `variables.flatten_data: true`; that setting will be removed.

### Pages and posts

- `all_pages` holds every page rendered from `content/`, sorted by URL. Posts are not in it while the blog is enabled. Each entry is the page's front matter plus `title` (the front matter title, or the file name, or the folder name for an `index` page), `url`, `section` (the page's top-level folder under `content/`, `""` at the root) and `source_path`.
- `all_blog_posts` holds every post, newest first, with the keys listed under [The `page` variable](#the-page-variable).
- `tags` and `categories` map each name to its `name`, `slug` and `posts`.

A section index can list its pages without a script:

```html
<!-- templates/projects.html, used by content/projects/index.md -->
{% for p in all_pages if p.section == 'projects' and p.url != page.url %}
  <a href="{{ p.url }}">{{ p.title }}</a>
{% endfor %}
```

### Data scripts

Every `*.py` file directly in `scripts/` runs on each build, in alphabetical order, after posts and pages have been collected and before anything is rendered. Files whose names start with `_` are skipped; use them for shared helpers. Scripts are trusted code: see [Security](#security).

```python
# scripts/team.py
from sonne.script_api import sonne_var

sonne_var(
    "team",
    [
        {"name": "John Doe", "role": "Developer"},
        {"name": "Jane Smith", "role": "Designer"},
    ],
)
```

```html
{% for member in data.team %}
<h3>{{ member.name }}</h3>
<p>{{ member.role }}</p>
{% endfor %}
```

#### Script API

Scripts talk to Sonne through seven functions in `sonne.script_api`. They are typed, so editors and type checkers can check your calls.

| Function | What it does |
|----------|--------------|
| `sonne_var(name, value)` | Publishes a variable to templates and content Jinja as `{{ data.name }}`. |
| `sonne_filter(name, fn)` | Registers a Jinja filter: `{{ value \| name }}`. |
| `sonne_global(name, value)` | Registers a Jinja global value or function: `{{ name }}`, `{{ name(...) }}`. |
| `sonne_config(*keys, default=None)` | Reads the configuration of the running build (your config file merged over the defaults), e.g. `sonne_config("site", "base_url")`. One key returns a whole section. The result is a copy. |
| `get_variable(name, default=None)` | Reads anything templates can see: `all_pages`, `all_blog_posts`, `tags`, data files, site config values, and variables set by scripts that ran earlier. The result is a copy, and large values such as `all_blog_posts` are copied on every call, so call it once and keep the result. |
| `get_post(slug=None, tag=None)` | Returns a post by slug, or the newest post with a tag, or `None`. |
| `dither_image(image)` | Dithers a Pillow image with the site's `images.dither_*` settings. Resize first if needed. |

A filter or global whose name is already taken by a built-in one is ignored, with a warning.

```python
# scripts/tools.py
from sonne.script_api import get_variable, sonne_config, sonne_filter, sonne_global, sonne_var


def read_time(html):
    return f"{max(1, round(len(html.split()) / 220))} min read"


sonne_filter("shout", lambda text: str(text).upper())  # {{ title | shout }}
sonne_global("read_time", read_time)  # {{ read_time(content) }}

city = sonne_config("site", "weather", "city", default="Berlin")
sonne_var("weather_city", city)

pages = get_variable("all_pages", [])
projects = [p for p in pages if p["section"] == "projects" and p["url"] != "/projects/"]
sonne_var(
    "recent_projects", sorted(projects, key=lambda p: str(p.get("date", "")), reverse=True)[:3]
)
```

The functions work only while Sonne runs the script. Called anywhere else, for example when you run the script with plain `python`, they raise `RuntimeError`. Older scripts that use the same names without importing them keep working.

#### Footer script

A script named `footer.py` in `data/`, in your `paths.data` folder, or in `scripts/` can set footer HTML with `sonne_var("footer_custom", "<p>...</p>")`. The first one found runs, once. Its value is marked as safe HTML and is available as `site.footer.custom`.

## Configuration

The config file is YAML or JSON. Sonne looks for, in order, `sonne.yaml`, `sonne.yml`, `sonne.json`, `.sonne/config.yaml`, `sonne.config` (JSON), `.sonne.yaml` and `.sonne.json`, first in the site directory and then in up to two parent directories (with a warning when a parent's config is used). `sonne build` and `sonne serve` stop with an error when there is none; an empty `sonne.yaml` is enough, since every key is optional. Editors can validate and complete the file with the JSON schema in `sonne/schemas/sonne.schema.json`.

```yaml
site:
  title: My Site
  base_url: https://example.com
  description: A site built with Sonne
  author: Your Name
  nav:
    - text: Home
      url: /
    - text: Blog
      url: /blog/

blog:
  posts_per_page: 5

images:
  dither: true
  dither_method: bayer
  formats: [webp, jpg]

url_style: directory
```

A list in your config replaces the default list.

### URL styles and environments

`url_style` decides how pages are written and linked:

| Style | `about.md` is written to | and linked as |
|-------|--------------------------|---------------|
| `clean` | `about/index.html` | `/about` |
| `directory` | `about/index.html` | `/about/` |
| `html` | `about.html` | `/about.html` |

`index.md` is always its folder's `index.html`: `content/index.md` is `/`, and `content/projects/index.md` is `/projects/`.

`url_style` can be one style for everything (`url_style: clean`) or one per environment:

```yaml
url_style:
  prod: clean       # the default environment
  dev: directory    # used with --dev
```

The `environment` setting picks the entry. It is `prod` unless you change it, and `--dev` on `sonne build` or `sonne serve` selects `dev`. Other names work when `url_style` has an entry for them. A plain `sonne serve` therefore previews the production URLs.

### Reference

Every key Sonne understands, with its default. Nested keys are written with dots: `blog.rss.path` means `path` under `rss` under `blog`.

#### `site`

| Key | Default | Description |
|-----|---------|-------------|
| `site.title` | `My Sonne Site` | Site title. A mapping with a `text` key is also accepted. |
| `site.base_url` | `http://localhost` | Absolute base URL of the deployed site (used for RSS feed links). |
| `site.description` | `A site built with Sonne` | Site description for meta tags and the feed. |
| `site.author` | `Sonne User` | Default author. |
| `site.keywords` | `[]` | SEO keywords. |
| `site.language` | `en` | Language tag (BCP 47, e.g. `en-US`, `zh-Hans`). |
| `site.nav` | none | Navigation entries (`text`, `url`) rendered by the bundled templates. |
| `site.footer.text` | none | Footer text used by some templates. A `footer.py` data script can set custom footer HTML. |
| `site.footer.links` | none | Footer links (`text`, `url`) used by some templates. |
| `site.weather` | none | Template-specific: location settings read by the solar template's scripts. |

Any other key under `site` is passed through to templates unchanged.

#### `paths`

Relative to the site directory unless absolute.

| Key | Default | Description |
|-----|---------|-------------|
| `paths.content` | `content` | Pages, posts and content images. |
| `paths.output` | `output` | Where the built site is written. |
| `paths.static` | `static` | Copied into the output as-is. |
| `paths.templates` | `templates` | Jinja templates. |
| `paths.data` | `data` | JSON, YAML and CSV data files. |
| `paths.cache` | `.cache` | Image processing cache. |
| `paths.scripts` | `scripts` | Python data scripts (trusted code; see [Security](#security)). |

#### `blog`

| Key | Default | Description |
|-----|---------|-------------|
| `blog.enabled` | `true` | Build the blog. |
| `blog.directory` | `blog` | Posts directory inside `paths.content`. |
| `blog.template` | `blog_post.html` | Template for a post. |
| `blog.list_template` | `blog_list.html` | Template for the post listing. |
| `blog.posts_per_page` | `10` | Posts per listing page (a positive integer). |
| `blog.excerpt_length` | `200` | Length of auto-generated excerpts, in characters. |
| `blog.url_pattern` | `{year}/{month}/{day}/{slug}` | Post URL pattern. |
| `blog.include_drafts` | `false` | Include posts marked as drafts. |
| `blog.taxonomies.tags.enabled` | `true` | Generate tag pages. |
| `blog.taxonomies.tags.template` | `tag.html` | Template for one tag's page. |
| `blog.taxonomies.tags.list_template` | `tags.html` | Template for the list of all tags. |
| `blog.taxonomies.categories.enabled` | `true` | Generate category pages. |
| `blog.taxonomies.categories.template` | `category.html` | Template for one category's page. |
| `blog.taxonomies.categories.list_template` | `categories.html` | Template for the list of all categories. |
| `blog.rss.enabled` | `true` | Write an RSS feed. `blog.rss: false` (or `true`) is shorthand for this. |
| `blog.rss.path` | `feed.xml` | Feed path inside the output directory. |
| `blog.rss.max_items` | `20` | Maximum number of posts in the feed. |
| `blog.date_archives` | `true` | Generate year, month and day archive pages. |
| `blog.archive_template` | `archive.html` | Template for the archive pages. |

#### `images`

| Key | Default | Description |
|-----|---------|-------------|
| `images.dither` | `true` | Create dithered variants and emit the dithering CSS/JS. |
| `images.optimize` | `true` | Optimize saved images. |
| `images.formats` | `[webp, png]` | Output formats (`webp`, `png`, `jpg`, `jpeg`). |
| `images.sizes` | `[1200, 800, 400]` | Widths to generate (positive integers). |
| `images.only_used` | `false` | Only process images referenced from content or templates. |
| `images.dither_method` | `bayer` | One of `bayer`, `grayscale`, `palette`, `1bit`, `halftone`, `floyd_steinberg`, `threshold`, `color_median`, `color_octree`, `color_lab`. |
| `images.dither_colors` | `4` | Colors or levels used by the dither (2–256). |
| `images.dither_formats` | `[webp]` | Formats for dithered variants. |
| `images.dither_sizes` | smallest of `images.sizes` | Widths for dithered variants. |
| `images.dither_cover_images` | `true` | Dither blog cover images. |
| `images.blog_original_max_width` | `1600` | Maximum width of a blog post's original image. |
| `images.blog_dithered_max_width` | `400` | Maximum width of a blog post's dithered image. |
| `images.webp_method` | `0` | WebP encoder effort for dithered images (0 = fastest … 6 = smallest). |
| `images.webp_method_original` | `4` | WebP encoder effort for originals. |
| `images.parallel` | `true` | Process images in parallel. |
| `images.parallel_workers` | `0` | Worker threads; `0` means automatic (up to 4). |
| `images.lazy_loading` | `true` | No effect. |
| `images.grayscale_before_dither` | `false` | No effect: grayscale is chosen with `dither_method: grayscale`. |
| `images.parallel_processing` | none | Deprecated name for `images.parallel` (still accepted, with a warning). |
| `images.max_workers` | none | Deprecated name for `images.parallel_workers` (still accepted, with a warning). |

#### Other sections

| Key | Default | Description |
|-----|---------|-------------|
| `content.render_jinja` | `false` | Render content files through Jinja before Markdown. Front matter `jinja: true` or `false` overrides it per file. See [Jinja in content](#jinja-in-content). |
| `variables.file` | `sonne_variables.json` | File used by `variables.preserve_prior`. |
| `variables.preserve_prior` | `false` | Keep script-produced variables between builds. By default every build starts fresh. |
| `variables.flatten_data` | `false` | Legacy: also expose data files and script variables flat, next to site config, where they can replace it. They are always available as `data.<name>`. Will be removed. |
| `serve.host` | `localhost` | `sonne serve` host (the `--host` option overrides it). |
| `serve.port` | `8000` | `sonne serve` port (the `--port` option overrides it). |
| `environment` | `prod` | Selects the `url_style` entry. `--dev` sets `dev`, and custom names work when `url_style` has an entry for them. |
| `url_style.prod` | `clean` | URL style in `prod`: `clean`, `html` or `directory` (see [URL styles and environments](#url-styles-and-environments)). `url_style` may also be a single style for every environment. |
| `url_style.dev` | `directory` | URL style in `dev`. |
| `build.show_page_size` | `false` | Add a note with the page's weight after the content of every generated page. |
| `build.accessibility_checks` | `warn` | Check generated pages for machine-detectable accessibility failures: `warn` reports them, `error` also fails the build (for CI), `off` skips the checks. See [Accessibility](#accessibility). |
| `build.incremental` | none | Deprecated: has no effect and will be removed (every build is a full build). |
| `build.show_progress` | none | Deprecated: has no effect and will be removed; use `sonne build --no-progress`. |
| `build.statistics` | none | Deprecated: has no effect and will be removed; use `sonne build --perf` for the build report. |
| `security.csp.enabled` | none | Deprecated with all of `security.csp`: has no effect and will be removed. Sonne never added the policy to pages; send a `Content-Security-Policy` header from your web server instead. |
| `security.csp.directives` | none | Deprecated: see `security.csp.enabled`. |
| `security.allow_embedded_python` | none | Removed (warns and is ignored). Use data scripts with `sonne_global()`/`sonne_filter()` plus `content.render_jinja`. |
| `solar` | none | Template-specific: settings for the solar template's scripts. |

[`sonne migrate`](#sonne-migrate) rewrites a config file that uses deprecated or removed keys.

## Commands

```bash
sonne [-v] [-q] COMMAND [OPTIONS]
```

`-v` turns on debug logging and `-q` shows errors only. Both go before the command: `sonne -v build`. `sonne --version` prints the version.

### `sonne new`

```bash
sonne new [-p PATH] [-t TEMPLATE] [-n NAME] [-f]
```

- `-p, --path`: where to create the site (default: the current directory)
- `-t, --template`: `minimal` (default), `blog`, `portfolio` or `solar`
- `-n, --name`: site title (default: the folder's name)
- `-f, --force`: write into a folder that is not empty

### `sonne build`

```bash
sonne build [-p PATH] [-c CONFIG] [--clean] [--skip-images] [--skip-cache]
            [--dev] [--no-progress] [--perf] [--a11y-strict] [-y]
```

- `-p, --path`: site directory (default: the current directory)
- `-c, --config`: path to the config file
- `--clean`: empty the output directory first
- `--skip-images`: skip image processing
- `--skip-cache`: ignore the image cache and reprocess every image
- `--dev`: build the `dev` environment
- `--no-progress`: hide the step-by-step progress lines
- `--perf`: print a performance report after the build
- `--a11y-strict`: fail the build on accessibility issues, as with `build.accessibility_checks: error`
- `-y, --yes`: continue when templates have errors, without asking (for CI)

### `sonne serve`

```bash
sonne serve [-p PATH] [--port PORT] [--host HOST] [--no-browser] [--no-watch] [--dev]
```

- `-p, --path`: site directory (default: the current directory)
- `--port`, `--host`: where to serve (default: `serve.port` and `serve.host`, which default to `localhost:8000`)
- `--no-browser`: do not open the browser
- `--no-watch`: do not rebuild on changes
- `--dev`: serve the `dev` environment

A running server keeps the Sonne code it started with. If Sonne is upgraded or edited meanwhile, the next rebuild warns you to restart `sonne serve`.

### `sonne migrate`

```bash
sonne migrate [-p PATH] [-c CONFIG] [--write]
```

Renames deprecated config keys to their replacements (`images.max_workers` to `images.parallel_workers`) and removes keys that no longer exist or have no effect (`build.statistics`, `security.csp`). Sonne keeps accepting those keys, with a warning, until they are removed; `migrate` makes the warnings go away.

It prints each change and a diff. Nothing is written unless you pass `--write`; then the original is kept next to the file as `sonne.yaml.bak` (or `.bak.1`, `.bak.2`, and so on).

- YAML configs are edited in place, so comments and layout are kept. If a file cannot be edited that way (for example, a section written in `{flow: style}`), Sonne rewrites the whole file and says that comments and formatting will be lost.
- JSON configs are rewritten with 2-space indentation.

Options:

- `-p, --path`: site directory (default: the current directory); only the config file in that directory is migrated
- `-c, --config`: migrate this config file instead
- `--write`: apply the changes

## Accessibility

Sonne aims for sites that meet [WCAG 2.2](https://www.w3.org/TR/WCAG22/) level AA. It cannot guarantee that on its own: much of accessibility depends on your content, templates and CSS. It builds accommodations in where it can and checks what a program can check.

### Build-time checks

Every build checks the pages it wrote and reports failures per page:

| Check | WCAG |
|-------|------|
| `<img>` without an `alt` attribute (`alt=""` is fine for decorative images) | 1.1.1 |
| Links and buttons without an accessible name (text, `aria-label`, `aria-labelledby`, `title`, or an image with alt text inside) | 2.4.4, 4.1.2 |
| Form fields without a label (`<label for>`, a wrapping `<label>`, `aria-label` or `aria-labelledby`) | 1.3.1, 4.1.2 |
| Missing or empty `<html lang>` | 3.1.1 |
| Missing or empty `<title>` (an empty page is reported as such) | 2.4.2 |
| Duplicate `id` values | 4.1.1 (robustness) |
| Positive `tabindex`, which changes the keyboard focus order | 2.4.3 |
| Skipped heading levels, e.g. `h2` followed by `h4` (advisory only) | 1.3.1 |

Elements hidden from assistive technology (`aria-hidden="true"`, `hidden`) are skipped. Each finding names the element, the problem and how to fix it. Long reports are capped at 10 pages and 5 findings per page; the build summary always shows the totals.

`build.accessibility_checks` controls what happens:

- `warn` (default): report the findings; the build succeeds.
- `error`: report them and fail the build (exit code 1) if there are any, apart from advisories. Use this in CI, or pass `sonne build --a11y-strict` for one build.
- `off`: skip the checks.

### What the starter templates give you

The `blog`, `portfolio` and `minimal` templates start from a baseline you can keep when you restyle them:

- A "Skip to content" link as the first Tab stop, targeting `<main id="main">`.
- Labelled navigation landmarks, with `aria-current="page"` on the current page's link.
- One `<h1>` per page (the page title) and heading levels without gaps. Start your Markdown headings at `##`.
- Link text that makes sense on its own ("Read more: *Post title*", "Previous post: *Title*"), with decorative arrows hidden from screen readers.
- A visible focus ring, and support for forced colours (Windows High Contrast) and `prefers-reduced-motion`.
- Text colours that meet AA contrast (4.5:1), in both themes where a template has a dark mode.
- A `.visually-hidden` CSS class for text meant only for screen readers.
- Portfolio: filter buttons announce how many projects are shown, the image gallery opens in a keyboard-accessible dialog, and form errors are announced and tied to their fields.

The `solar` template and Sonne's [built-in templates](#built-in-templates) were brought to the same level.

### Dithered images and the "original images" setting

Dithering can make images hard to read, so visitors can always switch to the original. Each dithered image has a toggle button, and every page with dithered images offers an "Always show original images" setting that applies to every image and is remembered in the browser. Visitors whose system asks for more contrast (`prefers-contrast: more`) or uses forced colours see the originals by default; their own choice always wins. The toggles work with the keyboard and screen readers, stay visible in forced-colours mode, and skip their animation when reduced motion is requested.

On a page with dithered images, `dithering.js` adds a small "Always show original images" button before the first one. To put the setting elsewhere, for example in your header, add any element with the `data-sonne-original-images` attribute: a `<button>` becomes a toggle (its `aria-pressed` reflects the setting), and a checkbox is checked when originals are on. Once your template provides one, no button is added. Scripts can call `window.sonneDithering.showOriginals(true)` or `.showsOriginals()`, and listen for the `sonne:original-images` event on `document`.

A post's cover image takes its alt text from `cover_alt` in the front matter. It defaults to empty (decorative) because the post title sits next to it. Set `cover_alt` when the image carries information the title does not.

### What the checks can't tell you

A clean report means none of the checks above failed, not that the site is accessible. No program can decide these for you:

- whether alt text describes the image, and link text makes sense out of context;
- colour contrast of arbitrary CSS, in every theme and state;
- reading and focus order that matches the visual layout, and visible focus indicators;
- captions and transcripts for audio and video;
- how the site works with a keyboard, a screen reader, zoom to 400% or reduced motion.

Check your templates and a few representative pages yourself, at least whenever you change the layout:

- Use the site with only a keyboard: every link and control is reachable, in a sensible order, with a visible focus indicator.
- Try a screen reader (NVDA or Narrator on Windows, VoiceOver on macOS and iOS, TalkBack on Android).
- Zoom to 200% and 400% and check that nothing is cut off or overlaps.
- Run an automated audit in the browser (Lighthouse or axe DevTools) for colour contrast and other checks that depend on rendering.

## Deployment

`sonne build` writes a complete static site to `output/`. Upload that folder to any static host or web server.

With `url_style: clean`, links have no trailing slash (`/about`), so the server must serve `about/index.html` for `/about`. Most static hosts do. With Nginx:

```
location / {
    try_files $uri $uri/ $uri.html =404;
}
```

Set `site.base_url` to the deployed address; the RSS feed's links are built from it.

## Security

Building a Sonne site runs code:

- **Data scripts** (`scripts/*.py`) run with full process privileges on every build, the same trust model as Jekyll plugins or a Makefile. Only build sites you trust, and never point CI at untrusted site content.
- **Footer scripts**: a `footer.py` in `data/`, in your `paths.data` folder or in `scripts/` is executed the same way, even though the data folder otherwise holds only JSON, YAML and CSV. The `footer_custom` it sets is inserted into pages as raw HTML.
- **Jinja in content** (`content.render_jinja`) makes content files templates. Jinja is not a security boundary, so treat content authors as trusted, the same as script authors.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests and conventions, and [CHANGELOG.md](CHANGELOG.md) for what changed between versions.

## License

MIT. See [LICENSE](LICENSE).
