import json
import os

class Config:
    def __init__(self, config_path='sonne.config'):
        self.config_path = config_path
        self.config = {}
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as file:
                self.config = json.load(file)
        else:
            self.create_default_config()

    def get_setting(self, section, option):
        return self.config.get(section, {}).get(option, None)

    def set_setting(self, section, option, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][option] = value
        self.save_config()

    def save_config(self):
        with open(self.config_path, 'w') as file:
            json.dump(self.config, file, indent=4)

    def create_default_config(self):
        self.config = {
            'DEFAULT': {
                'PagesDirectory': 'pages',
                'BlogDirectory': 'blog',
                'DitherImages': 'yes',
                'IndexPage': 'index.html',
                'SubstitutionTargets': ['html', 'css', 'js'],
                'OutputDirectory': 'output',
                'SourceDirectory': 'sonne_sources',
                'VariablesFile': 'sonne_variables.json',
                'PreservePriorVariables': False,
                'BlogBase': 'blog_base.html'
            }
        }
        self.save_config()

