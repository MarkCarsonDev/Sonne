"""
Generate statistics for the Sonne showcase site.

Demonstrates producing template data from Python: everything passed to
sonne_var() is available as a global variable in templates.
"""

import re
from datetime import datetime
from pathlib import Path

import yaml

from sonne.script_api import sonne_var

CONTENT_DIR = Path.cwd() / "content"
BLOG_DIR = CONTENT_DIR / "blog"
FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_front_matter(text):
    """Return (front_matter_dict, body) for a Markdown file's text."""
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, text[match.end() :]


def published_posts():
    """Yield the front matter of every blog post outside _drafts directories."""
    for path in BLOG_DIR.glob("**/*.md"):
        if "_drafts" not in path.relative_to(BLOG_DIR).parts:
            front_matter, _ = split_front_matter(path.read_text(encoding="utf-8"))
            if not front_matter.get("draft", False):
                yield front_matter


def tags_of(front_matter):
    tags = front_matter.get("tags") or []
    if isinstance(tags, str):
        return [tag.strip() for tag in tags.split(",") if tag.strip()]
    return [str(tag) for tag in tags]


def count_words():
    """Count words in the body of every Markdown file (front matter excluded)."""
    return sum(
        len(split_front_matter(path.read_text(encoding="utf-8"))[1].split())
        for path in CONTENT_DIR.glob("**/*.md")
    )


posts = list(published_posts())
unique_tags = {tag for post in posts for tag in tags_of(post)}
content_file_count = sum(1 for path in CONTENT_DIR.rglob("*") if path.is_file())

sonne_var(
    "site_stats",
    [
        {"label": "Blog Posts", "value": len(posts)},
        {"label": "Unique Tags", "value": len(unique_tags)},
        {"label": "Total Words", "value": f"{count_words():,}"},
        {"label": "Content Files", "value": content_file_count},
    ],
)

sonne_var(
    "features",
    [
        {
            "title": "Markdown Support",
            "description": "Write content in Markdown with front matter for metadata and flexible formatting.",
            "icon": "<path d='M14 3v4a1 1 0 0 0 1 1h4'/><path d='M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8l4 4v12a2 2 0 0 1-2 2z'/><path d='m9 17 2-2 2 2'/><path d='m9 11 2 2 2-2'/>",
        },
        {
            "title": "Jinja2 Templates",
            "description": "Powerful templating with Jinja2 for flexible layout and design options.",
            "icon": "<path d='M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'/><path d='M4 12h16'/><path d='M8 16h.01'/><path d='M12 16h.01'/><path d='M16 16h.01'/>",
        },
        {
            "title": "Blog Engine",
            "description": "Built-in blog functionality with categories, tags, pagination, and RSS feed.",
            "icon": "<path d='M19 22H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2z'/><path d='M7 14h10'/><path d='M7 18h6'/><path d='M7 10h10'/><path d='M7 6h10'/>",
        },
        {
            "title": "Image Optimization",
            "description": "Automatic image resizing, format conversion, and optimization for better performance.",
            "icon": "<circle cx='9' cy='9' r='2'/><path d='M10.3 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10.8'/><path d='m21 15-3.1-3.1a2 2 0 0 0-2.825 0L9 18'/>",
        },
        {
            "title": "Python Data Sources",
            "description": "Use Python scripts to generate dynamic data for your site.",
            "icon": "<path d='M12 9H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-5z'/><path d='M12 9V5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v4'/><path d='M12 9V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v4'/>",
        },
        {
            "title": "Live Reload",
            "description": "Development server with automatic browser refresh when content changes.",
            "icon": "<path d='M21 12a9 9 0 0 1-9 9'/><path d='M3 12a9 9 0 0 1 9-9'/><path d='m17 8-5 5-5-5'/><path d='M12 3v10'/>",
        },
    ],
)

sonne_var(
    "testimonials",
    [
        {
            "name": "Jane Doe",
            "title": "Web Developer",
            "quote": "Sonne has been a game-changer for my static site projects. It's fast, flexible, and the built-in blog functionality saves me hours of work.",
        },
        {
            "name": "John Smith",
            "title": "Content Creator",
            "quote": "I'm not a developer, but Sonne made it easy for me to create a professional blog. The Markdown support is fantastic!",
        },
        {
            "name": "Alex Johnson",
            "title": "Technical Writer",
            "quote": "The image optimization features in Sonne have significantly improved my site's performance. Pages load faster and I don't have to manually resize images.",
        },
    ],
)

sonne_var("last_updated", datetime.now().strftime("%B %d, %Y"))
