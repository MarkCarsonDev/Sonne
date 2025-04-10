import os
import argparse
from sonne.generator import generate_site
from sonne.setup import setup

def main():
    parser = argparse.ArgumentParser(description="Run Sonne static site generator")
    parser.add_argument('--path', type=str, default=os.getcwd(), help='Path to the site directory')
    args = parser.parse_args()

    setup(args.path)
    generate_site(args.path)

if __name__ == "__main__":
    main()
