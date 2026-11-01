import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QHBoxLayout, \
    QMessageBox, QFileDialog
from PyQt6.QtGui import QFont

APP_PATH = Path(__file__).parent
GLOBAL_STATE_FILE = APP_PATH / "global_app_state.json"
IMAGE_STATE_FILE = APP_PATH / "image_modality" / "layout_state.json"


class ModalitySelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Map Modality")
        self.resize(420, 220)
        self.setStyleSheet("background-color: #241c14; color: #f0e0d0;")

        layout = QVBoxLayout()
        title = QLabel("Choose Map Modality:")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e0d0b0;")
        layout.addWidget(title)

        self.combo = QComboBox()
        self.combo.addItem("Hexagon Map (Interactive / Procedural)", "hex_modality")
        self.combo.addItem("High-Definition Image Map (Static Background)", "image_modality")
        self.combo.setStyleSheet("background-color: #382c20; color: #f0e0d0; padding: 6px;")
        layout.addWidget(self.combo)

        self.image_path_label = QLabel("HD Image Path (Remembered / Optional to Change):")
        layout.addWidget(self.image_path_label)

        h_layout = QHBoxLayout()
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setStyleSheet("background-color: #382c20; color: #f0e0d0; padding: 4px;")

        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setStyleSheet("background-color: #4a3828; color: #fff; padding: 4px 8px; border-radius: 4px;")
        self.btn_browse.clicked.connect(self.browse_image)

        h_layout.addWidget(self.image_path_edit)
        h_layout.addWidget(self.btn_browse)
        layout.addLayout(h_layout)

        self.combo.currentIndexChanged.connect(self.on_mode_changed)

        # Load previous states (last modality & last used image path)
        self.load_previous_state()

        layout.addStretch()

        start_btn = QPushButton("Launch Application")
        start_btn.setStyleSheet(
            "background-color: #5a4430; color: #fff; padding: 8px; border-radius: 4px; font-weight: bold;")
        start_btn.clicked.connect(self.accept)
        layout.addWidget(start_btn)

        self.setLayout(layout)
        self.selected_folder = "hex_modality"
        self.hd_image_path = ""

    def load_previous_state(self):
        # 1. Default to last used modality
        if GLOBAL_STATE_FILE.exists():
            try:
                with open(GLOBAL_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    last_modality = data.get("last_modality", "hex_modality")
                    for i in range(self.combo.count()):
                        if self.combo.itemData(i) == last_modality:
                            self.combo.setCurrentIndex(i)
                            break
            except Exception:
                pass

        # 2. Preload remembered image path from image modality's state file
        if IMAGE_STATE_FILE.exists():
            try:
                with open(IMAGE_STATE_FILE, "r", encoding="utf-8") as f:
                    img_data = json.load(f)
                    saved_img = img_data.get("hd_image_path", "")
                    if saved_img and os.path.exists(saved_img):
                        self.image_path_edit.setText(saved_img)
            except Exception:
                pass

        self.on_mode_changed()

    def on_mode_changed(self):
        is_image = (self.combo.currentData() == "image_modality")
        self.image_path_label.setVisible(is_image)
        self.image_path_edit.setVisible(is_image)
        self.btn_browse.setVisible(is_image)

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HD Map Image", filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.image_path_edit.setText(path)

    def save_global_state(self, modality):
        try:
            with open(GLOBAL_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_modality": modality}, f, indent=2)
        except Exception as e:
            print(f"Error saving global state: {e}")

    def accept(self):
        self.selected_folder = self.combo.currentData()
        self.save_global_state(self.selected_folder)

        if self.selected_folder == "image_modality":
            self.hd_image_path = self.image_path_edit.text()
            if not self.hd_image_path or not os.path.exists(self.hd_image_path):
                QMessageBox.warning(self, "Error", "Please select a valid HD map image file.")
                return
        super().accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    dialog = ModalitySelectorDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        folder = dialog.selected_folder
        img_path = dialog.hd_image_path

        if folder == "hex_modality":
            from hex_modality.app import run_modality

            run_modality()
        elif folder == "image_modality":
            from image_modality.app import run_modality

            run_modality(hd_image_path=img_path)
    else:
        sys.exit(0)