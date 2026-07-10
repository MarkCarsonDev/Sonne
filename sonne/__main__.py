"""Allow running Sonne as ``python -m sonne`` (PATH-independent entry point)."""

from sonne.cli.commands import main

if __name__ == "__main__":
    main()
