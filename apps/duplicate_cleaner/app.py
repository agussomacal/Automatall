"""
Duplicate Finder microApp entry point.

Adapter for the microApp manager. All internal logic in DuplicateFinderLogic/,
all UI in DuplicateFinderGUI/.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from DuplicateFinderGUI.gui_app import DuplicateFinderApp

APP_ID = "org.agussomacal.DuplicateFinder"
APP_NAME = "Duplicate Finder"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Find and clean duplicate files using SHA256 hash comparison"

def get_app_info() -> dict:
    """Metadata consumed by the microApp manager."""
    return {
        "id": APP_ID,
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "icon": "view-filter-symbolic",
        "entrypoint": "launch",
    }

def launch(parent=None, argv=None) -> int:
    """Called by the microApp manager to start the app."""
    app = DuplicateFinderApp(application_id=APP_ID)
    app.props.register_session = False
    return app.run(argv if argv is not None else sys.argv)

if __name__ == "__main__":
    raise SystemExit(launch())