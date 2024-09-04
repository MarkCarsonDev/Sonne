import os
from sonne.config import Config

def setup(base_dir):
    initialize_sonne(base_dir)

def initialize_sonne(base_dir):
    print("Initializing Sonne")
    # Ensure base_dir exists
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print("\tCreating base directory...")

    config = Config(os.path.join(base_dir, 'sonne.config'))

    # Ensure directories as specified in the configuration
    ensure_directory(os.path.join(base_dir, config.get_setting('DEFAULT', 'PagesDirectory')))
    ensure_directory(os.path.join(base_dir, config.get_setting('DEFAULT', 'BlogDirectory')))
    ensure_directory(os.path.join(base_dir, config.get_setting('DEFAULT', 'OutputDirectory')))
    ensure_directory(os.path.join(base_dir, config.get_setting('DEFAULT', 'SourceDirectory')))


    print(f"Sonne configuration verified in `{base_dir}`.")

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"\tCreating {os.path.basename(path)} directory...")
