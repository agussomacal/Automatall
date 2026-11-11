import os
import webview
from xhtml2pdf import pisa


class Api:
    def __init__(self):
        pass

    def save_file(self, content, default_filename="presentation.html", file_type="html"):
        window = webview.windows[0]

        if file_type == "pdf":
            file_types = ('PDF Files (*.pdf)', 'All Files (*.*)')
            if not default_filename.endswith('.pdf'):
                default_filename = default_filename.rsplit('.', 1)[0] + '.pdf'
        else:
            file_types = ('HTML Files (*.html)', 'All Files (*.*)')
            if not default_filename.endswith('.html'):
                default_filename = default_filename.rsplit('.', 1)[0] + '.html'

        file_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=os.path.expanduser('~'),
            save_filename=default_filename,
            file_types=file_types
        )

        if file_path:
            if isinstance(file_path, (list, tuple)):
                file_path = file_path[0]

            try:
                if file_type == "pdf":
                    # Convert HTML content string directly into a true binary PDF file under the hood
                    with open(file_path, "wb") as pdf_file:
                        pisa_status = pisa.CreatePDF(content, dest=pdf_file)

                    if pisa_status.err:
                        return {"success": False, "error": "PDF conversion failed"}
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                return {"success": True, "path": file_path}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Cancelled"}


if __name__ == '__main__':
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