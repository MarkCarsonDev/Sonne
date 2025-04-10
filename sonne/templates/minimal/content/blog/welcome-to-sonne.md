---
title: Welcome to Sonne
date: 2025-04-01
author: Sonne User
description: A brief introduction to the Sonne static site generator
tags:
  - sonne
  - introduction
categories:
  - Getting Started
---

# Welcome to Sonne

Sonne is a minimalist static site generator designed to create websites with a low environmental footprint. This post will introduce you to its key features and help you get started.

## Features

Sonne comes with several key features that make it stand out from other static site generators:

1. **Lightweight Output**: Sonne generates highly optimized static sites with minimal footprint.
2. **Image Optimization**: Images are automatically optimized and can be dithered to reduce file size.
3. **Markdown Support**: Write your content in Markdown and let Sonne convert it to HTML.
4. **Blog Functionality**: Built-in support for blogs with tags, categories, and pagination.
5. **Variable Substitution**: Use variables throughout your site for dynamic content.
6. **Themes**: Switch between light and dark modes for better user experience.
7. **Keyboard Navigation**: Navigate your site using keyboard shortcuts.

## Getting Started

To create your first Sonne site, install the package and run the `new` command:

```bash
pip install sonne
sonne new --path my-site
cd my-site
```

This will create a new site with the default template. Then you can build and serve your site:

```bash
sonne build
sonne serve
```

Your site will be available at http://localhost:8000.

## Creating Content

Sonne supports both regular pages and blog posts. To create a new page, add a Markdown or HTML file to the `content` directory. To create a blog post, add a Markdown file to the `content/blog` directory.

Blog posts support front matter, which is a YAML block at the beginning of the file that contains metadata about the post:

```yaml
---
title: My First Post
date: 2025-04-01
author: Sonne User
description: A brief description of the post
tags:
  - tag1
  - tag2
categories:
  - category1
---
```

## Image Handling

Sonne has special features for handling images. When you include an image in your content, Sonne can automatically optimize it and provide a toggle for users to switch between the optimized and original versions:

![A sample image](sample-image.jpg "Sample image caption")

## Variables

You can use variables throughout your site using the `{+}{variable_name}` syntax. Variables can be defined in your configuration file or in separate data files.

For blog posts, you can also use "Mond variables" with the `{-}{variable_name}` syntax, which are specific to the current post.

## Conclusion

Sonne is designed to be simple, efficient, and environmentally friendly. By generating static sites with minimal footprint, it helps reduce the environmental impact of web hosting while still providing a great user experience.

If you have any questions or need help, check out the [documentation](https://github.com/MarkCarsonDev/Sonne) or open an issue on GitHub.

Happy building!