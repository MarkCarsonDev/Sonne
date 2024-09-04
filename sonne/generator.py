import os
from sonne.variable_manager import process_variables, substitute_variables
from sonne.config import Config
from sonne.blog import process_blogs
from sonne.images import optimize_images

def generate_site(base_dir):
    print("Starting site generation...")
    config = Config(os.path.join(base_dir, 'sonne.config'))
    
    # Ensure output directory exists
    output_dir = os.path.join(base_dir, config.get_setting('DEFAULT', 'OutputDirectory'))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Process variables in all documents
    process_variables(base_dir, config)

    # Process and copy files
    process_and_copy_files(base_dir, output_dir, config)

    # Generate blog pages from markdown files
    process_blogs(base_dir, output_dir)

    # Optimize images
    optimize_images(base_dir, output_dir)

    print("Site generation completed.")

def process_and_copy_files(source_dir, output_dir, config):
    # Define exclusions and target extensions
    exclusions = [config.get_setting('DEFAULT', 'OutputDirectory'),
                  config.get_setting('DEFAULT', 'SourceDirectory'),
                  'sonne.config']
    target_ext = config.get_setting('DEFAULT', 'SubstitutionTargets')

    # Process each file within the source directory
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in exclusions]  # Skip excluded directories
        process_directory(root, dirs, files, source_dir, output_dir, exclusions, target_ext, config)

def process_directory(root, dirs, files, base_dir, output_dir, exclusions, target_ext, config):
    rel_path = os.path.relpath(root, base_dir)  # Ensure relative path is calculated from base_dir
    if any(excl in rel_path.split(os.sep) for excl in exclusions):
        return  # Skip processing this directory and its files

    output_subdir = os.path.join(output_dir, rel_path)
    if not os.path.exists(output_subdir):
        os.makedirs(output_subdir)

    for file in files:
        if file in exclusions or not any(file.endswith(ext) for ext in target_ext):
            continue  # Skip excluded files and non-target files

        source_file_path = os.path.join(root, file)
        output_file_path = os.path.join(output_subdir, file)
        substitute_and_write_file(source_file_path, output_file_path, base_dir, config)

def substitute_and_write_file(source_file_path, output_file_path, base_dir, config):
    with open(source_file_path, 'r') as f:
        content = f.read()

    # Fetch the path of the variables file from the base directory as specified in the configuration
    variables_file = os.path.join(base_dir, config.get_setting('DEFAULT', 'VariablesFile'))

    # Substitute variables in the content using the variables file path
    updated_content = substitute_variables(content, variables_file)

    with open(output_file_path, 'w') as f:
        f.write(updated_content)

    print(f"Processed and copied: {source_file_path} to {output_file_path}")

