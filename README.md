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

Sonne uses a configuration file to customize your site. The configuration file can be in YAML or JSON format and should be named `sonne.yaml` or `sonne.json`.

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
  lazy_loading: true
```

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
- Custom global variables set in data files or scripts

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

# The sonne_var function will be injected by Sonne at runtime
# Ignore any linting warnings

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
  lazy_loading: true
```

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

By default, Sonne generates HTML files with the `.html` extension (e.g., `about.html`). If you prefer clean URLs without the extension (e.g., `/about/` instead of `/about.html`), you have two options:

1. **Configure URL rewriting on your web server**:

   For Nginx:

   ```
   location / {
       try_files $uri $uri.html $uri/ =404;
   }
   ```

   For Apache (.htaccess):

   ```
   RewriteEngine On
   RewriteCond %{REQUEST_FILENAME} !-f
   RewriteCond %{REQUEST_FILENAME} !-d
   RewriteCond %{REQUEST_FILENAME}.html -f
   RewriteRule ^(.*)$ $1.html [L]
   ```
2. **Manually structure your output as directories with index.html files**:

   - `/about.md` → `/about/index.html` (accessible as `/about/`)
   - This requires additional post-processing of the generated files

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
            [--dev] [--no-progress] [--perf] [--yes]
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
- `-y, --yes`: Continue past confirmation prompts (for CI)

### Serve the site

```bash
sonne serve [-p PATH] [--port PORT] [--host HOST] [--browser/--no-browser] [--watch/--no-watch]
```

Options:

- `-p, --path`: Site directory (default: current directory)
- `--port`: Port to serve on (default: 8000)
- `--host`: Host to serve on (default: localhost)
- `--browser/--no-browser`: Open in browser (default: open)
- `--watch/--no-watch`: Watch for changes (default: watch)

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

## Security

Building a Sonne site executes code:

- **Data scripts** (`scripts/*.py`) run with full process privileges on every
  build — the same trust model as Jekyll plugins or a Makefile. Only build
  sites you trust, and never point CI at untrusted site content.
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
