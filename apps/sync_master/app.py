"""
NoServerSync microApp entry point.

This file is ONLY the adapter for the microApp manager.
All internal logic lives in synclib.py / backend.py,
all UI lives in NoServerSyncGUI/ module.
"""
import sys
from pathlib import Path

# Add the parent directory to path so we can import NoServerSyncGUI
sys.path.insert(0, str(Path(__file__).parent))

from NoServerSyncGUI.gui_app import NoServerSyncGUIApp

APP_ID = "org.agussomacal.NoServerSync"
APP_NAME = "NoServerSync"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Serverless folder synchronization between devices"

def get_app_info() -> dict:
    """Metadata consumed by the microApp manager."""
    return {
        "id": APP_ID,
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "icon": "folder-sync-symbolic",
        "entrypoint": "launch",
    }

def launch(parent=None, argv=None) -> int:
    """Called by the microApp manager to start the app."""
    app = NoServerSyncGUIApp(application_id=APP_ID)
    app.props.register_session = False
    return app.run(argv if argv is not None else sys.argv)

if __name__ == "__main__":
    raise SystemExit(launch())