import json
import math
import os
import sys
from pathlib import Path
from typing import List, Optional

import yaml  # Requires PyYAML package

from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QEvent, QLineF
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QPixmap,
    QMouseEvent, QKeyEvent
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QMenu, QDialog, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog,
    QGraphicsDropShadowEffect, QFrame, QHBoxLayout, QWidget
)

APP_PATH = Path(__file__).parent
STATE_FILE = f"{APP_PATH}/layout_state.json"
SETTINGS_FILE = f"{APP_PATH}/settings.yaml"


# --- Configuration Loader ---
def load_settings(path: str = SETTINGS_FILE) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_settings(settings: dict, path: str = SETTINGS_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(settings, f, sort_keys=False, allow_unicode=True)
    except Exception as e:
        print(f"Error saving settings: {e}")


SETTINGS = load_settings()

# --- Constants ---
GRID_SIZE = 100
ZOOM_MIN = 0.1
ZOOM_MAX = 5.0


# --- Helper Functions ---
def get_system_icon(path: str, is_dir: bool) -> QPixmap:
    defaults = SETTINGS.get("defaults", {})
    custom_icon = defaults.get("folder_icon" if is_dir else "file_icon", "")

    if custom_icon and os.path.exists(custom_icon):
        pix = QPixmap(custom_icon)
        if not pix.isNull():
            return pix

    color = QColor(139, 115, 85) if is_dir else QColor(210, 180, 140)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(QColor(60, 40, 20), 2))
    painter.drawRoundedRect(4, 4, 56, 56, 8, 8)

    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Arial", 22, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "📁" if is_dir else "📄")
    painter.end()

    return pixmap


# --- Custom Graphics Items ---
class SpatialItem(QGraphicsItem):
    """Base class for all map items."""

    def __init__(self, path: str, is_dir: bool, x: float, y: float, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_dir = is_dir
        self.name = os.path.basename(path) or path

        self.width = 90
        self.height = 95
        self.setPos(x, y)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self._pixmap_cache: Optional[QPixmap] = None

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)

    def boundingRect(self) -> QRectF:
        return QRectF(-self.width / 2, -self.height / 2, self.width, self.height)

    def paint(self, painter: QPainter, option, widget):
        view = self.scene().views()[0] if self.scene() else None
        if view:
            scale = view.transform().m11()
            lod_threshold = SETTINGS.get("appearance", {}).get("lod_threshold_zoom", 0.5)
            if scale < lod_threshold:
                painter.setBrush(QBrush(QColor(180, 160, 130)))
                painter.drawEllipse(QPointF(0, 0), 6, 6)
                return

        if not self._pixmap_cache:
            self._pixmap_cache = get_system_icon(self.path, self.is_dir)

        scale_factor = max(0.5, min(1.5, view.transform().m11() if view else 1.0))
        scaled_pixmap = self._pixmap_cache.scaled(
            int(54 * scale_factor), int(54 * scale_factor),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        dx = -scaled_pixmap.width() / 2
        dy = -self.height / 2 + 5
        painter.drawPixmap(QPointF(dx, dy), scaled_pixmap)

        painter.setPen(QColor(240, 230, 210))
        font_family = SETTINGS.get("appearance", {}).get("font_family", "Georgia")
        font = QFont(font_family, 10)
        font.setBold(True)
        painter.setFont(font)

        text_rect = QRectF(-self.width / 2, self.height / 2 - 35, self.width, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.name)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_item()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def open_item(self):
        import subprocess
        try:
            target_path = self.path
            if sys.platform == "darwin":
                subprocess.Popen(["open", target_path])
            elif sys.platform == "win32":
                os.startfile(target_path)
            else:
                subprocess.Popen(["xdg-open", target_path])
        except Exception as e:
            print(f"Error opening {target_path}: {e}")


class BackgroundGrid(QGraphicsItem):
    """Infinite grid background styled like an old map."""

    def __init__(self):
        super().__init__()
        self.setZValue(-10)

    def boundingRect(self) -> QRectF:
        return QRectF(-200000, -200000, 400000, 400000)

    def paint(self, painter: QPainter, option, widget):
        view = self.scene().views()[0] if self.scene() else None
        if not view:
            return

        rect = view.mapToScene(view.viewport().rect()).boundingRect()
        grid_color = SETTINGS.get("appearance", {}).get("grid_color", "#a08060")
        painter.setPen(QPen(QColor(grid_color), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        scale = view.transform().m11()
        if scale < 0.05:
            return

        step = GRID_SIZE / scale
        if step < 15:
            step = 15.0

        start_x = math.floor(rect.left() / step) * step
        end_x = math.ceil(rect.right() / step) * step
        start_y = math.floor(rect.top() / step) * step
        end_y = math.ceil(rect.bottom() / step) * step

        top = float(rect.top())
        bottom = float(rect.bottom())
        left = float(rect.left())
        right = float(rect.right())

        n_cols = int((end_x - start_x) / step) + 1
        n_rows = int((end_y - start_y) / step) + 1
        if n_cols > 1500 or n_rows > 1500:
            return

        x = start_x
        for _ in range(n_cols):
            painter.drawLine(QLineF(x, top, x, bottom))
            x += step

        y = start_y
        for _ in range(n_rows):
            painter.drawLine(QLineF(left, y, right, y))
            y += step


# --- Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map Explorer Settings")
        self.resize(440, 280)
        self.setStyleSheet("background-color: #241c14; color: #f0e0d0;")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Default Folder Icon Path:"))
        self.folder_path_edit = QLineEdit(SETTINGS.get("defaults", {}).get("folder_icon", ""))
        btn_folder = QPushButton("Browse")
        btn_folder.clicked.connect(lambda: self.browse_path(self.folder_path_edit))
        h_layout_f = QHBoxLayout()
        h_layout_f.addWidget(self.folder_path_edit)
        h_layout_f.addWidget(btn_folder)
        layout.addLayout(h_layout_f)

        layout.addWidget(QLabel("Default File Icon Path:"))
        self.file_path_edit = QLineEdit(SETTINGS.get("defaults", {}).get("file_icon", ""))
        btn_file = QPushButton("Browse")
        btn_file.clicked.connect(lambda: self.browse_path(self.file_path_edit))
        h_layout_i = QHBoxLayout()
        h_layout_i.addWidget(self.file_path_edit)
        h_layout_i.addWidget(btn_file)
        layout.addLayout(h_layout_i)

        layout.addStretch()

        save_btn = QPushButton("Save & Close")
        save_btn.setStyleSheet("background-color: #4a3828; color: #fff; padding: 6px; border-radius: 4px;")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def browse_path(self, line_edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image Icon", filter="Images (*.png *.xpm *.jpg)")
        if path:
            line_edit.setText(path)


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Infinite Map File Explorer")
        self.resize(1200, 800)

        # Scene Setup
        self.scene = QGraphicsScene()
        bg_color = SETTINGS.get("appearance", {}).get("background_color", "#1a1510")
        self.scene.setBackgroundBrush(QColor(bg_color))

        # Grid
        self.grid_item = BackgroundGrid()
        self.scene.addItem(self.grid_item)

        # View Setup
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.view.setSceneRect(-100000, -100000, 200000, 200000)
        self.view.centerOn(0, 0)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #241c14; border-bottom: 1px solid #3c2e20;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(15, 8, 15, 8)

        title_label = QLabel("🗺️ The File Land")
        title_label.setStyleSheet("color: #e0d0b0; font-weight: bold; font-size: 14pt;")
        top_layout.addWidget(title_label)
        top_layout.addStretch()

        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setStyleSheet(
            "background-color: #382c20; color: #f0e0d0; border: 1px solid #5a4430; padding: 6px 12px; border-radius: 4px;"
        )
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn)

        main_layout.addWidget(top_bar)
        main_layout.addWidget(self.view)
        self.setCentralWidget(central_widget)

        self.selected_items: List[SpatialItem] = []
        self.is_dragging_items = False
        self.is_panning_view = False
        self.drag_mouse_start = QPointF()
        self.pan_mouse_start = QPointF()
        self.item_start_positions = {}

        self.load_layout_state()
        self.view.viewport().installEventFilter(self)

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if "defaults" not in SETTINGS:
                SETTINGS["defaults"] = {}
            SETTINGS["defaults"]["folder_icon"] = dialog.folder_path_edit.text()
            SETTINGS["defaults"]["file_icon"] = dialog.file_path_edit.text()

            # Persist changes to settings.yaml
            save_settings(SETTINGS)

            for item in self.scene.items():
                if isinstance(item, SpatialItem):
                    item._pixmap_cache = None
            self.scene.update()
            QMessageBox.information(self, "Settings", "Settings saved and applied successfully.")

    def eventFilter(self, obj, event):
        if obj == self.view.viewport():
            etype = event.type()

            if etype == QEvent.Type.MouseButtonPress:
                mouse_event = event
                scene_pos = self.view.mapToScene(mouse_event.position().toPoint())
                clicked_item = self.scene.itemAt(scene_pos, self.view.transform())

                if mouse_event.button() == Qt.MouseButton.RightButton:
                    self.show_context_menu(mouse_event.position())
                    return True

                if mouse_event.button() == Qt.MouseButton.LeftButton:
                    modifiers = QApplication.keyboardModifiers()

                    if modifiers == Qt.KeyboardModifier.ControlModifier:
                        if clicked_item and isinstance(clicked_item, SpatialItem):
                            if not clicked_item.isSelected():
                                clicked_item.setSelected(True)
                            self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]

                            self.is_dragging_items = True
                            self.drag_mouse_start = scene_pos
                            self.item_start_positions = {item: item.pos() for item in self.selected_items}
                            return True
                    else:
                        if clicked_item and isinstance(clicked_item, SpatialItem):
                            if not clicked_item.isSelected():
                                clicked_item.setSelected(True)
                            self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]
                        else:
                            self.scene.clearSelection()
                            self.selected_items = []
                            self.is_panning_view = True
                            self.pan_mouse_start = mouse_event.globalPosition()
                            self.view.setCursor(Qt.CursorShape.ClosedHandCursor)
                            return True

            elif etype == QEvent.Type.MouseMove:
                mouse_event = event
                if self.is_dragging_items:
                    current_scene_pos = self.view.mapToScene(mouse_event.position().toPoint())
                    delta = current_scene_pos - self.drag_mouse_start
                    for item, start_pos in self.item_start_positions.items():
                        item.setPos(start_pos + delta)
                    return True
                elif self.is_panning_view:
                    global_pos = mouse_event.globalPosition()
                    delta = global_pos - self.pan_mouse_start
                    self.pan_mouse_start = global_pos

                    h_bar = self.view.horizontalScrollBar()
                    v_bar = self.view.verticalScrollBar()
                    h_bar.setValue(int(h_bar.value() - delta.x()))
                    v_bar.setValue(int(v_bar.value() - delta.y()))
                    return True

            elif etype == QEvent.Type.MouseButtonRelease:
                if self.is_dragging_items:
                    self.is_dragging_items = False
                    self.save_layout_state()
                    return True
                if self.is_panning_view:
                    self.is_panning_view = False
                    self.view.setCursor(Qt.CursorShape.ArrowCursor)
                    return True

            elif etype == QEvent.Type.Wheel:
                wheel_event = event
                angle = wheel_event.angleDelta().y()
                factor = 1.15 if angle > 0 else 1.0 / 1.15

                current_scale = self.view.transform().m11()
                if (factor > 1.0 and current_scale < ZOOM_MAX) or (factor < 1.0 and current_scale > ZOOM_MIN):
                    self.view.scale(factor, factor)
                return True

        return super().eventFilter(obj, event)

    def show_context_menu(self, pos: QPointF):
        scene_pos = self.view.mapToScene(pos.toPoint())
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #241c14; color: #f0e0d0; border: 1px solid #4a3828;")

        add_folder_action = menu.addAction("📁 Add Folder Link Here")
        add_file_action = menu.addAction("📄 Add File Link Here")

        action = menu.exec(self.view.mapToGlobal(pos.toPoint()))

        if action == add_folder_action:
            self.add_item(scene_pos.x(), scene_pos.y(), is_dir=True)
        elif action == add_file_action:
            self.add_item(scene_pos.x(), scene_pos.y(), is_dir=False)

    def add_item(self, x: float, y: float, is_dir: bool):
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Select Folder to Map")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File to Map")

        if not path:
            return

        item = SpatialItem(path, is_dir, x, y)
        self.scene.addItem(item)
        item.setSelected(True)
        self.selected_items = [item]
        self.save_layout_state()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete:
            for item in self.selected_items:
                self.scene.removeItem(item)
            self.selected_items.clear()
            self.save_layout_state()
            event.accept()
            return
        super().keyPressEvent(event)

    def save_layout_state(self):
        data = []
        for item in self.scene.items():
            if isinstance(item, SpatialItem):
                data.append({
                    "path": item.path,
                    "is_dir": item.is_dir,
                    "x": item.pos().x(),
                    "y": item.pos().y()
                })
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving layout state: {e}")

    def load_layout_state(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data:
                    path = entry.get("path")
                    if path and os.path.exists(path):
                        item = SpatialItem(path, entry.get("is_dir", False), entry.get("x", 0), entry.get("y", 0))
                        self.scene.addItem(item)
        except Exception as e:
            print(f"Error loading layout state: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont(SETTINGS.get("appearance", {}).get("font_family", "Georgia"))
    font.setPointSize(11)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())