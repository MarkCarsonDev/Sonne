# Sonne - A Minimalist Static Site Generator

Sonne is a lightweight, environmentally-conscious static site generator designed to create websites with minimal resource usage and environmental impact.

![Sonne Logo](https://raw.githubusercontent.com/MarkCarsonDev/Sonne/main/docs/sonne-logo.png)

> "Sonne" is the German word for "sun" - reflecting the project's goal to be as sustainable as possible, just like solar energy.

## Features

- **Minimalist Approach**: Generate lean, efficient websites that load quickly and consume minimal resources.
- **Blog Support**: Built-in blog functionality with posts, tags, categories, and pagination.
- **Image Optimization**: Automatically optimize and dither images to reduce file size while maintaining acceptable quality.
- **Variable System**: Simple yet powerful variable substitution for dynamic content generation.
- **Markdown Support**: Write content in Markdown with front matter for easy content creation.
- **Multiple Templates**: Choose from different templates or create your own.
- **Dark/Light Themes**: Built-in support for theme switching to improve user experience.
- **Keyboard Navigation**: Navigate your site using keyboard shortcuts.

## Philosophy

The web has become increasingly resource-intensive, with many sites requiring significant server resources and bandwidth. Sonne takes a different approach, focusing on:

- **Minimal Footprint**: Generate static sites that require minimal server resources.
- **Environmental Consciousness**: Reduce energy consumption by optimizing all assets.
- **Speed and Efficiency**: Create fast-loading sites that work well even on slower connections.
- **Simplicity**: Keep things simple and straightforward, avoiding complexity where possible.

## Installation

```bash
# Install using pip
pip install sonne
```

## Quick Start

```bash
# Create a new site
sonne new --path my-site

# Change to the site directory
cd my-site

# Build the site
sonne build

# Serve locally for development
sonne serve
```

Your site will be available at http://localhost:8000.

## Creating Content

### Pages

Add HTML or Markdown files to your `content` directory. Files with front matter will be processed:

```markdown
---
title: About
template: page.html
---

# About This Site

This is a sample page created with Sonne.
```

### Blog Posts

Add Markdown files to your `content/blog` directory with appropriate front matter:

```markdown
---
title: My First Post
date: 2025-04-01
author: Your Name
description: A brief description
tags:
  - sample
  - post
categories:
  - tutorial
---

# My First Post

This is my first blog post with Sonne.
```

## Image Handling

When you include images in your content, Sonne can automatically optimize them and provide a toggle for users to switch between optimized and original versions:

```markdown
![Alt text](image.jpg "Optional title")
```

Images will be processed according to your configuration settings in `sonne.yaml`.

## Variable System

Sonne provides two types of variables:

1. **Sonne Variables**: Available site-wide using the `{+}{variable_name}` syntax.
2. **Mond Variables**: Specific to blog posts using the `{-}{variable_name}` syntax.

Variables can be defined in your configuration file, data files, or script files.

## Configuration

Sonne uses a YAML configuration file (`sonne.yaml`) for site settings. Here's a sample configuration:

```yaml
site:
  title: "My Sonne Site"
  base_url: "https://example.com"
  description: "A site built with Sonne"
  author: "Your Name"

paths:
  content: "content"
  output: "output"
  static: "static"
  templates: "templates"

blog:
  enabled: true
  posts_per_page: 10
  url_pattern: "{year}/{month}/{day}/{slug}"

images:
  dither: true
  optimize: true
  formats: 
    - "webp"
    - "png"
  sizes:
    - 1200
    - 800
    - 400
```

## Commands

Sonne provides several commands to help you work with your site:

- `sonne new`: Create a new site from a template
- `sonne build`: Build the site
- `sonne serve`: Start a local development server
- `sonne --help`: Show help information

## Templates

Sonne comes with several built-in templates:

- `minimal`: A clean, minimalist template
- `blog`: A blog-focused template
- `portfolio`: A template designed for portfolios

You can also create your own templates or modify the existing ones.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Environmental Impact

A website built with Sonne typically uses less than half the resources of a comparable site built with a typical CMS or JavaScript framework. By choosing Sonne, you're making a small but meaningful contribution to a more sustainable web.

---

Built with ☀️ by [Mark Carson](https://github.com/MarkCarsonDev)