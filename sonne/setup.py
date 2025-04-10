import os
from sonne.config import Config

def setup(base_dir):
    initialize_sonne(base_dir)

def initialize_sonne(base_dir):
    print("Initializing Sonne")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    config = Config(os.path.join(base_dir, 'sonne.config'))
    config.normalize_output_directory()

    required_dirs = [
        config.get_setting('DEFAULT', 'PagesDirectory'),
        config.get_setting('DEFAULT', 'BlogDirectory'),
        config.get_setting('DEFAULT', 'SourceDirectory'),
    ]

    for directory in required_dirs:
        full_path = os.path.join(base_dir, directory)
        os.makedirs(full_path, exist_ok=True)
        print(f"Ensured {full_path} exists.")
