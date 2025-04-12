"""
Setup script for Sonne static site generator.
"""
from setuptools import setup, find_packages
import os

# Read the long description from README.md
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Read the version from sonne/__init__.py
with open(os.path.join('sonne', '__init__.py'), 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip("'").strip('"')
            break
    else:
        version = '0.1.0'

setup(
    name='sonne',
    version=version,
    description='A minimalist static site generator optimized for low footprint sites',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Mark Carson',
    author_email='markcarson.dev@gmail.com',
    url='https://github.com/MarkCarsonDev/Sonne',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'sonne': [
            'static/css/*.css',
            'static/js/*.js',
            'templates/*/*.html',
            'templates/*/content/**/*',
            'templates/*/static/**/*',
        ],
    },
    entry_points={
        'console_scripts': [
            'sonne=sonne.cli.commands:main',
        ],
    },
    python_requires='>=3.8',
    install_requires=[
        'markdown>=3.4.0',
        'Pillow>=9.0.0',
        'click>=8.0.0',
        'PyYAML>=6.0',
        'Jinja2>=3.0.0',
        'beautifulsoup4>=4.9.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'black>=22.0.0',
            'isort>=5.10.0',
            'flake8>=4.0.0',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup :: HTML',
        'Topic :: Utilities',
    ],
    keywords='static site generator, blog, markdown, html, web, minimalist, energy-efficient, dithering',
    project_urls={
        'Bug Reports': 'https://github.com/MarkCarsonDev/Sonne/issues',
        'Source': 'https://github.com/MarkCarsonDev/Sonne',
    },
)