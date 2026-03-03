"""
Support for running scripts as module: python -m mermaid_ascii.scripts.render
"""

from .render import main
import sys

if __name__ == "__main__":
    sys.exit(main())
