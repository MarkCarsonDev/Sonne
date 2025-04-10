---
title: About Sonne
description: About the Sonne static site generator
template: page.html
---

# About Sonne

Sonne is a minimalist static site generator designed with a focus on environmental consciousness and efficiency. The name "Sonne" comes from the German word for "sun," reflecting its goal to be as sustainable as possible, just like solar energy.

## The Philosophy

The web has become increasingly resource-intensive, with websites often consuming significant server resources and bandwidth. Sonne takes a different approach by generating completely static sites that:

1. **Minimize Server Load**: Static files require minimal server resources to host.
2. **Reduce Bandwidth**: Optimized images and minimal code reduce data transfer.
3. **Lower Energy Consumption**: Less processing power means lower energy usage.
4. **Speed Up Loading**: Static sites load quickly, improving user experience.

## Key Features

### Efficient Rendering

Sonne generates pure HTML, CSS, and JavaScript without relying on heavy client-side frameworks. This means websites load faster and consume less resources on both the server and client side.

### Image Optimization

Images are automatically optimized and can be dithered to significantly reduce file size while maintaining acceptable quality. Users can toggle between optimized and original images if needed.

### Variable Substitution

Sonne's simple variable system allows you to insert dynamic content into your static pages without the overhead of a full templating engine.

### Blog Support

Built-in blog functionality with support for posts, tags, categories, and pagination makes it easy to maintain a blog without additional plugins or complexity.

### Markdown Support

Write your content in Markdown and let Sonne convert it to HTML, making content creation simple and efficient.

## Getting Started

To create your first Sonne site:

```bash
pip install sonne
sonne new --path my-site
cd my-site
sonne build
sonne serve
```

## Environmental Impact

A website built with Sonne typically uses less than half the resources of a comparable site built with a typical CMS or JavaScript framework. This means:

- Less server energy usage
- Reduced carbon footprint
- Faster loading times
- Lower hosting costs

By choosing Sonne, you're making a small but meaningful contribution to a more sustainable web.

## Contributing

Sonne is open source and welcomes contributions. Visit the [GitHub repository](https://github.com/MarkCarsonDev/Sonne) to learn more about how you can help improve Sonne.