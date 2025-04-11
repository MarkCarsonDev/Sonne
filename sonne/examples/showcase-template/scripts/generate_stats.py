"""
Generate statistics for the Sonne showcase site.

This script demonstrates how to generate dynamic data for your Sonne site
using Python. The generated data will be available as global variables in templates.
"""

import os
import random
from datetime import datetime
from pathlib import Path

def count_posts():
    """Count the number of blog posts."""
    try:
        blog_dir = os.path.join(os.getcwd(), 'content', 'blog')
        if not os.path.exists(blog_dir):
            return 0
            
        # Count markdown files (posts)
        post_count = 0
        for file_path in Path(blog_dir).glob('**/*.md'):
            # Skip files in _drafts directory
            if '_drafts' not in str(file_path):
                post_count += 1
                
        return post_count
    except Exception as e:
        print(f"Error counting posts: {e}")
        return 0
        
def count_tags():
    """Count the number of unique tags in blog posts."""
    try:
        blog_dir = os.path.join(os.getcwd(), 'content', 'blog')
        if not os.path.exists(blog_dir):
            return 0
            
        # Collect all tags
        all_tags = set()
        
        for file_path in Path(blog_dir).glob('**/*.md'):
            # Skip files in _drafts directory
            if '_drafts' in str(file_path):
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Look for tags in front matter
            import re
            
            # Match YAML front matter
            front_matter_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            
            if front_matter_match:
                front_matter = front_matter_match.group(1)
                
                # Look for tags section
                tags_match = re.search(r'tags:\s*\n((?:\s*-\s*.*\n)+)', front_matter)
                
                if tags_match:
                    # Extract individual tags
                    tag_lines = tags_match.group(1).strip().split('\n')
                    for line in tag_lines:
                        tag = line.strip().lstrip('-').strip()
                        if tag:
                            all_tags.add(tag)
                else:
                    # Look for inline tags
                    inline_tags_match = re.search(r'tags:\s*\[(.*?)\]', front_matter)
                    if inline_tags_match:
                        tags_list = inline_tags_match.group(1)
                        for tag in tags_list.split(','):
                            tag = tag.strip().strip('"\'')
                            if tag:
                                all_tags.add(tag)
                                
        return len(all_tags)
    except Exception as e:
        print(f"Error counting tags: {e}")
        return 0
        
def count_words():
    """Estimate the total word count across all content."""
    try:
        content_dir = os.path.join(os.getcwd(), 'content')
        if not os.path.exists(content_dir):
            return 0
            
        # Count words in all markdown files
        word_count = 0
        
        for file_path in Path(content_dir).glob('**/*.md'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Remove front matter
            import re
            content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
            
            # Count words in the content
            words = content.split()
            word_count += len(words)
                
        return word_count
    except Exception as e:
        print(f"Error counting words: {e}")
        return 0
        
def get_build_time():
    """Get the estimated build time."""
    # This is a simulated value since we don't have actual build time metrics
    post_count = count_posts()
    
    # Simulate build time based on number of posts (just for demonstration)
    # In a real scenario, you might track actual build times
    base_time = 0.5  # Base time in seconds
    per_post_time = 0.1  # Time per post in seconds
    
    build_time = base_time + (post_count * per_post_time)
    
    return round(build_time, 2)

# Generate data
post_count = count_posts()
tag_count = count_tags()
word_count = count_words()
build_time = get_build_time()

# Generate site statistics
site_stats = [
    {"label": "Blog Posts", "value": post_count},
    {"label": "Unique Tags", "value": tag_count},
    {"label": "Total Words", "value": f"{word_count:,}"},
    {"label": "Build Time", "value": f"{build_time}s"}
]

# Create a list of features for the homepage
features = [
    {
        "title": "Markdown Support",
        "description": "Write content in Markdown with front matter for metadata and flexible formatting.",
        "icon": "<path d='M14 3v4a1 1 0 0 0 1 1h4'/><path d='M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8l4 4v12a2 2 0 0 1-2 2z'/><path d='m9 17 2-2 2 2'/><path d='m9 11 2 2 2-2'/>"
    },
    {
        "title": "Jinja2 Templates",
        "description": "Powerful templating with Jinja2 for flexible layout and design options.",
        "icon": "<path d='M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'/><path d='M4 12h16'/><path d='M8 16h.01'/><path d='M12 16h.01'/><path d='M16 16h.01'/>"
    },
    {
        "title": "Blog Engine",
        "description": "Built-in blog functionality with categories, tags, pagination, and RSS feed.",
        "icon": "<path d='M19 22H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2z'/><path d='M7 14h10'/><path d='M7 18h6'/><path d='M7 10h10'/><path d='M7 6h10'/>"
    },
    {
        "title": "Image Optimization",
        "description": "Automatic image resizing, format conversion, and optimization for better performance.",
        "icon": "<circle cx='9' cy='9' r='2'/><path d='M10.3 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10.8'/><path d='m21 15-3.1-3.1a2 2 0 0 0-2.825 0L9 18'/>"
    },
    {
        "title": "Python Data Sources",
        "description": "Use Python scripts to generate dynamic data for your site.",
        "icon": "<path d='M12 9H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-5z'/><path d='M12 9V5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v4'/><path d='M12 9V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v4'/>"
    },
    {
        "title": "Live Reload",
        "description": "Development server with automatic browser refresh when content changes.",
        "icon": "<path d='M21 12a9 9 0 0 1-9 9'/><path d='M3 12a9 9 0 0 1 9-9'/><path d='m17 8-5 5-5-5'/><path d='M12 3v10'/>"
    }
]

# Generate testimonials
testimonials = [
    {
        "name": "Jane Doe",
        "title": "Web Developer",
        "quote": "Sonne has been a game-changer for my static site projects. It's fast, flexible, and the built-in blog functionality saves me hours of work."
    },
    {
        "name": "John Smith",
        "title": "Content Creator",
        "quote": "I'm not a developer, but Sonne made it easy for me to create a professional blog. The Markdown support is fantastic!"
    },
    {
        "name": "Alex Johnson",
        "title": "Technical Writer",
        "quote": "The image optimization features in Sonne have significantly improved my site's performance. Pages load faster and I don't have to manually resize images."
    }
]

# Set global variables for use in templates
sonne_var("site_stats", site_stats)
sonne_var("features", features)
sonne_var("testimonials", testimonials)
sonne_var("last_updated", datetime.now().strftime("%B %d, %Y"))

# Generate a custom footer with statistics
footer_custom = f"""
<div class="site-stats">
    <p>This site includes {post_count} blog posts with {tag_count} unique tags and approximately {word_count:,} words.</p>
    <p>Last updated: {datetime.now().strftime("%B %d, %Y")}</p>
</div>
"""

# Set the custom footer
sonne_var("footer_custom", footer_custom)