---
title: Creating Custom Templates
template: page.html
description: Learn how to create custom templates for your Sonne static site generator
---

# Creating Custom Templates in Sonne

One of Sonne's strengths is its flexibility when it comes to templating. This guide will walk you through the process of creating custom templates for your Sonne site.

## Template Directory Structure

A Sonne template consists of several components organized in a specific directory structure:

```
my-template/
├── static/              # Static assets
│   ├── css/             # Stylesheets
│   ├── js/              # JavaScript files
│   └── images/          # Images used by the template
├── templates/           # HTML templates (Jinja2)
│   ├── base.html        # Base template with common elements
│   ├── page.html        # Standard page template
│   ├── blog_post.html   # Blog post template
│   ├── blog_list.html   # Blog list page template
│   └── ...              # Other template files
├── content/             # Sample content
│   ├── index.md         # Homepage
│   ├── about.md         # About page
│   └── blog/            # Sample blog posts
└── sonne.yaml           # Template configuration
```

## Essential Template Files

### base.html

The `base.html` template serves as the foundation for all other templates. It typically includes:

- HTML document structure
- Head section with metadata
- Header and navigation
- Footer
- Common JavaScript and CSS

Here's a minimal example:

```html
<!DOCTYPE html>
<html lang="{{ site.language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% if page.title %}{{ page.title }} - {% endif %}{{ site.title }}</title>
    <meta name="description" content="{{ page.description | default(site.description) }}">
    <link rel="stylesheet" href="/static/css/main.css">
</head>
<body>
    <header>
        <h1><a href="/">{{ site.title }}</a></h1>
        <nav>
            <ul>
                {% for item in site.nav %}
                <li><a href="{{ item.url }}">{{ item.text }}</a></li>
                {% endfor %}
            </ul>
        </nav>
    </header>
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <p>&copy; {{ site.year }} {{ site.author }}</p>
        {% if site.footer.custom %}{{ site.footer.custom }}{% endif %}
    </footer>
    
    <script src="/static/js/main.js"></script>
</body>
</html>
```

### page.html

The `page.html` template extends the base template and is used for standard content pages:

```html
{% extends "base.html" %}

{% block content %}
<article class="page">
    <header class="page-header">
        <h1>{{ page.title }}</h1>
    </header>
    
    <div class="page-content">
        {{ content }}
    </div>
</article>
{% endblock %}
```

### blog_post.html

The `blog_post.html` template is used for individual blog posts:

```html
{% extends "base.html" %}

{% block content %}
<article class="blog-post">
    <header class="post-header">
        <h1>{{ page.title }}</h1>
        <div class="post-meta">
            <time datetime="{{ page.date_str }}">{{ page.date_formatted }}</time>
            {% if page.author %} • By {{ page.author }}{% endif %}
        </div>
    </header>
    
    {% if page.cover_img %}
    <div class="post-cover">
        <img src="{{ page.cover_img }}" alt="{{ page.title }}">
    </div>
    {% endif %}
    
    <div class="post-content">
        {{ content }}
    </div>
    
    {% if page.tags %}
    <div class="post-tags">
        <h3>Tags:</h3>
        <ul>
            {% for tag in page.tags %}
            <li><a href="/blog/tags/{{ tag | lower | replace(' ', '-') }}/">{{ tag }}</a></li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}
</article>
{% endblock %}
```

### blog_list.html

The `blog_list.html` template displays a list of blog posts with pagination:

```html
{% extends "base.html" %}

{% block content %}
<div class="blog-list">
    <header class="page-header">
        <h1>{{ page.title }}</h1>
    </header>
    
    {% for post in page.posts %}
    <article class="post-summary">
        <h2><a href="{{ post.full_url }}">{{ post.title }}</a></h2>
        <div class="post-meta">
            <time datetime="{{ post.date_str }}">{{ post.date_formatted }}</time>
        </div>
        <div class="post-excerpt">{{ post.excerpt }}</div>
        <a href="{{ post.full_url }}" class="read-more">Read More</a>
    </article>
    {% endfor %}
    
    {% if page.pagination %}
    <nav class="pagination">
        {% if page.pagination.has_prev %}
        <a href="{{ page.pagination.prev_url }}" class="prev">&larr; Previous</a>
        {% endif %}
        
        <span class="page-number">Page {{ page.pagination.current }} of {{ page.pagination.total }}</span>
        
        {% if page.pagination.has_next %}
        <a href="{{ page.pagination.next_url }}" class="next">Next &rarr;</a>
        {% endif %}
    </nav>
    {% endif %}
</div>
{% endblock %}
```

## Template Variables

When creating templates, you'll work with three main variable scopes:

1. **site**: Global site configuration from `sonne.yaml`
2. **page**: Current page metadata from front matter
3. **content**: The rendered content of the current page

Additionally, you can access:

- **all_blog_posts**: List of all blog posts (when blog is enabled)
- Custom variables defined in data files or scripts

## Template Customization Techniques

### Custom CSS and JavaScript

Include your template's CSS and JavaScript files:

```html
<link rel="stylesheet" href="/static/css/main.css">
<script src="/static/js/main.js"></script>
```

### Conditionally Loading Resources

Load CSS/JS only when needed:

```html
{% if page.css %}
<link rel="stylesheet" href="/static/css/{{ page.css }}">
{% endif %}

{% if page.js %}
<script src="/static/js/{{ page.js }}"></script>
{% endif %}
```

### Adding Custom Metadata

Support custom metadata in templates:

```html
{% if page.canonical_url %}
<link rel="canonical" href="{{ page.canonical_url }}">
{% endif %}

{% if page.robots %}
<meta name="robots" content="{{ page.robots }}">
{% endif %}
```

### Image Handling

Implement responsive images:

```html
<picture>
    <source srcset="{{ image | replace('.jpg', '_800.webp') }}" type="image/webp">
    <source srcset="{{ image | replace('.jpg', '_800.jpg') }}" type="image/jpeg">
    <img src="{{ image }}" alt="{{ alt }}" loading="lazy">
</picture>
```

## Setting Up Base Styles

Your template should include a set of base styles. Here's a starting point:

1. **Reset/Normalize**: Ensure consistent rendering across browsers
2. **Typography**: Define base font styles and sizes
3. **Layout**: Create basic grid or layout system
4. **Components**: Style common elements like buttons, cards, etc.
5. **Utilities**: Add utility classes for common needs
6. **Responsive Design**: Ensure the template works on all devices

## Sharing Your Template

To share your template with others:

1. Create a repository for your template
2. Include clear documentation on how to use it
3. Provide sample content to demonstrate the template
4. Create a screenshot to showcase the design
5. Include license information

## Template Testing

Before releasing your template, test it thoroughly:

1. **Cross-browser Testing**: Ensure it works in all major browsers
2. **Responsive Testing**: Check on different screen sizes
3. **Accessibility**: Verify WCAG compliance
4. **Performance**: Test page load times
5. **Validation**: Ensure valid HTML and CSS

## Advanced Templating Techniques

### Custom Template Filters

You can add custom Jinja2 filters to extend templating capabilities. These are defined in Python code:

```python
def word_count(text):
    return len(text.split())

# Register filter in template_processor.py
self.jinja_env.filters['word_count'] = word_count
```

Then use in templates:

```html
<p>This article contains {{ content|word_count }} words.</p>
```

### Template Includes

For reusable components, use includes:

```html
{% include "components/header.html" %}
{% include "components/pagination.html" %}
```

### Template Inheritance Chains

Create more specific template inheritance:

```
base.html
└── layout-sidebar.html
    └── page-with-sidebar.html
```

### Template Variables with Default Values

Provide defaults for optional variables:

```html
{{ page.subtitle | default('Welcome to our site') }}
```

## Conclusion

Creating custom templates gives you complete control over the design and functionality of your Sonne site. By understanding the template structure, available variables, and customization techniques, you can create unique and powerful templates that showcase your content effectively.

Remember to start simple and add complexity gradually as you become more familiar with Sonne's templating system. Happy designing!