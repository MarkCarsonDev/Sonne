import os
import markdown
from markdown.extensions.meta import MetaExtension
import re
import json
from sonne.variable_manager import substitute_variables, report_variable  # Import the function for global variable substitution

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
                html_content, mond_variables = markdown_to_html(file_path)
                post_metadata = {
                    "title": mond_variables.get("title", "No Title"),
                    "date_posted": mond_variables.get("date_posted", ""),
                    "featured": mond_variables.get("featured", False),
                    # "url": os.path.join("blog", mond_variables.get("date_posted"), mond_variables.get("page_url", "")),
                    "url": os.path.join(mond_variables.get("page_url", "")),
                    "page_url": mond_variables.get("page_url", ""),
                    "content": html_content
                }
                blog_posts_metadata.append(post_metadata)

    # Sort posts
    blog_posts_metadata.sort(key=lambda x: (x['date_posted'], x['url']))

    # Assign next and prev URLs
    for i, post in enumerate(blog_posts_metadata):
        next_index = i + 1 if i + 1 < len(blog_posts_metadata) else None
        prev_index = i - 1 if i > 0 else None
        blog_posts_metadata[i]['next_post'] = blog_posts_metadata[next_index]['url'] if next_index is not None else None
        blog_posts_metadata[i]['prev_post'] = blog_posts_metadata[prev_index]['url'] if prev_index is not None else None

    # Save all blog posts metadata as a global variable
    report_variable("all_blog_posts", blog_posts_metadata, variables_path)

    # Now apply the template and write output
    for post in blog_posts_metadata:
        mond_variables.update(post)  # Include next/prev post URLs and any additional metadata
        rendered_content = apply_template(post['content'], mond_variables, template_path, variables_path)
        write_output(post['page_url'] + '.html', rendered_content, output_blog_dir)


def apply_template(html_content, mond_variables, template_path, variables_file):
    print(mond_variables)
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


def markdown_to_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    # Extract front matter for Mond variables
    front_matter, markdown_content = parse_front_matter(text)
    html_content = markdown.markdown(markdown_content, extensions=[MetaExtension()])

    # Add extra metadata like page URL
    if 'page_url' not in front_matter:
        front_matter['page_url'] = file_path.split('/')[-1].replace('.md', '.html')  # Default to filename if not specified

    return html_content, front_matter


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
    output_path = os.path.join(output_dir, filename.replace('.md', '.html'))
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(content)

    print(f"Blog processed and written to: {output_path}")
