import os
import argparse
from sonne.generator import generate_site
from sonne.setup import setup

def main():
    parser = argparse.ArgumentParser(description="Run Sonne static site generator")
    parser.add_argument('--path', type=str, default=os.getcwd(), help='Path to the site directory')
    args = parser.parse_args()

    # Run setup checker and daemon
    setup(args.path)

    # Assuming generate_site expects a path to the site directory
    generate_site(args.path)
