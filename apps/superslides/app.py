import os
import json
import base64
import io
import shutil
import subprocess
import webview
from PIL import Image
from requirements import check_and_install_dependencies


class Api:
    def _initial_dir(self, override=None):
        return override or os.path.expanduser('~')

    def select_folder(self):
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return {"success": False, "error": "Cancelled"}
        if isinstance(result, (list, tuple)):
            result = result[0]
        return {"success": True, "path": result}

    def create_project(self, name):
        window = webview.windows[0]
        parent = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not parent:
            return {"success": False, "error": "Cancelled"}
        if isinstance(parent, (list, tuple)):
            parent = parent[0]

        safe = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe:
            safe = "Presentation"

        folder = os.path.join(parent, safe)
        project_file = os.path.join(folder, safe + ".ssproj")

        try:
            os.makedirs(folder, exist_ok=True)
            if os.path.exists(project_file):
                return {"success": False, "error": "A project with this name already exists in that folder."}
        except Exception as e:
            return {"success": False, "error": str(e)}

        return {"success": True, "path": project_file, "folder": folder}

    def save_project_data(self, path, content):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_project_at(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            json.loads(content)
            return {"success": True, "path": path, "content": content}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Not a valid project file: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_project(self):
        window = webview.windows[0]
        file_path = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('Slide Project Files (*.ssproj)', 'JSON Files (*.json)', 'All Files (*.*)')
        )
        if not file_path:
            return {"success": False, "error": "Cancelled"}
        if isinstance(file_path, (list, tuple)):
            file_path = file_path[0]
        return self.load_project_at(file_path)

    def save_text_file(self, folder_path, filename, content):
        try:
            if not folder_path:
                return {"success": False, "error": "No folder path provided"}
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_text_file(self, folder_path, filename):
        try:
            if not folder_path:
                return {"success": False, "error": "No folder path provided"}
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"success": True, "content": content}
            return {"success": False, "error": "File not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_recent_projects(self):
        recents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recents.json")
        if not os.path.exists(recents_file):
            return {"success": True, "projects": []}
        try:
            with open(recents_file, "r", encoding="utf-8") as f:
                projects = json.load(f)

            valid = []
            for p in projects:
                if isinstance(p, dict):
                    path = p.get("path")
                    if path and os.path.exists(path):
                        valid.append(p)

            with open(recents_file, "w", encoding="utf-8") as f:
                json.dump(valid, f, indent=2)
            return {"success": True, "projects": valid}
        except Exception as e:
            return {"success": False, "error": str(e), "projects": []}

    def add_recent_project(self, name, path):
        recents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recents.json")
        projects = []
        try:
            if os.path.exists(recents_file):
                with open(recents_file, "r", encoding="utf-8") as f:
                    projects = json.load(f)
        except Exception:
            projects = []

        projects = [p for p in projects if isinstance(p, dict) and p.get("path") != path]
        projects.insert(0, {"name": name, "path": path})
        projects = projects[:10]

        try:
            with open(recents_file, "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_file_with_system(self, file_path):
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File not found."}

            if os.name == 'nt':
                os.startfile(file_path)
            elif os.uname().sysname == 'Darwin':
                subprocess.run(['open', file_path])
            else:
                subprocess.run(['xdg-open', file_path])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


if __name__ == '__main__':
    check_and_install_dependencies()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "index.html")

    if not os.path.exists(html_path):
        print(f"Error: Could not find {html_path}. Make sure index.html is in the same directory.")
    else:
      api = Api()
      window = webview.create_window(
          "Local Slide Creator",
          html_path,
          width=1200,
          height=750,
          resizable=True,
          js_api=api
      )
      webview.start(http_server=True)