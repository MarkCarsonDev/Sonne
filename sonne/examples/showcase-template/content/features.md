---
title: Sonne Features
template: page.html
description: Explore the powerful features of the Sonne static site generator
---
# Sonne Features

Sonne combines simplicity with power to create an efficient static site generator that works for a wide range of projects. Here's a detailed overview of Sonne's key features.

## Content Management

### Markdown-based Content

Write content in Markdown with front matter for metadata and easy formatting.

```markdown
---
title: My First Post
date: 2025-04-01
tags:
  - welcome
  - getting started
---

# Welcome to My Site

This is my first post using **Sonne**!
```

### Front Matter

Define metadata for your content using YAML or JSON front matter.

```yaml
---
title: About Us
template: page.html
description: Learn about our company
featured_image: /images/team.jpg
---
```

### Directory Structure

Intuitive content organization that maps directly to your site structure.

```
content/
├── index.md        # Home page
├── about.md        # About page
└── blog/           # Blog directory
    ├── post-1.md   # First post
    └── post-2.md   # Second post
```

## Templating System

### Jinja2 Templates

Flexible and powerful templating with Jinja2.

```html
<!DOCTYPE html>
<html>
<head>
    <title>{% if page.title %}{{ page.title }} - {% endif %}{{ site.title }}</title>
</head>
<body>
    <main>
        {{ content }}
    </main>
</body>
</html>
```

### Template Inheritance

Create reusable layouts with template inheritance.

```html
{% extends "base.html" %}

{% block content %}
<article>
    <h1>{{ page.title }}</h1>
    {{ content }}
</article>
{% endblock %}
```

### Template Functions & Filters

Extend templates with custom functions and filters.

```html
<p>Published: {{ page.date | date('%B %d, %Y') }}</p>
<div>{{ content | markdown }}</div>
```

## Blog Engine

### Post Management

Built-in blog functionality with automatic post listing and pagination.

### Categories & Tags

Organize posts with categories and tags, with automatic archive pages.

### RSS Feed

Automatic RSS feed generation for your blog.

### Pagination

Paginated blog listing pages with customizable posts per page.

## Image Processing

### Automatic Resizing

Generate multiple sizes of images for responsive design.

```html
<picture>
    <source srcset="image_800.webp" type="image/webp">
    <source srcset="image_800.jpg" type="image/jpeg">
    <img src="image_800.jpg" alt="Description">
</picture>
```

### Format Conversion

Convert images to modern formats like WebP for better performance.

### Image Optimization

Automatically optimize images for web delivery.

### Dithering Effects

Apply dithering for artistic effect or size reduction.

## Data Management

### Multiple Data Sources

Load data from JSON, YAML, CSV, and Python sources.

### JSON & YAML Files

Define structured data in JSON or YAML files.

```json
{
  "team": [
    {"name": "Alice", "role": "Developer"},
    {"name": "Bob", "role": "Designer"}
  ]
}
```

### Python Data Generation

Create dynamic data with Python scripts.

```python
# The sonne_var function will be injected by Sonne at runtime
# Ignore any linting warnings

# Generate data
stats = {
    "posts": 42,
    "words": 12500,
    "build_time": "1.2s"
}

# Make it available in templates
sonne_var("stats", stats)
```

### Variables in Content

Use variables directly in content (Jinja, opt-in via `content.render_jinja`).

```markdown
There are {{ stats.posts }} posts on this site.
```

## Performance Features

### Fast Build Times

Efficient build process with minimal overhead.

### Caching System

Smart caching to avoid unnecessary processing.

### Minification

Automatic minification of HTML, CSS, and JavaScript (optional).

### Optimized Output

Clean, optimized output ready for deployment.

## Development Experience

### Live Development Server

Development server with automatic reloading on changes.

```bash
sonne serve
```

### Configurable Builds

Customize the build process to suit your needs.

```bash
sonne build --clean --skip-images
```

### Detailed Logging

Helpful logs for troubleshooting and monitoring.

### Multiple Templates

Choose from several built-in templates or create your own.

```bash
sonne new -p my-site -t blog
```

## Customization

### Simple Configuration

Customize your site with a simple YAML configuration file.

```yaml
site:
  title: My Awesome Site
  base_url: https://example.com
  
blog:
  posts_per_page: 10
  
images:
  formats:
    - webp
    - jpg
```

### Plugin System

Extend functionality with plugins (coming soon).

### Custom Templates

Create and share your own templates.

### Advanced Scripting

Use Python scripts for custom functionality.

## Deployment Features

### Flexible Output

Generate static files ready for any hosting platform.

### Clean URLs

Support for clean URLs without file extensions.

### Optimized Assets

Optimized static assets for fast loading.

### Deployment Scripts

Helper scripts for common deployment targets (coming soon).

## Feature Comparison

Here's how Sonne compares to other popular static site generators:

| Feature          | Sonne    | Jekyll    | Hugo         | Gatsby     |
| ---------------- | -------- | --------- | ------------ | ---------- |
| Language         | Python   | Ruby      | Go           | JavaScript |
| Build Speed      | Fast     | Slow      | Very Fast    | Medium     |
| Image Processing | ✓       | ✗        | ✓           | ✓         |
| Templating       | Jinja2   | Liquid    | Go Templates | React      |
| Learning Curve   | Easy     | Medium    | Medium       | Steep      |
| Blog Support     | Built-in | Built-in  | Built-in     | Plugin     |
| Data Sources     | Multiple | YAML/JSON | Multiple     | GraphQL    |

## Examples in Action

### Variables in Content

```markdown
The current year is {{ year }}.
This site was last built on {{ build_time }}.
```

(See it live on the [Jinja demo page](/jinja-demo/).)

### Python from Data Scripts

```python
# scripts/tools.py
import random
sonne_global('lucky_number', lambda: random.randint(1, 100))
```

```markdown
Your lucky number is {{ lucky_number() }}.
```

### Image Dithering

![Original Image](https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=600)
*Original image*

![Dithered Image](https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=600)
*Same image with dithering applied (demonstration)*

## Ready to Try Sonne?

Get started with Sonne in just a few minutes:

```bash
pip install sonne
sonne new -p my-site -t blog
cd my-site
sonne serve
```

[Read the Getting Started Guide](/blog/2025/04/01/getting-started-with-sonne-static-site-generator/) for more detailed instructions.
