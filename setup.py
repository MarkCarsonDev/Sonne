from setuptools import setup, find_packages

setup(
    name='sonne',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'sonne = sonne.__main__:main'
        ]
    },
    install_requires=[
        # List your project's dependencies here.
        # e.g., 'requests', 'markdown2', 'Pillow'
    ],
)
