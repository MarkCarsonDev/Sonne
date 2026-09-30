# Sonne Static Site Generator

[![PyPI version](https://img.shields.io/badge/pypi-v0.4.0-blue.svg)](https://pypi.org/project/sonne/)
[![Python Versions](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/sonne/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Sonne is a minimalist static site generator optimized for creating efficient websites with minimal resource requirements. It provides a flexible, Python-based platform for building blogs, portfolios, documentation sites, and more.

### Key Features

- **Minimalist design philosophy** with a focus on performance and simplicity
- **Markdown-based content** with powerful front matter support
- **Flexible templating** using Jinja2
- **Built-in blog functionality** with tags, categories, and RSS feeds
- **Image optimization** with automated resizing, format conversion, and dithering
- **Variable system** for dynamic content and data injection
- **Live development server** with auto-reload
- **Python data sources** for advanced content generation
- **Customizable themes** and templates

## Installation

Install Sonne using pip:

```bash
pip install sonne
```

### Dependencies

Sonne has the following dependencies (installed automatically by pip):

- Python 3.9+
- markdown
- Pillow and numpy (image processing and dithering)
- click and rich (CLI and console output)
- PyYAML
- Jinja2 and MarkupSafe
- beautifulsoup4 (HTML post-processing)
- watchdog (file watching for `sonne serve`)

## Quick Start

### Create a new site

```bash
sonne new -p my-site -t blog
```

Available templates:

- `blog`: Full-featured blog template
- `portfolio`: Portfolio/showcase site template
- `minimal`: Bare-bones template (the default)
- `solar`: Solar-powered-site theme with battery/weather data scripts

### Build the site

```bash
cd my-site
sonne build
```

### Serve the site locally

```bash
sonne serve
```

This will start a local development server at http://localhost:8000 with live reloading.

## Site Configuration

Sonne uses a configuration file to customize your site. The configuration file can be in YAML or JSON format. Sonne looks for, in order, `sonne.yaml`, `sonne.yml`, `sonne.json`, `.sonne/config.yaml`, `sonne.config` (JSON), `.sonne.yaml` and `.sonne.json`, first in the site directory and then up to two parent directories (with a warning when a parent's config is used). Every key is optional; anything you leave out takes the default listed in the [Configuration Reference](#configuration-reference). Editors can validate and complete the file with the JSON schema in `sonne/schemas/sonne.schema.json`.

### Example Configuration (sonne.yaml)

```yaml
site:
  title: My Awesome Site
  base_url: https://example.com
  description: A site built with Sonne
  author: Your Name
  keywords:
    - static site
    - blog
    - sonne
  language: en

paths:
  content: content
  output: output
  static: static
  templates: templates
  data: data
  cache: .cache

blog:
  enabled: true
  directory: blog
  template: blog_post.html
  list_template: blog_list.html
  posts_per_page: 10
  excerpt_length: 200
  url_pattern: '{year}/{month}/{day}/{slug}'
  include_drafts: false
  taxonomies:
    tags:
      enabled: true
      template: tag.html
      list_template: tags.html
    categories:
      enabled: true
      template: category.html
      list_template: categories.html

images:
  dither: false
  optimize: true
  formats:
    - webp
    - png
  sizes:
    - 1200
    - 800
    - 400
```

### Configuration Reference

Every key Sonne understands, with its default. Nested keys are written with dots: `blog.rss.path` means `path` under `rss` under `blog`.

#### `site`: site metadata (all exposed to templates as `site.*`)

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

#### `paths`: directories, relative to the site directory unless absolute

| Key | Default | Description |
|-----|---------|-------------|
| `paths.content` | `content` | Pages, posts and content images. |
| `paths.output` | `output` | Where the built site is written. |
| `paths.static` | `static` | Copied verbatim into the output. |
| `paths.templates` | `templates` | Jinja templates. |
| `paths.data` | `data` | JSON, YAML and CSV data files. |
| `paths.cache` | `.cache` | Image processing cache. |
| `paths.scripts` | `scripts` | Python data scripts (trusted code; see [Python Data Sources](#python-data-sources)). |

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
| `blog.date_archives` | `true` | Generate year and month archive pages. |
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
| `images.lazy_loading` | `true` | No effect: generated `<img>` tags always use `loading="lazy"`. |
| `images.grayscale_before_dither` | `false` | No effect: grayscale is chosen with `dither_method: grayscale`. |
| `images.parallel_processing` | none | Deprecated name for `images.parallel` (still accepted, with a warning). |
| `images.max_workers` | none | Deprecated name for `images.parallel_workers` (still accepted, with a warning). |

#### Other sections

| Key | Default | Description |
|-----|---------|-------------|
| `content.render_jinja` | `false` | Render content files through Jinja before Markdown. Per-file front matter `jinja: true` or `false` overrides it. See [Variables in Content](#variables-in-content-jinja). |
| `variables.file` | `sonne_variables.json` | File used by `variables.preserve_prior`. |
| `variables.preserve_prior` | `false` | Keep script-produced variables between builds. By default every build starts fresh. |
| `variables.flatten_data` | `true` | Also expose data files and script variables flat, next to site config (legacy). They are always available as `data.<name>`; set `false` so they can never replace site config. The default will become `false`. |
| `serve.host` | `localhost` | `sonne serve` host (the `--host` option overrides it). |
| `serve.port` | `8000` | `sonne serve` port (the `--port` option overrides it). |
| `environment` | `prod` | Selects the `url_style` entry. `sonne build --dev` sets `dev`, and custom names work when `url_style` has an entry for them. |
| `url_style.prod` | `clean` | URL style in `prod`: `clean`, `html` or `directory` (see [URL Configuration](#url-configuration)). `url_style` may also be a single style for every environment. |
| `url_style.dev` | `directory` | URL style in `dev`. |
| `build.show_page_size` | `false` | Add a small page-weight label to every generated page. |
| `build.accessibility_checks` | `warn` | Check generated pages for machine-detectable accessibility failures: `warn` reports them, `error` also fails the build (for CI), `off` skips the checks. See [Accessibility](#accessibility). |
| `build.incremental` | none | Deprecated: has no effect and will be removed (every build is a full build). |
| `build.show_progress` | none | Deprecated: has no effect and will be removed; use `sonne build --no-progress`. |
| `build.statistics` | none | Deprecated: has no effect and will be removed; use `sonne build --perf` for the build report. |
| `security.csp.enabled` | none | Deprecated with all of `security.csp`: has no effect and will be removed. Sonne never added the policy to pages; send a `Content-Security-Policy` header from your web server instead. |
| `security.csp.directives` | none | Deprecated: see `security.csp.enabled`. |
| `security.allow_embedded_python` | none | Removed (warns and is ignored). Use data scripts with `sonne_global()`/`sonne_filter()` plus `content.render_jinja`. |
| `solar` | none | Template-specific: settings for the solar template's scripts. |

## Content Creation

### Page Structure

Content is stored in the `content` directory. Each markdown file becomes a page on your site.

### Front Matter

Pages and blog posts use front matter to define metadata:

```markdown
---
title: My Page Title
template: page.html
description: This is a page description
---

# Main Content Heading

This is the page content in Markdown format.
```

### Blog Posts

Blog posts are stored in the `content/blog` directory by default and support additional front matter:

```markdown
---
title: My Blog Post
date: 2025-04-01
author: John Doe
tags:
  - web development
  - tutorial
categories:
  - coding
excerpt: An optional custom excerpt for this post
featured: true
# Post-relative path: the cover is resized/dithered alongside the post.
# (Absolute /... paths are served from static/ and are not processed here.)
cover_img: post-cover.jpg
---

Post content here...
```

## Templates and Theming

### Template Structure

Templates are stored in the `templates` directory and use Jinja2 syntax.

### Static Assets

Static assets (CSS, JavaScript, images) should be placed in the `static` directory. These files will be copied to the output directory during the build process, preserving their subdirectory structure but removing the "static" prefix:

```
static/
├── css/main.css       → output/css/main.css
├── js/script.js       → output/js/script.js
└── images/logo.png    → output/images/logo.png
```

Therefore, in your templates, you should reference these files without the "static" prefix:

```html
<link rel="stylesheet" href="/css/main.css">
<script src="/js/script.js"></script>
<img src="/images/logo.png" alt="Logo">
```

### Base Template Example

```html
<!DOCTYPE html>
<html lang="{{ site.language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% if page.title %}{{ page.title }} - {% endif %}{{ site.title }}</title>
    <meta name="description" content="{{ page.description | default(site.description) }}">
    <link rel="stylesheet" href="/css/main.css">
</head>
<body>
    <header>
        <h1><a href="/">{{ site.title }}</a></h1>
        <nav>
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/blog/">Blog</a></li>
                <li><a href="/about/">About</a></li>
            </ul>
        </nav>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
    <footer>
        <p>© {{ site.year }} {{ site.author }}</p>
        {% if site.footer.custom %}{{ site.footer.custom }}{% endif %}
    </footer>
</body>
</html>
```

### Page Template Example

```html
{% extends "base.html" %}

{% block content %}
<article>
    <h1>{{ page.title }}</h1>
    <div class="content">
        {{ content }}
    </div>
</article>
{% endblock %}
```

### Blog Post Template Example

```html
{% extends "base.html" %}

{% block content %}
<article class="blog-post">
    <header>
        <h1>{{ page.title }}</h1>
        <div class="meta">
            <time datetime="{{ page.date_str }}">{{ page.date_formatted }}</time>
            {% if page.author %} by {{ page.author }}{% endif %}
        </div>
    </header>
  
    {% if page.cover_img %}
    <img src="{{ page.cover_img }}" alt="{{ page.title }}" class="post-cover">
    {% endif %}
  
    <div class="content">
        {{ content }}
    </div>
  
    {% if page.tags %}
    <div class="tags">
        <h3>Tags:</h3>
        <ul>
            {% for tag in page.tags %}
            <li><a href="/blog/tags/{{ tag | lower | replace(' ', '-') }}/">{{ tag }}</a></li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}
  
    <nav class="post-navigation">
        {% if page.prev_post %}
        <a href="{{ page.prev_post.url }}" class="prev">← {{ page.prev_post.title }}</a>
        {% endif %}
      
        {% if page.next_post %}
        <a href="{{ page.next_post.url }}" class="next">{{ page.next_post.title }} →</a>
        {% endif %}
    </nav>
</article>
{% endblock %}
```

### Creating a New Template

To create a custom template for Sonne:

1. Create a directory structure similar to:

   ```
   my-template/
   ├── static/
   │   ├── css/
   │   ├── js/
   │   └── images/
   ├── templates/
   │   ├── base.html
   │   ├── page.html
   │   ├── blog_post.html
   │   └── blog_list.html
   ├── content/
   │   ├── index.md
   │   ├── about.md
   │   └── blog/
   │       └── first-post.md
   └── sonne.yaml
   ```
2. Define templates in Jinja2 format
3. Add static assets (CSS, JS, images)
4. Create sample content
5. Configure with sonne.yaml

## Variables and Data Management

Sonne provides a powerful variable system for dynamic content:

### Global Variables

Available across all templates:

- `site`: Site-wide configuration and data
- `page`: Current page information
- `all_blog_posts`: List of all blog posts (when blog is enabled)
- `all_pages`: List of every content page (see below)
- `data`: every data file and script variable, by name (see below)
- Custom global variables set in data files or scripts (legacy flat access)

### The `data` Namespace

Each file in `data/` is available as `data.<file name>`, and each script
variable (`sonne_var("name", ...)`) as `data.<name>`, in every template as
`data.*` and `site.data.*`:

```html
<!-- data/authors.yaml:  alice: Alice A. -->
By {{ data.authors.alice }}
{% for book in data.books %}{{ book.title }}{% endfor %}  {# data/books.csv #}
```

For backward compatibility they are also exposed the old flat way: the keys
of a mapping data file merged into `site`, script variables at the top level.
Flat names can clash with site config (a script variable `weather` replaces
`site.weather`; Sonne warns when that happens). Set
`variables.flatten_data: false` to use only `data.*`, which can never
clash. That will become the default in a future release.

### Listing Pages (`all_pages`)

`all_pages` holds every page Sonne renders from `content/`, sorted by URL.
Blog posts are left out while the blog is enabled; they are in
`all_blog_posts`. Each entry is the page's front matter plus:

- `title`: the front matter title, or the file name (the folder name for an
  `index` page)
- `url`: the URL the page is written at, in the site's URL style
  (`content/index.md` is `/`, `content/projects/index.md` is `/projects/`)
- `section`: the page's top-level folder under `content/` (`""` at the root)
- `source_path`: the page's file

A section index can list its pages without a data script:

```html
<!-- templates/projects.html, used by content/projects/index.md -->
{% for p in all_pages if p.section == 'projects' and p.url != page.url %}
  <a href="{{ p.url }}">{{ p.title }}</a>
{% endfor %}
```

### Variable Files

Variables can be defined in:

- JSON files in the `data` directory
- YAML files in the `data` directory
- CSV files in the `data` directory
- Python scripts in the `scripts` directory

### Variables in Content (Jinja)

Content files (Markdown and HTML pages) can be rendered through Jinja before
Markdown conversion, giving you variables, loops, conditionals, filters, and
`{% include %}` right inside your content. It's opt-in:

```yaml
content:
  render_jinja: true    # site-wide
```

or per file, in front matter (this overrides the site setting either way):

```yaml
---
title: My Post
jinja: true
---
```

Then:

```markdown
The year is {{ year }} and this site has {{ all_blog_posts | length }} posts.

{% for member in team_members %}
- **{{ member.name }}** — {{ member.role }}
{% endfor %}
```

Notes:

- Content rendering does **not** autoescape (your content becomes markdown
  source), so HTML-bearing variables insert as-is — no `| safe` needed here,
  unlike in `.html` templates.
- Files with literal `{{` in code samples: leave Jinja off for that file
  (`jinja: false`) or wrap the sample in `{% raw %}...{% endraw %}`.
- The old `{+}{variable}` / `{-}{variable}` substitution syntax and
  `{p}{# ... #}` embedded Python blocks have been removed (they were never
  functional in the current pipeline); the build warns if it finds those
  markers in your content.

### Python Data Sources

You can create Python scripts to generate dynamic data:

```python
# scripts/team.py
from sonne.script_api import sonne_var

# Generate team data
team_members = [
    {'name': 'John Doe', 'role': 'Developer', 'bio': 'Lorem ipsum...'},
    {'name': 'Jane Smith', 'role': 'Designer', 'bio': 'Lorem ipsum...'}
]

# Make it available as a global variable
sonne_var('team_members', team_members)
```

Then access in templates:

```html
<div class="team">
    {% for member in team_members %}
    <div class="member">
        <h3>{{ member.name }}</h3>
        <p class="role">{{ member.role }}</p>
        <p>{{ member.bio }}</p>
    </div>
    {% endfor %}
</div>
```

Every `*.py` directly in `scripts/` runs on each build, in alphabetical order; files whose names start with `_` are skipped (use them for shared helpers). Scripts are trusted code: see [Security](#security).

A script named `footer.py`, placed in `data/`, your `paths.data` folder, or `scripts/`, can set custom footer HTML with `sonne_var('footer_custom', '<p>...</p>')`. The first one found runs (once), and its value is marked HTML-safe and exposed as `site.footer.custom`.

### Script API

Scripts talk to Sonne through seven functions in `sonne.script_api`. Import them, so your editor, Pylance/pyright and ruff know where they come from (Sonne ships type hints):

```python
from sonne.script_api import (
    dither_image, get_post, get_variable, sonne_config, sonne_filter, sonne_global, sonne_var,
)
```

| Function | What it does |
|----------|--------------|
| `sonne_var(name, value)` | Publishes a variable to every template and to content Jinja, as `{{ name }}` and `{{ site.name }}`. A name that matches a site config or data-file key replaces it, with a warning. |
| `get_post(slug=None, tag=None)` | Returns a blog post of this build (a dict with title, url, date, tags, excerpt, ...) by slug, or the newest one with a tag; `None` if there is none. |
| `sonne_filter(name, fn)` | Registers a Jinja filter: `{{ value \| name }}`. |
| `sonne_global(name, value)` | Registers a Jinja global value or function: `{{ name }}`, `{{ name(...) }}`. |
| `sonne_config(*keys, default=None)` | Reads the site's configuration (your config file merged over the defaults), e.g. `sonne_config("site", "base_url")`; one key returns a whole section. Returns `default` when the key is not set. The result is a copy, so changing it does not affect the build. |
| `get_variable(name, default=None)` | Reads anything templates can see: `all_pages`, `all_blog_posts`, `tags`, data files, site config values, and variables set by scripts that ran earlier (scripts run in file-name order). Returns `default` when there is no such variable. The result is a copy; large values such as `all_blog_posts` (which includes rendered content) are copied on every call, so call it once and keep the result. |
| `dither_image(image)` | Dithers a Pillow image with the site's `images.dither_*` settings and returns the result, ready to save as PNG. For images a script fetches or generates itself; resize first if needed. |

Use `sonne_config` rather than opening `sonne.yaml` yourself: it is the configuration of the build that is running (the right file even with `sonne build -p other-site`, with defaults and deprecated-key renames applied).

```python
# scripts/weather.py
from sonne.script_api import sonne_config, sonne_var

city = sonne_config("site", "weather", "city", default="Berlin")
sonne_var("weather_city", city)
```

```python
# scripts/projects.py: the three newest pages under content/projects/
from sonne.script_api import get_variable, sonne_var

pages = get_variable("all_pages", [])
projects = [p for p in pages if p["section"] == "projects" and p["url"] != "/projects/"]
sonne_var("recent_projects", sorted(projects, key=lambda p: p.get("date", ""), reverse=True)[:3])
```

The functions work only while Sonne runs the script during `sonne build` or `sonne serve` (including from helper modules the script calls). Anywhere else, for example when you run the script with plain `python`, they raise `RuntimeError`. Older scripts that call them without importing keep working: Sonne still provides the same names as globals, but the import is the recommended form.

## Image Processing

### Automatic Image Optimization

Sonne automatically processes images in your content directory:

- Resizes images to configured dimensions
- Converts to multiple formats (WebP, PNG, etc.)
- Optimizes for web delivery
- Optional dithering for artistic effect

### Configuration

```yaml
images:
  dither: false
  optimize: true
  formats:
    - webp
    - png
  sizes:
    - 1200  # Large
    - 800   # Medium
    - 400   # Small
  dither_method: bayer
```

All image settings are listed in the [Configuration Reference](#images).

### Dithered/Original Toggle

With `images.dither: true`, readers can switch each dithered image back to its original:

- **Blog post images** get this automatically. Each one is wrapped in a `<figure>` with a "view original" button, and the styles and script are added to the page.
- **Other images** (pages, and anything under `static/images/`) are handled by the core assets Sonne writes to `/css/dithering.css` and `/js/dithering.js`. The bundled templates don't include them, so add them to your base template:

  ```html
  {% if dithering_enabled %}
  <link rel="stylesheet" href="/css/dithering.css">
  <script src="/js/dithering.js" defer></script>
  {% endif %}
  ```

  The script adds a toggle to every same-origin, non-SVG image outside blog figures. The dithered image is the one at the image's URL, and its original is expected next to it with an `_original` suffix (`images/logo.png` → `images/logo_original.png`, `photo_800.webp` → `photo_800_original.webp`). Sonne writes those originals for images under `static/images/` and for resized content images. To render the same markup on the server instead, use the `process_image` filter: `{{ "/images/logo.png" | process_image("Logo") }}`.

### Usage in Templates

```html
<picture>
    <source srcset="/assets/images/photo_800.webp" type="image/webp">
    <source srcset="/assets/images/photo_800.png" type="image/png">
    <img src="/assets/images/photo_800.png" alt="Description" loading="lazy">
</picture>
```

## Deployment

After building your site, the generated static files in the `output` directory can be deployed to any web server or hosting service:

### URL Configuration

`url_style` decides how pages are written and linked:

| Style | `about.md` is written to | and linked as |
|-------|--------------------------|---------------|
| `clean` | `about/index.html` | `/about` |
| `directory` | `about/index.html` | `/about/` |
| `html` | `about.html` | `/about.html` |

It can be one style for everything (`url_style: clean`), or one per environment:

```yaml
url_style:
  prod: clean       # the default environment
  dev: directory    # used with --dev
```

The `environment` setting picks the entry (default `prod`; custom names work when `url_style` has an entry for them). Both `sonne build` and `sonne serve` use the configured environment, so a plain `sonne serve` previews the production settings; add `--dev` to either command to use the `dev` settings instead.

For `clean` links (`/about`) your web server must serve `about/index.html` for `/about`; most static hosts do this already. With Nginx, for example:

```
location / {
    try_files $uri $uri/ $uri.html =404;
}
```

### Basic Hosting Options

- **GitHub Pages**: Push your output directory to a GitHub repository
- **Netlify**: Connect your repository or upload the output directory
- **Vercel**: Similar to Netlify with simple deployment options
- **Traditional Hosting**: FTP upload to any web host

### Example: GitHub Pages Deployment

1. Build your site: `sonne build`
2. Copy contents of the `output` directory to your GitHub Pages repository
3. Push to GitHub

## Advanced Usage

### Custom Markdown Extensions

To use additional Markdown extensions, modify the `template_processor.py` file:

```python
self.markdown_extensions = [
    'markdown.extensions.meta',
    'markdown.extensions.tables',
    'markdown.extensions.fenced_code',
    'markdown.extensions.toc',
    'markdown.extensions.smarty',
    # Add custom extensions here
]
```

### Custom Jinja Filters and Functions (from your site's scripts)

Data scripts can register real Python callables that become available in
every template — and, with `content.render_jinja`, in every content file.
No need to touch Sonne's source:

```python
# scripts/tools.py
from datetime import datetime

from sonne.script_api import sonne_filter, sonne_global

def read_time(html):
    words = len(html.split())
    return f"{max(1, round(words / 220))} min read"

sonne_filter('shout', lambda s: str(s).upper())   # {{ title | shout }}
sonne_global('read_time', read_time)              # {{ read_time(content) }}
sonne_global('built_at', datetime.now().strftime('%Y-%m-%d'))
```

Filters and globals that would shadow a built-in name are ignored with a
warning. This replaces the removed embedded-Python (`{p}{#...#}`) feature:
your Python lives in proper `.py` files (testable, lintable, full imports)
instead of inside markdown.

## Command Reference

### Create a new site

```bash
sonne new -p PATH -t TEMPLATE -n NAME [-f]
```

Options:

- `-p, --path`: Where to create the site (default: current directory)
- `-t, --template`: Template to use (solar, blog, portfolio, minimal)
- `-n, --name`: Site name
- `-f, --force`: Overwrite existing files

### Build the site

```bash
sonne build [-p PATH] [-c CONFIG] [--clean] [--skip-images] [--skip-cache]
            [--dev] [--no-progress] [--perf] [--a11y-strict] [--yes]
```

Options:

- `-p, --path`: Site directory (default: current directory)
- `-c, --config`: Path to config file
- `--clean`: Clean output directory before building
- `--skip-images`: Skip image processing
- `--skip-cache`: Ignore cache and rebuild everything
- `--dev`: Build for the development environment (dev url_style)
- `--no-progress`: Disable progress output
- `--perf`: Show a detailed performance breakdown after the build
- `--a11y-strict`: Fail the build on accessibility issues, as with `build.accessibility_checks: error` (for CI)
- `-y, --yes`: Continue past confirmation prompts (for CI)

### Serve the site

```bash
sonne serve [-p PATH] [--port PORT] [--host HOST] [--browser/--no-browser] [--watch/--no-watch]
            [--dev]
```

Options:

- `-p, --path`: Site directory (default: current directory)
- `--port`: Port to serve on (default: 8000)
- `--host`: Host to serve on (default: localhost)
- `--browser/--no-browser`: Open in browser (default: open)
- `--watch/--no-watch`: Watch for changes (default: watch)
- `--dev`: Serve the development environment (the `dev` settings, e.g. `url_style.dev`), like `sonne build --dev`

With `--watch`, a running server rebuilds your site on every change, but it keeps running the Sonne code it started with. If Sonne itself is upgraded or edited meanwhile, the next rebuild warns you to restart `sonne serve`.

### Update an old config file

```bash
sonne migrate [-p PATH] [-c CONFIG] [--write]
```

Renames deprecated keys to their replacements (e.g. `images.max_workers` → `images.parallel_workers`) and removes keys that no longer exist or have no effect (e.g. `build.statistics`, `security.csp`). Sonne keeps accepting those keys, with a warning, until they are removed for good; `migrate` makes the warnings go away.

It prints each change and a diff. Nothing is written unless you pass `--write`; then the original is kept next to it as `sonne.yaml.bak` (or `.bak.1`, `.bak.2`, ... if a backup already exists).

- YAML configs are edited in place, so comments and layout are kept. If a file can't be edited that way (for example, a section written in `{flow: style}`), Sonne rewrites the whole file instead and says clearly that comments and formatting will be lost, so you can review the diff or edit the listed keys by hand.
- JSON configs are rewritten with 2-space indentation.

Options:

- `-p, --path`: Site directory (default: current directory); only the config file in that directory is migrated
- `-c, --config`: Migrate this config file instead
- `--write`: Apply the changes (default: dry run)

## Troubleshooting

### Common Issues

1. **Missing dependencies**

   - Ensure you have all required packages installed
   - For image processing, make sure Pillow is installed: `pip install Pillow`
2. **Template not found**

   - Check the template path in your configuration
   - Ensure template files have the correct names
3. **Live reloading not working**

   - Install the watchdog package: `pip install watchdog`
4. **Image processing errors**

   - Ensure Pillow is properly installed
   - Check if source images are valid

### Logging

Increase verbosity for more detailed logs (debug level):

```bash
sonne build -v
```

## Accessibility

Sonne aims for sites that meet [WCAG 2.2](https://www.w3.org/TR/WCAG22/) level AA. It can't guarantee that on its own: much of accessibility depends on your content, your templates and your CSS. It does build accommodations in where it can and checks what a program can check.

### Build-time checks

Every build checks the pages it wrote for machine-detectable failures and reports them per page:

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

Elements hidden from assistive technology (`aria-hidden="true"`, `hidden`) are skipped. Each finding names the element, the problem and how to fix it. Long reports are capped (10 pages, 5 findings each), and the build summary always shows the totals.

`build.accessibility_checks` controls what happens:

- `warn` (default): report the findings; the build succeeds.
- `error`: report them and fail the build (exit code 1) if there are any, apart from advisories. Use this in CI, or pass `sonne build --a11y-strict` for one build.
- `off`: skip the checks.

### What the checks can't tell you

A clean report means none of the checks above failed, not that the site is accessible. No program can decide these for you:

- whether alt text actually describes the image, and link text makes sense out of context;
- colour contrast of arbitrary CSS, in every theme and state;
- reading and focus order that matches the visual layout, and visible focus indicators;
- captions and transcripts for audio and video;
- how the site works with a keyboard, a screen reader, zoom to 400% or reduced motion.

### Testing your site by hand

Check your templates and a few representative pages yourself, at least whenever you change the layout:

- Use the site with only a keyboard: every link and control is reachable, in a sensible order, with a visible focus indicator.
- Try a screen reader (NVDA or Narrator on Windows, VoiceOver on macOS and iOS, TalkBack on Android).
- Zoom to 200% and 400% and check that nothing is cut off or overlaps.
- Run an automated audit in the browser (for example Lighthouse or axe DevTools) for colour contrast and other rendering-dependent checks.

## Security

Building a Sonne site executes code:

- **Data scripts** (`scripts/*.py`) run with full process privileges on every
  build — the same trust model as Jekyll plugins or a Makefile. Only build
  sites you trust, and never point CI at untrusted site content.
- **Footer scripts**: a `footer.py` in `data/`, in your `paths.data` folder or
  in `scripts/` is executed the same way, even though the data folder
  otherwise holds only JSON, YAML and CSV. The `footer_custom` it sets is
  inserted into pages as raw HTML.
- **Content Jinja** (`content.render_jinja`) makes content files templates.
  Jinja is not a security boundary — treat content authors as trusted, the
  same as script authors. There is no embedded-Python-in-content feature
  (the old `{p}{#...#}` blocks and `security.allow_embedded_python` flag
  were removed).

## Contributing

Contributions to Sonne are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)
for setup, testing, and PR guidelines, and [docs/BACKLOG.md](docs/BACKLOG.md)
for issue-ready improvement ideas. Ways you can contribute:

1. Report bugs and feature requests on GitHub
2. Submit pull requests with bug fixes and improvements
3. Create and share templates
4. Improve documentation

### Development Setup

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
3. Run tests:
   ```bash
   pytest
   ```

## License

Sonne is licensed under the MIT License. See the LICENSE file for details.
