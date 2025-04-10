---
title: About Sonne
template: page.html
description: Learn about the Sonne static site generator, its philosophy, and the team behind it
---

# About Sonne

## Our Philosophy

Sonne was created with a simple philosophy: static site generators should be powerful yet easy to use. We believe that creating websites shouldn't be complicated or resource-intensive. Our goal is to provide a tool that allows creators to focus on their content while ensuring their sites are fast, efficient, and beautiful.

### What Sets Sonne Apart

While there are many static site generators available today, Sonne differentiates itself through:

- **Minimalist Approach**: We focus on what's essential, avoiding bloat and complexity
- **Performance First**: Every feature is designed with performance in mind
- **Content-Centric**: Content creation is streamlined and intuitive
- **Flexible Templating**: Powerful enough for designers, simple enough for everyone
- **Python Ecosystem**: Leverage the extensive Python ecosystem for endless extensibility

## The Origin Story

Sonne (German for "sun") was born out of frustration with existing static site generators that were either too complex or too rigid. In late 2024, development began with the goal of creating a more balanced tool—one that offered power without complexity.

The name "Sonne" represents our philosophy: just as the sun provides essential light and energy efficiently, our generator aims to provide essential website functionality without unnecessary resource consumption.

## Core Principles

1. **Simplicity**: Intuitive interfaces and straightforward configuration
2. **Efficiency**: Minimal resource usage during building and serving
3. **Flexibility**: Adaptable to various project types and requirements
4. **Performance**: Fast build times and optimized output
5. **Accessibility**: Websites that work for everyone

## The Team

Sonne is developed and maintained by a small team of passionate developers, designers, and content creators. We're committed to open-source principles and believe in building tools that empower creators.

### Core Team Members

<div class="team-grid">
{% for member in team_members %}
    <div class="team-member">
        <div class="team-member-image">
            <img src="{{ member.image }}" alt="{{ member.name }}">
        </div>
        <h3 class="team-member-name">{{ member.name }}</h3>
        <p class="team-member-role">{{ member.role }}</p>
        <p>{{ member.bio }}</p>
        <div class="team-member-social">
            {% if member.social.github %}
            <a href="https://github.com/{{ member.social.github }}" target="_blank" rel="noopener">GitHub</a>
            {% endif %}
            {% if member.social.twitter %}
            <a href="https://twitter.com/{{ member.social.twitter }}" target="_blank" rel="noopener">Twitter</a>
            {% endif %}
        </div>
    </div>
{% endfor %}
</div>

## Open Source

Sonne is open source software, released under the MIT License. We believe in the power of community-driven development and welcome contributions from developers of all skill levels.

### How to Contribute

There are many ways to contribute to Sonne:

1. **Code**: Submit pull requests for bug fixes or features
2. **Documentation**: Help improve our documentation
3. **Templates**: Create and share templates
4. **Testing**: Test Sonne in different environments and report issues
5. **Feedback**: Share your ideas and suggestions

Visit our [GitHub repository](https://github.com/MarkCarsonDev/Sonne) to get started.

## Support Sonne

If you find Sonne useful, there are several ways you can support the project:

- **Star** our repository on GitHub
- **Share** Sonne with others
- **Create** and share templates, plugins, or tutorials
- **Report** bugs or suggest improvements
- **Contribute** code or documentation

## Contact Us

Have questions, suggestions, or just want to say hello? You can reach us through:

- **GitHub Issues**: For bug reports and feature requests
- **Twitter**: [@sonne_ssg](https://twitter.com/sonne_ssg)
- **Email**: [contact@sonnegenerator.dev](mailto:contact@sonnegenerator.dev)

We'd love to hear from you and see what you're building with Sonne!