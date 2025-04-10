---
title: Markdown Guide for Blogging
date: 2025-01-02
author: Your Name
tags:
  - markdown
  - tutorial
  - writing
categories:
  - guides
---

# Markdown Guide for Blogging

Markdown is a lightweight markup language that makes it easy to format text for the web. This guide covers the basics of using Markdown in your Sonne blog posts.

## Basic Formatting

### Headings

Create headings using `#` symbols:

```markdown
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6
```

### Emphasis

Italicize text with single asterisks or underscores:
*italic text* or _italic text_

Make text bold with double asterisks or underscores:
**bold text** or __bold text__

Combine them for bold and italic:
***bold and italic*** or ___bold and italic___

### Lists

#### Unordered Lists

Create unordered lists with asterisks, plus signs, or hyphens:

```markdown
* Item 1
* Item 2
  * Subitem 2.1
  * Subitem 2.2
* Item 3
```

Which renders as:

* Item 1
* Item 2
  * Subitem 2.1
  * Subitem 2.2
* Item 3

#### Ordered Lists

Create ordered lists with numbers:

```markdown
1. First item
2. Second item
3. Third item
```

Which renders as:

1. First item
2. Second item
3. Third item

### Links

Create links with square brackets for the text and parentheses for the URL:

```markdown
[Visit Example.com](https://example.com)
```

Which renders as: [Visit Example.com](https://example.com)

### Images

Add images with an exclamation mark, square brackets for alt text, and parentheses for the image URL:

```markdown
![Sonne Logo](/path/to/logo.png)
```

## Advanced Formatting

### Code Blocks

Create inline code with backticks:
`var example = "hello world";`

For code blocks, use triple backticks with an optional language identifier:

```python
def hello_world():
    print("Hello, world!")
```

### Blockquotes

Create blockquotes with greater-than signs:

```markdown
> This is a blockquote.
> 
> It can span multiple paragraphs if you include a greater-than sign on the blank lines in between.
```

Which renders as:

> This is a blockquote.
> 
> It can span multiple paragraphs if you include a greater-than sign on the blank lines in between.

### Horizontal Rules

Create horizontal rules with three or more hyphens, asterisks, or underscores:

```markdown
---
```

Which renders as:

---

### Tables

Create tables with pipes and hyphens:

```markdown
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
```

Which renders as:

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

## Using Markdown in Sonne

Sonne processes your Markdown files and converts them to HTML when building your site. You can use all the Markdown features described above in your blog posts and pages.

### Sonne-Specific Features

Sonne also supports some additional features:

#### Front Matter

As you've seen, each post starts with front matter:

```yaml
---
title: Markdown Guide
date: 2025-01-02
author: Your Name
tags:
  - markdown
  - tutorial
---
```

#### Variable Substitution

You can use variables in your content:

```markdown
The current year is {+}{site.year}.
My name is {+}{site.author}.
```

## Conclusion

Markdown makes writing content for your blog simple and efficient. With just a few special characters, you can create well-formatted posts that look great on your Sonne site.

Happy writing!