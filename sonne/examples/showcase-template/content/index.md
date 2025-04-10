---
title: Sonne Static Site Generator
subtitle: A minimalist static site generator optimized for low footprint sites
template: home.html
primary_button:
  text: Get Started
  url: /docs/getting-started/
secondary_button:
  text: View on GitHub
  url: https://github.com/MarkCarsonDev/Sonne
cta:
  title: Ready to Build Your Site?
  description: Get started with Sonne in just a few minutes
  button:
    text: Install Sonne
    url: /docs/installation/
---

## Welcome to Sonne

Sonne is a minimalist static site generator designed to create efficient websites with minimal resource requirements. It combines simplicity, flexibility, and performance to help you create beautiful static websites without the bloat.

### Why Choose Sonne?

- **Minimalist Design Philosophy**: Focus on simplicity and performance
- **Easy Content Creation**: Write in Markdown with powerful front matter support
- **Flexible Templating**: Use Jinja2 templates for complete control over your design
- **Built-in Blog Engine**: Create blog posts with categories, tags, and more
- **Image Optimization**: Automatically resize, convert, and optimize images
- **Python Data Sources**: Use Python scripts to generate dynamic content
- **Live Development Server**: Preview your site with auto-reload while you work

### Getting Started

Install Sonne using pip:

```bash
pip install sonne
```

Create a new site:

```bash
sonne new -p my-site -t blog
cd my-site
sonne serve
```

### Examples of Sonne in Action

Here are some ways Sonne helps you build better websites:

#### Variable Substitution

```markdown
The current year is {+}{site.year}.
My name is {+}{site.author}.
```

#### Embedded Python

```
{p}{# 
import random
result = "Random number: " + str(random.randint(1, 100))
#}
```

#### Custom Data Sources

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

### Join the Community

Sonne is an open-source project with a growing community. Contributions, feedback, and questions are always welcome!