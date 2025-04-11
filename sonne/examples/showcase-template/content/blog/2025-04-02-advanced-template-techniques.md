---
title: Advanced Template Techniques in Sonne
date: 2025-04-02
author: Sarah Chen
tags:
  - templates
  - advanced
  - design
categories:
  - tutorials
featured: true
cover_img: /assets/images/advanced-templates.jpg
description: Take your Sonne templates to the next level with advanced techniques and best practices.
---

# Advanced Template Techniques in Sonne

Sonne's templating system, built on Jinja2, offers powerful capabilities for creating sophisticated layouts and dynamic content presentation. This guide explores advanced templating techniques to help you build more flexible and maintainable sites.

## Template Inheritance Patterns

While basic template inheritance is straightforward, there are several patterns you can use to create more sophisticated template structures.

### Multi-level Inheritance

Instead of inheriting directly from `base.html`, create intermediate templates for different section types:

```
base.html                   # Site-wide structure
├── layout-sidebar.html     # Layout with sidebar
│   ├── page-with-toc.html  # Page with table of contents
│   └── blog-sidebar.html   # Blog with sidebar
└── layout-full.html        # Full-width layout
    ├── portfolio.html      # Portfolio layout
    └── landing-page.html   # Landing page layout
```

Example of a multi-level template:

```html
{# layout-sidebar.html #}
{% extends "base.html" %}

{% block content %}
<div class="container with-sidebar">
    <main class="main-content">
        {% block main_content %}{% endblock %}
    </main>
    
    <aside class="sidebar">
        {% block sidebar %}
        <div class="default-sidebar">
            <h3>Navigation</h3>
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/about/">About</a></li>
                <li><a href="/blog/">Blog</a></li>
            </ul>
        </div>
        {% endblock %}
    </aside>
</div>
{% endblock %}
```

Then, create specific templates that extend this layout:

```html
{# blog-sidebar.html #}
{% extends "layout-sidebar.html" %}

{% block sidebar %}
<div class="blog-sidebar">
    <div class="recent-posts">
        <h3>Recent Posts</h3>
        <ul>
            {% for post in all_blog_posts[:5] %}
            <li><a href="{{ post.full_url }}">{{ post.title }}</a></li>
            {% endfor %}
        </ul>
    </div>
    
    <div class="categories">
        <h3>Categories</h3>
        <ul>
            {% for category_name, category_data in categories.items() %}
            <li><a href="/blog/categories/{{ category_data.slug }}/">{{ category_name }}</a></li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endblock %}
```

This approach allows for more specific template customization while maintaining a consistent structure.

## Template Includes and Macros

### Reusable Components with Includes

For repeating elements, create separate template files and include them:

```html
{# _header.html #}
<header class="site-header">
    <div class="logo">
        <a href="/"><img src="/images/logo.svg" alt="{{ site.title }}"></a>
    </div>
    
    <nav class="main-nav">
        <ul>
            {% for item in site.nav %}
            <li><a href="{{ item.url }}" {% if page.url == item.url %}class="active"{% endif %}>{{ item.text }}</a></li>
            {% endfor %}
        </ul>
    </nav>
</header>
```

Then include it in your base template:

```html
{% include "_header.html" %}
```

### Powerful Macros

Macros are like functions in Jinja2 templates, allowing you to create reusable UI components with parameters:

```html
{# _macros.html #}
{% macro card(title, content, url='#', image=none, tags=[]) %}
<div class="card">
    {% if image %}
    <div class="card-image">
        <img src="{{ image }}" alt="{{ title }}">
    </div>
    {% endif %}
    
    <div class="card-content">
        <h3 class="card-title">{{ title }}</h3>
        <div class="card-body">{{ content }}</div>
        
        {% if tags %}
        <div class="card-tags">
            {% for tag in tags %}
            <span class="tag">{{ tag }}</span>
            {% endfor %}
        </div>
        {% endif %}
        
        <a href="{{ url }}" class="card-link">Read more</a>
    </div>
</div>
{% endmacro %}
```

Import and use the macro in your templates:

```html
{% import "_macros.html" as macros %}

<div class="card-grid">
    {% for post in featured_posts %}
    {{ macros.card(
        title=post.title,
        content=post.excerpt,
        url=post.full_url,
        image=post.cover_img,
        tags=post.tags
    ) }}
    {% endfor %}
</div>
```

## Advanced Conditional Logic

### Complex Conditions

Jinja2 allows for sophisticated conditional logic in templates:

```html
{% if page.title and (page.featured or page.cover_img) %}
    <!-- Display featured header -->
{% elif page.title and page.date %}
    <!-- Display blog post header -->
{% elif page.title %}
    <!-- Display standard page header -->
{% endif %}
```

### Using Ternary Operators

For simple conditionals, use the inline ternary operator:

```html
<span class="status {{ 'active' if page.status == 'published' else 'draft' }}">
    {{ page.status|title }}
</span>
```

## Template Variables with Filters

### Default Values and Fallbacks

Provide default values for optional variables:

```html
{{ page.subtitle | default('Welcome to our site') }}
```

Create fallback chains:

```html
{{ page.meta_description | default(page.excerpt) | default(site.description) }}
```

### Custom Filters for Content Transformation

Sonne allows you to create custom Jinja2 filters in Python. Here's an example implementation:

```python
def truncate_words(text, length=30):
    """Truncate text to a specified number of words."""
    words = text.split()
    if len(words) <= length:
        return text
    return ' '.join(words[:length]) + '...'

# Register filter in template_processor.py
self.jinja_env.filters['truncate_words'] = truncate_words
```

Then use it in templates:

```html
<p class="excerpt">{{ post.content | truncate_words(50) }}</p>
```

## Dynamic Layouts Based on Content

### Content-Aware Layouts

Adapt your layout based on content characteristics:

```html
<div class="content-area {% if content|word_count > 1000 %}long-form{% endif %}">
    {{ content }}
</div>
```

### Featured Content Detection

Create special layouts for featured content:

```html
{% set featured_posts = [] %}
{% for post in all_blog_posts %}
    {% if post.featured %}
        {% set featured_posts = featured_posts + [post] %}
    {% endif %}
{% endfor %}

{% if featured_posts %}
<section class="featured-posts">
    <h2>Featured Content</h2>
    <div class="featured-grid">
        {% for post in featured_posts %}
        <!-- Display featured post -->
        {% endfor %}
    </div>
</section>
{% endif %}
```

## SEO Optimization in Templates

### Dynamic Meta Tags

Create comprehensive meta tags based on page content:

```html
<!-- Basic Meta Tags -->
<meta name="description" content="{{ page.description | default(site.description) }}">
<meta name="keywords" content="{{ page.keywords | default(site.keywords) | join(', ') }}">
<meta name="author" content="{{ page.author | default(site.author) }}">

<!-- Open Graph Meta Tags -->
<meta property="og:title" content="{{ page.title }} - {{ site.title }}">
<meta property="og:description" content="{{ page.description | default(site.description) }}">
<meta property="og:type" content="{% if page.url == '/' %}website{% else %}article{% endif %}">
<meta property="og:url" content="{{ site.base_url }}{{ page.url }}">
{% if page.cover_img %}
<meta property="og:image" content="{{ site.base_url }}{{ page.cover_img }}">
{% endif %}

<!-- Twitter Card Meta Tags -->
<meta name="twitter:card" content="{% if page.cover_img %}summary_large_image{% else %}summary{% endif %}">
<meta name="twitter:title" content="{{ page.title }} - {{ site.title }}">
<meta name="twitter:description" content="{{ page.description | default(site.description) }}">
{% if page.cover_img %}
<meta name="twitter:image" content="{{ site.base_url }}{{ page.cover_img }}">
{% endif %}
```

### Structured Data

Add JSON-LD structured data for better search engine understanding:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "{% if page.url == '/' %}WebSite{% elif 'blog' in page.url %}BlogPosting{% else %}WebPage{% endif %}",
  "headline": "{{ page.title }}",
  "description": "{{ page.description | default(site.description) }}",
  "url": "{{ site.base_url }}{{ page.url }}"
  {% if page.date %},
  "datePublished": "{{ page.date_str }}",
  "dateModified": "{{ page.modified | default(page.date_str) }}"
  {% endif %}
  {% if page.author %},
  "author": {
    "@type": "Person",
    "name": "{{ page.author }}"
  }
  {% endif %}
  {% if page.cover_img %},
  "image": "{{ site.base_url }}{{ page.cover_img }}"
  {% endif %}
}
</script>
```

## Handling External Data

### Working with API Data in Templates

If you're using Python scripts to fetch external data:

```python
import requests

# The sonne_var function will be injected by Sonne at runtime
# Ignore any linting warnings

try:
    response = requests.get('https://api.example.com/data')
    if response.status_code == 200:
        api_data = response.json()
        sonne_var('api_data', api_data)
    else:
        sonne_var('api_data', None)
        sonne_var('api_error', f"API Error: {response.status_code}")
except Exception as e:
    sonne_var('api_data', None)
    sonne_var('api_error', f"Exception: {str(e)}")
```

Then in your template:

```html
<div class="api-data">
    {% if api_data %}
        <h2>Data from API</h2>
        <ul>
            {% for item in api_data.items %}
            <li>{{ item.name }}: {{ item.value }}</li>
            {% endfor %}
        </ul>
    {% elif api_error %}
        <div class="error-message">{{ api_error }}</div>
    {% else %}
        <div class="loading">Loading data...</div>
    {% endif %}
</div>
```

## Responsive Design in Templates

### Responsive Images

Create truly responsive images with multiple sources:

```html
<picture>
    <!-- Mobile portrait -->
    <source media="(max-width: 480px)"
            srcset="{{ image | replace('.jpg', '_400.webp') }}" type="image/webp">
    
    <!-- Tablet portrait -->
    <source media="(max-width: 768px)"
            srcset="{{ image | replace('.jpg', '_800.webp') }}" type="image/webp">
    
    <!-- Desktop -->
    <source srcset="{{ image | replace('.jpg', '_1200.webp') }}" type="image/webp">
    
    <!-- Fallback -->
    <img src="{{ image | replace('.jpg', '_800.jpg') }}" alt="{{ alt }}" loading="lazy">
</picture>
```

### Responsive Layout Control

Use template logic to adapt layouts for different screen sizes:

```html
<div class="content-grid {% if page.layout_type == 'wide' %}wide-grid{% endif %}">
    <!-- For mobile, fixed 1-column layout regardless of page.layout_type -->
    <div class="mobile-only">
        <div class="single-column">
            {{ content }}
        </div>
    </div>
    
    <!-- For tablets and desktops -->
    <div class="desktop-only">
        {% if page.layout_type == 'columns' %}
        <div class="multi-column">
            <!-- Column layout -->
        </div>
        {% else %}
        <div class="standard-layout">
            {{ content }}
        </div>
        {% endif %}
    </div>
</div>
```

## Performance Optimization

### Preloading Critical Resources

Add preload hints for critical resources:

```html
<link rel="preload" href="/fonts/main-font.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/css/critical.css" as="style">
<link rel="preload" href="/js/nav.js" as="script">
```

### Critical CSS Inlining

Inline critical CSS for faster initial rendering:

```html
<style>
    /* Critical CSS for above-the-fold content */
    body {
        font-family: sans-serif;
        margin: 0;
        padding: 0;
    }
    .header {
        background-color: #fff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 1rem;
    }
    /* More critical styles... */
</style>
```

### Deferred Loading

Defer non-critical JavaScript:

```html
<script src="/js/main.js" defer></script>
```

## Debugging Templates

### Debug Output

Add debug output when developing:

```html
{% if site.debug %}
<div class="debug-info">
    <h3>Debug Information</h3>
    <pre>{{ page | pprint }}</pre>
</div>
{% endif %}
```

### Conditional Debugging

Show detailed information conditionally:

```html
<!-- Add ?debug=1 to URL to see this -->
{% if request.args.get('debug') == '1' %}
<div class="debug-panel">
    <h4>Template Context</h4>
    <pre>{{ _context | pprint }}</pre>
</div>
{% endif %}
```

## Accessibility Enhancements

### ARIA Attributes

Add ARIA attributes for better accessibility:

```html
<nav aria-label="Main navigation">
    <button class="menu-toggle" aria-expanded="false" aria-controls="main-menu">
        <span class="sr-only">Toggle menu</span>
        <span class="icon"></span>
    </button>
    
    <ul id="main-menu" aria-labelledby="main-menu-toggle">
        {% for item in site.nav %}
        <li><a href="{{ item.url }}" {% if page.url == item.url %}aria-current="page"{% endif %}>{{ item.text }}</a></li>
        {% endfor %}
    </ul>
</nav>
```

### Skip Links

Add skip links for keyboard navigation:

```html
<a href="#main-content" class="skip-link">Skip to main content</a>

<!-- Later in the page -->
<main id="main-content" tabindex="-1">
    <!-- Main content -->
</main>
```

## Internationalization

### Multi-language Support

Structure templates for internationalization:

```html
<html lang="{{ site.language }}">
<head>
    <title>{{ page.title }}</title>
</head>
<body>
    <div class="language-selector">
        {% for lang in site.languages %}
        <a href="/{{ lang }}/{{ page.url }}" lang="{{ lang }}" {% if lang == site.language %}aria-current="true"{% endif %}>
            {{ lang | upper }}
        </a>
        {% endfor %}
    </div>
    
    <h1>{{ page.title }}</h1>
    <div class="content">{{ content }}</div>
</body>
</html>
```

## Conclusion

These advanced templating techniques will help you create more sophisticated, maintainable, and performant websites with Sonne. By leveraging Jinja2's powerful features and Sonne's flexibility, you can build templates that adapt to content needs while maintaining consistency across your site.

Remember that templates should serve your content, not the other way around. Start simple and add complexity only when it serves a specific purpose. With these techniques in your toolkit, you'll be able to create templates that enhance your content while providing a great experience for your users.

## Further Resources

- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/)
- [Web Accessibility Initiative (WAI)](https://www.w3.org/WAI/)
- [Schema.org](https://schema.org/) for structured data
- [Google's PageSpeed Insights](https://pagespeed.web.dev/) for performance testing