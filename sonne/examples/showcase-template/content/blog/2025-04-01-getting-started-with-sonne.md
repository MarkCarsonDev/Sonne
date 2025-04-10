---
title: Getting Started with Sonne Static Site Generator
date: 2025-04-01
author: Sonne Developer
tags:
  - tutorial
  - beginner
  - static site
categories:
  - guides
featured: true
cover_img: /assets/images/getting-started.jpg
description: Learn how to create your first static site with Sonne, from installation to deployment.
---

# Getting Started with Sonne

Sonne is a minimalist static site generator designed to create efficient websites with minimal resource requirements. In this guide, we'll walk through setting up your first Sonne site and introduce you to its key features.

## Installation

To get started with Sonne, you'll need Python 3.8 or newer. Install Sonne using pip:

```bash
pip install sonne
```

This will install Sonne and its dependencies.

## Creating a New Site

Once installed, you can create a new site using the `new` command:

```bash
sonne new -p my-blog -t blog
```

This command creates a new site in the `my-blog` directory using the blog template. Sonne provides several templates out of the box:

- `blog`: A full-featured blog template
- `portfolio`: A template for showcasing your work
- `minimal`: A bare-bones template with minimal styling

Let's explore what's created in your new site:

```
my-blog/
├── content/        # Your content goes here
│   ├── about.md    # About page
│   ├── index.md    # Home page
│   └── blog/       # Blog posts
├── static/         # Static assets (CSS, JS, images)
├── templates/      # HTML templates
└── sonne.yaml      # Configuration file
```

## Configuration

The `sonne.yaml` file contains settings for your site. Here's a basic example:

```yaml
site:
  title: My Awesome Blog
  base_url: https://example.com
  description: A blog built with Sonne
  author: Your Name

paths:
  content: content
  output: output
  static: static
  templates: templates

blog:
  enabled: true
  posts_per_page: 10
```

You can customize these settings to match your needs.

## Creating Content

Sonne uses Markdown for content. Each page or post starts with front matter that defines metadata:

```markdown
---
title: My First Post
date: 2025-04-01
tags:
  - sonne
  - tutorial
---

This is my first post using Sonne!
```

Place blog posts in the `content/blog` directory and regular pages in the `content` directory.

## Building Your Site

To build your site, run:

```bash
cd my-blog
sonne build
```

This generates your site in the `output` directory. To preview it locally:

```bash
sonne serve
```

This starts a development server at `http://localhost:8000` with live reloading.

## Image Optimization

Sonne automatically processes and optimizes images in your content. For example, if you include an image:

```markdown
![My Image](/assets/images/photo.jpg)
```

Sonne will:

1. Create multiple sizes (1200px, 800px, 400px by default)
2. Convert to multiple formats (WebP, PNG by default)
3. Optimize for web delivery

In your templates, you can use responsive images:

```html
<picture>
    <source srcset="/assets/images/photo_800.webp" type="image/webp">
    <source srcset="/assets/images/photo_800.png" type="image/png">
    <img src="/assets/images/photo_800.png" alt="My Image" loading="lazy">
</picture>
```

## Using Data Sources

Sonne can use data from various sources:

### JSON Files

Create a JSON file in the `data` directory:

```json
{
  "team": [
    {"name": "Alice", "role": "Developer"},
    {"name": "Bob", "role": "Designer"}
  ]
}
```

### Python Scripts

Create Python scripts in the `scripts` directory:

```python
def sonne_var(key, value):
    # This function is provided by Sonne
    pass

# Generate data
projects = [
    {"title": "Project 1", "url": "/projects/1/"},
    {"title": "Project 2", "url": "/projects/2/"}
]

# Make it available in templates
sonne_var("projects", projects)
```

Then use this data in your templates:

```html
<div class="team">
    {% for member in team %}
    <div class="member">
        <h3>{{ member.name }}</h3>
        <p>{{ member.role }}</p>
    </div>
    {% endfor %}
</div>
```

## Variable Substitution

You can also use variables directly in your Markdown content:

```markdown
The current year is {+}{site.year}.
My name is {+}{site.author}.
```

## Deploying Your Site

After building your site, the files in the `output` directory can be deployed to any web hosting provider:

1. GitHub Pages
2. Netlify
3. Vercel
4. Any traditional web host

For example, to deploy to GitHub Pages:

1. Create a GitHub repository
2. Build your site: `sonne build`
3. Push the contents of the `output` directory to your repository

## Next Steps

Now that you have a basic understanding of Sonne, explore these advanced features:

1. Custom templates and themes
2. Blog taxonomies (tags, categories)
3. Image dithering effects
4. Python data processing
5. Extended Markdown features

Happy building with Sonne!

## Example: Using Embedded Python

Sonne allows you to embed Python code in your content:

{p}{# 
import random
result = f"This number was generated by Python: {random.randint(1, 100)}"
#}

## Example: Responsive Images

Here's how Sonne handles responsive images:

![Landscape](https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1200)

The above image will be automatically optimized and converted to multiple formats and sizes.

## Example: Syntax Highlighting

Sonne supports code syntax highlighting:

```python
def hello_world():
    print("Hello, Sonne!")
    
if __name__ == "__main__":
    hello_world()
```

## Conclusion

Sonne makes creating static sites straightforward while providing powerful features for more advanced users. Its minimalist approach ensures your sites remain fast and efficient.

Start building with Sonne today and experience the perfect balance of simplicity and capability in static site generation!