"""Repository entry point; no installation or third-party Python package required."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from science_story.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
