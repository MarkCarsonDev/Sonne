import os
import markdown
from markdown.extensions.meta import MetaExtension
import re
import json
from sonne.variable_manager import substitute_variables  # Import the function for global variable substitution

def process_blogs(base_dir, output_dir, config):
    blog_dir = os.path.join(base_dir, config.get_setting('DEFAULT', 'BlogDirectory'))
    template_path = os.path.join(blog_dir, config.get_setting('DEFAULT', 'BlogBase'))
    output_blog_dir = os.path.join(output_dir, config.get_setting('DEFAULT', 'BlogDirectory'))
    variables_file = os.path.join(base_dir, config.get_setting('DEFAULT', 'VariablesFile'))  # Path to the global variables file

    if not os.path.exists(output_blog_dir):
        os.makedirs(output_blog_dir)

    # Process each Markdown file in the blog directory
    for root, dirs, files in os.walk(blog_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                html_content, mond_variables = markdown_to_html(file_path)
                rendered_content = apply_template(html_content, mond_variables, template_path, variables_file)  # Pass the path to the global variables file
                write_output(file, rendered_content, output_blog_dir)

def apply_template(html_content, mond_variables, template_path, variables_file):
    with open(template_path, 'r', encoding='utf-8') as file:
        template = file.read()

    # Substitute Mond variables and content into the template
    for key, value in mond_variables.items():
        template = template.replace(f"{{-}}{{{key}}}", str(value))

    # Substitute the content placeholder with the HTML content
    template = template.replace("{-}{content}", html_content)

    # Apply global Sonne variables
    final_rendered_content = substitute_variables(template, variables_file)

    return final_rendered_content

def markdown_to_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    # Extract front matter for Mond variables
    front_matter, markdown_content = parse_front_matter(text)
    html_content = markdown.markdown(markdown_content, extensions=[MetaExtension()])

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
