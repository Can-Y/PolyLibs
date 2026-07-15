"""Entry point: python -m polylibs."""

import sys

from .cli import main as cli_main


def main() -> int:
    """CLI entry point."""
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
