# blog.py

import os
import markdown
from markdown.extensions.meta import MetaExtension
import re
import json
from sonne.variable_manager import substitute_variables, report_variable
from sonne.images import dither_image, copy_original_image
import textwrap
from datetime import datetime

def process_blogs(base_dir, output_dir, config):
    blog_dir = os.path.join(base_dir, config.get_setting('DEFAULT', 'BlogDirectory'))
    template_path = os.path.join(blog_dir, config.get_setting('DEFAULT', 'BlogBase'))
    variables_path = os.path.join(base_dir, config.get_setting('DEFAULT', 'VariablesFile'))
    output_blog_dir = os.path.join(output_dir, config.get_setting('DEFAULT', 'BlogDirectory'))
    blog_posts_metadata = []

    # Collect metadata first
    for root, dirs, files in os.walk(blog_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                html_content, mond_variables = markdown_to_html(file_path, base_dir, output_dir)
                post_metadata = {
                    "title": mond_variables.get("title", "No Title"),
                    "date_posted": mond_variables.get("date_posted", ""),
                    "date_edited": mond_variables.get("date_edited", ""),
                    "description": mond_variables.get("description", ""),
                    "featured": mond_variables.get("featured", False),
                    "author": mond_variables.get("author", "Unattributed"),
                    "full_url": os.path.join("blog", mond_variables.get("date_posted") + '-' + mond_variables.get("page_url", "") + '.html'),
                    "url": os.path.join(mond_variables.get("page_url", "")),
                    "page_url": mond_variables.get("page_url", ""),
                    "content": html_content,
                    "current_year": datetime.now().year,
                    "tags": mond_variables.get("tags", "").split(),
                    "cover_img": mond_variables.get("cover_img", ""),
                }
                blog_posts_metadata.append(post_metadata)

    # Sort posts
    blog_posts_metadata.sort(key=lambda x: (x['date_posted'], x['url']))

    # Assign next and prev URLs
    for i, post in enumerate(blog_posts_metadata):
        next_index = i + 1 if i + 1 < len(blog_posts_metadata) else None
        prev_index = i - 1 if i > 0 else None
        blog_posts_metadata[i]['next_post'] = f"../{blog_posts_metadata[next_index]['full_url'][5:-5]}" if next_index is not None else None
        blog_posts_metadata[i]['prev_post'] = f"../{blog_posts_metadata[prev_index]['full_url'][5:-5]}" if prev_index is not None else None

    # Save all blog posts metadata as a global variable
    report_variable("all_blog_posts", blog_posts_metadata, variables_path)

    # Now apply the template and write output
    for post in blog_posts_metadata:
        mond_variables.update(post)  # Include next/prev post URLs and any additional metadata
        rendered_content = apply_template(post['content'], mond_variables, template_path, variables_path)
        write_output(post['date_posted'] + '-' + post['page_url'] + '.html', rendered_content, os.path.join(output_blog_dir))

def markdown_to_html(file_path, base_dir, output_dir):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    # Extract front matter for Mond variables
    front_matter, markdown_content = parse_front_matter(text)

    # Process images in markdown content
    markdown_content = process_images_in_markdown(markdown_content, file_path, front_matter, base_dir, output_dir)

    # Convert markdown to HTML
    html_content = markdown.markdown(markdown_content, extensions=[MetaExtension()])

    # Add extra metadata like page URL
    if 'page_url' not in front_matter:
        front_matter['page_url'] = os.path.splitext(os.path.basename(file_path))[0]  # Default to filename without extension

    return html_content, front_matter

def process_images_in_markdown(markdown_content, markdown_file_path, mond_variables, base_dir, output_dir):
    # Regex pattern to find image references in markdown
    # Pattern matches: ![alt text](image_path "title")
    image_pattern = r'!\[(.*?)\]\((.*?)(?: "(.*?)")?\)'
    matches = re.finditer(image_pattern, markdown_content)
    new_markdown_content = markdown_content

    for match in matches:
        full_match = match.group(0)
        alt_text = match.group(1)
        image_path = match.group(2)
        title = match.group(3)  # May be None

        # Resolve the absolute path of the image relative to the markdown file
        image_source_path = os.path.abspath(os.path.join(os.path.dirname(markdown_file_path), image_path))
        if not os.path.exists(image_source_path):
            print(f"Image not found: {image_source_path}")
            continue

        # Generate new image filename with publish date and title
        image_ext = os.path.splitext(image_source_path)[1]
        sanitized_title = ''.join(e for e in mond_variables.get('title', 'untitled') if e.isalnum())
        base_filename = f"{mond_variables.get('date_posted', 'unknown')}_{sanitized_title}"

        # Determine the image extension for the optimized image (PNG)
        optimized_image_ext = '.png'

        # Prepare optimized image filename and original image filename
        optimized_image_filename = f"{base_filename}_optimized{optimized_image_ext}"
        original_image_filename = f"{base_filename}_original{image_ext}"

        # Define the output paths for the images
        output_image_dir = os.path.join(output_dir, 'images')
        if not os.path.exists(output_image_dir):
            os.makedirs(output_image_dir)
        optimized_image_path = os.path.join(output_image_dir, optimized_image_filename)
        original_image_path = os.path.join(output_image_dir, original_image_filename)

        # Optimize the image and save it
        dither_image(image_source_path, optimized_image_path)

        # Copy the original image
        copy_original_image(image_source_path, original_image_path)

        # Update the image paths to be relative to the output HTML
        output_html_dir = os.path.join(output_dir, 'blog', mond_variables.get('date_posted', ''))
        relative_optimized_image_path = os.path.relpath(optimized_image_path, output_html_dir)
        relative_original_image_path = os.path.relpath(original_image_path, output_html_dir)

        # Generate unique ID for the image to be used in the JS
        image_id = f"image_{sanitized_title}_{match.start()}"

        # Prepare the SVG icon (simple dither icon)
        svg_icon = '''<svg onclick="swapImage('{image_id}', '{original_src}', '{optimized_src}')" style="cursor:pointer;width:16px;height:16px;" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <!-- Simple icon representing image quality toggle -->
    <circle cx="32" cy="32" r="30" stroke="black" stroke-width="2" fill="none"/>
    <circle cx="24" cy="24" r="2" fill="black"/>
    <circle cx="40" cy="24" r="2" fill="black"/>
    <circle cx="24" cy="40" r="2" fill="black"/>
    <circle cx="40" cy="40" r="2" fill="black"/>
</svg>'''.format(
            image_id=image_id,
            original_src=relative_original_image_path.replace('\\', '/'),
            optimized_src=relative_optimized_image_path.replace('\\', '/')
        )

        # Prepare the HTML to replace the markdown image
        image_html = textwrap.dedent('''\
            <div class="image-container">
                <img id="{image_id}" src="{optimized_src}" alt="{alt_text}" data-optimized-src="{optimized_src}" data-original-src="{original_src}" data-original="false">
                {title_html}
                <div class="image-footer">
                    {svg_icon}
                </div>
            </div>
        ''').format(
            image_id=image_id,
            optimized_src=relative_optimized_image_path.replace('\\', '/'),
            original_src=relative_original_image_path.replace('\\', '/'),
            alt_text=alt_text,
            title_html=f'<p>{title}</p>' if title else '',
            svg_icon=svg_icon
        )

        # Replace the markdown image syntax with the custom HTML
        new_markdown_content = new_markdown_content.replace(full_match, image_html)

    return new_markdown_content


def parse_front_matter(text):
    pattern = r'^---\s+(.*?)\s+---\s+(.*)$'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        # Extract front matter and replace newline with comma, enclose keys and string values in double quotes
        front_matter_text = match.group(1)
        # Convert to a valid JSON string
        json_str = front_matter_to_json(front_matter_text)
        front_matter = json.loads(json_str)
        content = match.group(2)
    else:
        front_matter = {}
        content = text

    return front_matter, content

def front_matter_to_json(front_matter_text):
    # Convert colon-separated key-value pairs to JSON
    lines = front_matter_text.split('\n')
    json_pieces = []
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().replace('\'', '').replace('"', '')
            value = value.strip()
            # Check if value is a string that needs quotes
            if not value.isdigit() and not (value.startswith('[') and value.endswith(']')):
                value = f'"{value}"'
            json_pieces.append(f'"{key}": {value}')
    json_str = '{' + ', '.join(json_pieces) + '}'
    return json_str

def write_output(filename, content, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, filename.replace('.md', '.html'))
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(content)

    print(f"Blog processed and written to: {output_path}")

def apply_template(html_content, mond_variables, template_path, variables_file):
    with open(template_path, 'r', encoding='utf-8') as file:
        template = file.read()

    for key, value in mond_variables.items():
        template = template.replace(f"{{-}}{{{key}}}", str(value))

    # Insert navigation links
    navigation_html = ""
    if mond_variables.get('prev_post'):
        navigation_html += f'<a href="{mond_variables["prev_post"]}.html">Previous Post</a> '
    if mond_variables.get('next_post'):
        navigation_html += f'<a href="{mond_variables["next_post"]}.html">Next Post</a>'

    template = template.replace("{-}{navigation}", navigation_html)

    final_rendered_content = substitute_variables(template, variables_file)
    return final_rendered_content
