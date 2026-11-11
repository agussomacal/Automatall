import os
import json
import base64
import io
import webview
from PIL import Image
from requirements import check_and_install_dependencies


class Api:
    def __init__(self):
        pass

    def _prepare_save_path(self, default_filename, file_types):
        """Shared helper: open a save dialog and normalize the chosen path."""
        window = webview.windows[0]
        file_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=os.path.expanduser('~'),
            save_filename=default_filename,
            file_types=file_types
        )
        if not file_path:
            return None
        if isinstance(file_path, (list, tuple)):
            file_path = file_path[0]
        return file_path

    def save_file(self, content, default_filename="presentation.html", file_type="html"):
        file_path = self._prepare_save_path(
            default_filename, ('HTML Files (*.html)', 'All Files (*.*)'))

        if file_path:
            if not file_path.endswith('.html'):
                file_path = file_path.rsplit('.', 1)[0] + '.html'
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {"success": True, "path": file_path}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Cancelled"}

    def save_project(self, content, default_filename="presentation.ssproj"):
        file_path = self._prepare_save_path(
            default_filename,
            ('Slide Project Files (*.ssproj)', 'JSON Files (*.json)', 'All Files (*.*)'))

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {"success": True, "path": file_path}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Cancelled"}

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

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            json.loads(content)  # validate before handing to the UI
            return {"success": True, "path": file_path, "content": content}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Not a valid project file: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_pdf_from_images(self, image_data_list, default_filename="presentation.pdf"):
        file_path = self._prepare_save_path(
            default_filename, ('PDF Files (*.pdf)', 'All Files (*.*)'))

        if file_path:
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
        return {"success": False, "error": "Cancelled"}


if __name__ == '__main__':
    # Check and install dependencies defined in dependencies.yaml
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