import os
import json
import base64
import io
import webview
from PIL import Image
from requirements import check_and_install_dependencies


class Api:
    def _initial_dir(self, override=None):
        """Dialog start directory: given override or the user's home."""
        return override or os.path.expanduser('~')

    def select_folder(self):
        """Native folder picker. Returns {success, path}."""
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return {"success": False, "error": "Cancelled"}
        if isinstance(result, (list, tuple)):
            result = result[0]
        return {"success": True, "path": result}

    def create_project(self, name):
        """Ask for a parent folder, create a subfolder named after the
        project, and return the path of the project file to create."""
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
        """Silently write project data (used by the autosave)."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_project_at(self, path):
        """Load project JSON from a known path (used for the recents list)."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            json.loads(content)  # validate
            return {"success": True, "path": path, "content": content}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Not a valid project file: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_project(self):
        """Open dialog to pick a project file."""
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

    def save_file(self, content, default_filename="presentation.html", file_type="html", start_dir=None):
        window = webview.windows[0]
        file_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=self._initial_dir(start_dir),
            save_filename=default_filename,
            file_types=('HTML Files (*.html)', 'All Files (*.*)')
        )
        if not file_path:
            return {"success": False, "error": "Cancelled"}
        if isinstance(file_path, (list, tuple)):
            file_path = file_path[0]

        if not file_path.endswith('.html'):
            file_path = file_path.rsplit('.', 1)[0] + '.html'
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_pdf_from_images(self, image_data_list, default_filename="presentation.pdf", start_dir=None):
        window = webview.windows[0]
        file_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=self._initial_dir(start_dir),
            save_filename=default_filename,
            file_types=('PDF Files (*.pdf)', 'All Files (*.*)')
        )
        if not file_path:
            return {"success": False, "error": "Cancelled"}
        if isinstance(file_path, (list, tuple)):
            file_path = file_path[0]

        try:
            pil_images = []
            for img_base64 in image_data_list:
                header, encoded = img_base64.split(",", 1)
                data = base64.b64decode(encoded)
                image = Image.open(io.BytesIO(data)).convert("RGB")
                pil_images.append(image)

            if pil_images:
                pil_images[0].save(
                    file_path,
                    "PDF",
                    save_all=True,
                    append_images=pil_images[1:]
                )
            return {"success": True, "path": file_path}
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
        webview.start()
