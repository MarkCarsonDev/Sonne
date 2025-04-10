import os
from sonne.variable_manager import process_variables, substitute_variables
from sonne.config import Config
from sonne.blog import process_blogs
from sonne.images import optimize_images

def generate_site(base_dir):
    print("Starting site generation...")
    config = Config(os.path.join(base_dir, 'sonne.config'))

    # Normalize and prepare output directory
    output_dir = config.normalize_output_directory()

    # Process variables in all documents
    process_variables(base_dir, config)

    # Generate blog pages from markdown files
    process_blogs(base_dir, output_dir, config)

    # Process and copy files
    process_and_copy_files(base_dir, output_dir, config)

    # Optimize images
    optimize_images(base_dir, output_dir)

    print("Site generation completed and ready at:", output_dir)

def process_and_copy_files(source_dir, output_dir, config):
    exclusions = [
        config.get_setting('DEFAULT', 'OutputDirectory'),
        config.get_setting('DEFAULT', 'SourceDirectory'),
        # Exclude the BlogDirectory except for the blog index file
        os.path.join(config.get_setting('DEFAULT', 'BlogDirectory'), ''),  
        'sonne.config',
    ]
    target_ext = config.get_setting('DEFAULT', 'SubstitutionTargets')

    for root, dirs, files in os.walk(source_dir):
        # Include the blog index.html as an exception
        if root.endswith(config.get_setting('DEFAULT', 'BlogDirectory')):
            dirs[:] = []  # Don't traverse deeper into the blog directory
            if 'index.html' in files:
                # Copy the blog index file to the correct place
                source_file = os.path.join(root, 'index.html')
                dest_file = os.path.join(output_dir, 'blog', 'index.html')
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                with open(source_file, 'r') as f:
                    content = f.read()

                variables_file = os.path.join(source_dir, config.get_setting('DEFAULT', 'VariablesFile'))
                updated_content = substitute_variables(content, variables_file)

                with open(dest_file, 'w') as f:
                    f.write(updated_content)

                print(f"Copied blog index {source_file} to {dest_file}")

        else:
            # Normal exclusion logic
            dirs[:] = [d for d in dirs if os.path.join(root, d) not in exclusions]
            for file in files:
                if any(file.endswith(ext) for ext in target_ext):
                    process_file(root, file, source_dir, output_dir, config)



def process_file(root, file, source_dir, output_dir, config):
    rel_path = os.path.relpath(root, source_dir)
    output_path = os.path.join(output_dir, rel_path)
    os.makedirs(output_path, exist_ok=True)

    source_file = os.path.join(root, file)
    dest_file = os.path.join(output_path, file)

    with open(source_file, 'r') as f:
        content = f.read()

    variables_file = os.path.join(source_dir, config.get_setting('DEFAULT', 'VariablesFile'))
    updated_content = substitute_variables(content, variables_file)

    with open(dest_file, 'w') as f:
        f.write(updated_content)

    print(f"Copied {source_file} to {dest_file}")
