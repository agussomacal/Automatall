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
        """Fallback path: build a PDF from rasterized slide images."""
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

    def save_text_file(self, folder_path, filename, content):
        """Silently saves a text file inside the given folder without a dialog."""
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
        """Silently loads a text file from the given folder."""
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

    def save_direct_file(self, folder_path, filename, content):
        """Directly save a file in the project folder without a dialog."""
        try:
            if not folder_path or not os.path.exists(folder_path):
                return {"success": False, "error": "Project folder not set or does not exist."}
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_direct_pdf_from_images(self, folder_path, filename, image_data_list):
        """Directly save a PDF from images in the project folder without a dialog."""
        try:
            if not folder_path or not os.path.exists(folder_path):
                return {"success": False, "error": "Project folder not set or does not exist."}
            file_path = os.path.join(folder_path, filename)

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

    def open_file_with_system(self, file_path):
        """Open a file using the OS default viewer or browser."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File not found."}

            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.uname().sysname == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Headless-browser PDF generation (vector, pixel-perfect)
    # ------------------------------------------------------------------

    @staticmethod
    def _find_chromium_browser():
        """Locate an installed Chromium-family browser for headless printing.
        Returns an executable path or None."""
        candidates = []

        # PATH lookup first (linux/mac chromium installs, pinned versions)
        for name in ("chrome", "chromium", "chromium-browser", "google-chrome"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

        if os.name == 'nt':  # Windows
            base = os.environ.get('PROGRAMFILES', r'C:\Program Files')
            base86 = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
            local = os.environ.get('LOCALAPPDATA', '')
            for root in (base, base86, local):
                if not root:
                    continue
                candidates += [
                    os.path.join(root, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                    os.path.join(root, 'Google', 'Chrome', 'Application', 'chrome.exe'),
                ]
        elif os.uname().sysname == 'Darwin':  # macOS
            candidates += [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                '/Applications/Chromium.app/Contents/MacOS/Chromium',
            ]
        else:  # Linux standard install dirs
            candidates += [
                '/usr/bin/google-chrome',
                '/usr/bin/chromium',
                '/usr/bin/chromium-browser',
                '/snap/bin/chromium',
            ]

        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None

    def print_html_to_pdf(self, html_path, pdf_path=None, wait_ms=4000):
        """Render an HTML file to PDF using a headless Chromium-family
        browser (Edge/Chrome). Vector output, pixel-perfect math, fully
        autonomous — no dialogs, no user interaction.
        """
        try:
            if not html_path or not os.path.isfile(html_path):
                return {"success": False, "error": f"HTML file not found: {html_path}"}

            if not pdf_path:
                pdf_path = os.path.splitext(html_path)[0] + '.pdf'

            browser = self._find_chromium_browser()
            if not browser:
                return {"success": False, "error": "No Chromium-family browser found for headless PDF export."}

            uri = 'file:///' + os.path.abspath(html_path).replace('\\', '/')

            cmd = [
                browser,
                '--headless',
                '--disable-gpu',
                '--no-sandbox',  # <--- Fixes Linux zygote / broken pipe crash
                '--disable-dev-shm-usage',  # <--- Fixes shared memory limitations
                f'--print-to-pdf={os.path.abspath(pdf_path)}',
                '--no-pdf-header-footer',
                f'--virtual-time-budget={wait_ms}',
                uri,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )

            if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0:
                return {"success": True, "path": pdf_path, "engine": browser}
            return {
                "success": False,
                "error": f"Headless render failed: {result.stderr.strip()[:300] or 'no output file produced'}",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Headless render timed out."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_recent_projects(self):
        """Load recent projects from recents.json and filter out deleted/non-existent paths."""
        recents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recents.json")
        if not os.path.exists(recents_file):
            return {"success": True, "projects": []}
        try:
            with open(recents_file, "r", encoding="utf-8") as f:
                projects = json.load(f)

            # Safely check if path exists for each dictionary entry
            valid = []
            for p in projects:
                if isinstance(p, dict):
                    path = p.get("path")
                    if path and os.path.exists(path):
                        valid.append(p)

            # Save the cleaned list back
            with open(recents_file, "w", encoding="utf-8") as f:
                json.dump(valid, f, indent=2)
            return {"success": True, "projects": valid}
        except Exception as e:
            return {"success": False, "error": str(e), "projects": []}

    def add_recent_project(self, name, path):
        """Add or update a project in recents.json."""
        recents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recents.json")
        projects = []
        try:
            if os.path.exists(recents_file):
                with open(recents_file, "r", encoding="utf-8") as f:
                    projects = json.load(f)
        except Exception:
            projects = []

        # Remove existing entry with same path to avoid duplicates
        projects = [p for p in projects if isinstance(p, dict) and p.get("path") != path]
        projects.insert(0, {"name": name, "path": path})
        projects = projects[:10]  # Keep up to 10 recent projects

        try:
            with open(recents_file, "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=2)
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
        webview.start()
