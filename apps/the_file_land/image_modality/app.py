import json
import os
import sys
from pathlib import Path
from typing import Optional
import yaml

from PyQt6.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap, QMouseEvent, QKeyEvent, QPolygonF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QMenu, QVBoxLayout,
    QLabel, QPushButton, QFileDialog,
    QGraphicsDropShadowEffect, QFrame, QHBoxLayout, QWidget, QRubberBand, QDialog
)

APP_PATH = Path(__file__).parent
STATE_FILE = APP_PATH / "layout_state.json"
SETTINGS_FILE = APP_PATH / "settings.yaml"


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


SETTINGS = load_settings()
ZOOM_MIN = 0.01
ZOOM_MAX = 5.0


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


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HD Image Map - Shortcuts & Help")
        self.resize(400, 320)
        self.setStyleSheet("background-color: #241c14; color: #f0e0d0;")

        layout = QVBoxLayout()
        title = QLabel("⌨️ Controls & Shortcuts Guide")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e0d0b0;")
        layout.addWidget(title)

        shortcuts_text = (
            "• **Left Click & Drag (Empty Space):** Pan / Move around the map.\n\n"
            "• **Left Click (Item):** Select an item.\n\n"
            "• **Ctrl + Click:** Multi-select items or add/remove from selection.\n\n"
            "• **Ctrl + Drag Box:** Box-select multiple items in bulk.\n\n"
            "• **Drag Selected Items:** Move all selected items together.\n\n"
            "• **Ctrl + Plus (+) / Ctrl + Scroll Up:** Resize selected items larger.\n\n"
            "• **Ctrl + Minus (-) / Ctrl + Scroll Down:** Resize selected items smaller.\n\n"
            "• **Delete / Backspace:** Remove selected items from the map.\n\n"
            "• **Double Click Item:** Open file or folder."
        )

        help_label = QLabel(shortcuts_text)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 10pt; line-height: 14px;")
        layout.addWidget(help_label)

        layout.addStretch()
        close_btn = QPushButton("Got it")
        close_btn.setStyleSheet(
            "background-color: #4a3828; color: #fff; padding: 6px; border-radius: 4px; font-weight: bold;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.setLayout(layout)


class ImageMarkerItem(QGraphicsItem):
    def __init__(self, path: str, is_dir: bool, x: float, y: float, scale_factor: float = 1.0, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_dir = is_dir
        self.name = os.path.basename(path) or path
        self.setPos(x, y)
        self.base_width = 90
        self.base_height = 95
        self.item_scale = scale_factor

        # Ensure markers always render above the background image
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._pixmap_cache: Optional[QPixmap] = None

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)

    def boundingRect(self) -> QRectF:
        w = self.base_width * self.item_scale
        h = self.base_height * self.item_scale
        return QRectF(-w / 2, -h / 2, w, h)

    def paint(self, painter: QPainter, option, widget):
        view = self.scene().views()[0] if self.scene() else None
        painter.setOpacity(1.0 if self.isSelected() else 0.85)

        w = self.base_width * self.item_scale
        h = self.base_height * self.item_scale

        painter.setBrush(QBrush(QColor(248, 245, 235, 200) if self.is_dir else QColor(255, 248, 180, 200)))
        painter.setPen(QPen(QColor(218, 165, 32), 2) if self.isSelected() else QPen(QColor(60, 50, 40, 180), 1.5))
        painter.drawRoundedRect(QRectF(-w / 2, -h / 2, w, h - (30 * self.item_scale)), 12 * self.item_scale,
                                12 * self.item_scale)

        if not self._pixmap_cache:
            self._pixmap_cache = get_system_icon(self.path, self.is_dir)

        icon_size = int(54 * self.item_scale)
        scaled_pixmap = self._pixmap_cache.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)

        painter.drawPixmap(QPointF(-scaled_pixmap.width() / 2, -h / 2 + (5 * self.item_scale)), scaled_pixmap)

        painter.setBrush(QBrush(QColor(15, 12, 10, 230)))
        painter.setPen(QPen(QColor(218, 165, 32), 1) if self.isSelected() else QPen(QColor(60, 50, 40), 1))

        text_bg_height = 32 * self.item_scale
        text_bg_rect = QRectF(-w / 2, h / 2 - text_bg_height - (4 * self.item_scale), w, text_bg_height)
        painter.drawRoundedRect(text_bg_rect, 5, 5)

        painter.setPen(QColor(255, 248, 230))
        font_size = max(8, int(10 * self.item_scale))
        font = QFont(SETTINGS.get("appearance", {}).get("font_family", "Georgia"), font_size)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(text_bg_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.name)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            import subprocess
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", self.path])
                elif sys.platform == "win32":
                    os.startfile(self.path)
                else:
                    subprocess.Popen(["xdg-open", self.path])
            except Exception as e:
                print(f"Error opening {self.path}: {e}")
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MiniMapWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.setFixedSize(180, 140)
        self.setStyleSheet("background-color: rgba(26, 21, 16, 210); border: 2px solid #5a4430; border-radius: 6px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.mw.hd_pixmap and not self.mw.hd_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.mw.hd_pixmap)
        else:
            painter.fillRect(self.rect(), QBrush(QColor(27, 54, 93)))

        img_w = self.mw.hd_pixmap.width() if (self.mw.hd_pixmap and not self.mw.hd_pixmap.isNull()) else 1000
        img_h = self.mw.hd_pixmap.height() if (self.mw.hd_pixmap and not self.mw.hd_pixmap.isNull()) else 1000

        painter.setBrush(QBrush(QColor(218, 165, 32)))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        for item in self.mw.scene.items():
            if isinstance(item, ImageMarkerItem):
                mx = (item.pos().x() / img_w) * self.width()
                my = (item.pos().y() / img_h) * self.height()
                painter.drawEllipse(QPointF(mx, my), 3.5, 3.5)

        view = self.mw.view
        viewport_scene_rect = view.mapToScene(view.viewport().rect()).boundingRect()

        tl_x = (viewport_scene_rect.left() / img_w) * self.width()
        tl_y = (viewport_scene_rect.top() / img_h) * self.height()
        br_x = (viewport_scene_rect.right() / img_w) * self.width()
        br_y = (viewport_scene_rect.bottom() / img_h) * self.height()

        cam_rect = QRectF(tl_x, tl_y, br_x - tl_x, br_y - tl_y)
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
        painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
        painter.drawRect(cam_rect)

    def mousePressEvent(self, event: QMouseEvent):
        self.pan_to_click(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        self.pan_to_click(event.position())

    def pan_to_click(self, pos: QPointF):
        if self.mw.hd_pixmap and not self.mw.hd_pixmap.isNull():
            img_w = self.mw.hd_pixmap.width()
            img_h = self.mw.hd_pixmap.height()
            wx = (pos.x() / self.width()) * img_w
            wy = (pos.y() / self.height()) * img_h
            self.mw.view.centerOn(wx, wy)
            self.update()


class MainWindow(QMainWindow):
    def __init__(self, hd_image_path=""):
        super().__init__()
        self.hd_image_path = hd_image_path
        self.hd_pixmap = None
        self.setWindowTitle("The File Land - HD Image Modality")
        self.resize(1200, 800)

        self.scene = QGraphicsScene()

        # 1. Resolve background image path first (from argument or state file)
        if hd_image_path and os.path.exists(hd_image_path):
            self.hd_image_path = hd_image_path
        else:
            self.hd_image_path = self.get_path_from_state()

        # 2. Setup background pixmap with a negative Z-value so it stays at the back
        if self.hd_image_path and os.path.exists(self.hd_image_path):
            self.hd_pixmap = QPixmap(self.hd_image_path)
            if not self.hd_pixmap.isNull():
                bg_item = self.scene.addPixmap(self.hd_pixmap)
                bg_item.setZValue(-10)
                self.scene.setSceneRect(QRectF(self.hd_pixmap.rect()))

        # 3. Load saved marker items afterwards so they render on top of the background
        self.load_state()

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        if self.hd_pixmap and not self.hd_pixmap.isNull():
            self.view.centerOn(self.hd_pixmap.width() / 2, self.hd_pixmap.height() / 2)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #241c14; border-bottom: 1px solid #3c2e20;")
        top_layout = QHBoxLayout(top_bar)
        title = QLabel("🗺️ HD Image Map Explorer (Bulk Move & Resize Support)")
        title.setStyleSheet("color: #e0d0b0; font-weight: bold; font-size: 14pt;")
        top_layout.addWidget(title)

        top_layout.addStretch()
        change_bg_btn = QPushButton("📷 Change Background")
        change_bg_btn.setStyleSheet("background-color: #4a3828; color: #f0e0d0; padding: 5px 10px; border-radius: 4px;")
        change_bg_btn.clicked.connect(self.change_background_image)
        top_layout.addWidget(change_bg_btn)

        layout.addWidget(top_bar)
        layout.addWidget(self.view)
        self.setCentralWidget(central)

        self.minimap = MiniMapWidget(self, self.view)

        # Floating Help Button at bottom-left
        self.help_btn = QPushButton("❓ Help", self)
        self.help_btn.setStyleSheet(
            "background-color: rgba(36, 28, 20, 230); color: #f0e0d0; border: 1px solid #5a4430; "
            "padding: 6px 12px; border-radius: 6px; font-weight: bold;"
        )
        self.help_btn.clicked.connect(self.show_help_dialog)

        self.selected_items = []
        self.is_dragging = False
        self.is_panning = False
        self.is_selecting_box = False
        self.drag_start = QPointF()
        self.pan_start = QPointF()
        self.box_start = QPointF()
        self.item_starts = {}
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.view.viewport())

        self.view.viewport().installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.minimap.move(self.width() - self.minimap.width() - 20, self.height() - self.minimap.height() - 40)
        self.help_btn.move(20, self.height() - self.help_btn.height() - 40)

    def show_help_dialog(self):
        dlg = HelpDialog(self)
        dlg.exec()

    def get_path_from_state(self) -> str:
        if not STATE_FILE.exists():
            return ""
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("hd_image_path", "")
        except Exception:
            return ""

    def change_background_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HD Map Background Image",
                                              filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.hd_image_path = path
            self.hd_pixmap = QPixmap(path)
            if not self.hd_pixmap.isNull():
                for item in self.scene.items():
                    if isinstance(item, QGraphicsItem) and not isinstance(item, ImageMarkerItem):
                        self.scene.removeItem(item)
                bg_item = self.scene.addPixmap(self.hd_pixmap)
                bg_item.setZValue(-10)
                self.scene.setSceneRect(QRectF(self.hd_pixmap.rect()))
                self.view.centerOn(self.hd_pixmap.width() / 2, self.hd_pixmap.height() / 2)
                self.save_state()
                self.scene.update()
                self.minimap.update()

    def eventFilter(self, obj, event):
        if obj == self.view.viewport():
            etype = event.type()
            if etype == QEvent.Type.MouseButtonPress:
                scene_pos = self.view.mapToScene(event.position().toPoint())
                clicked = self.scene.itemAt(scene_pos, self.view.transform())
                modifiers = QApplication.keyboardModifiers()

                if event.button() == Qt.MouseButton.RightButton:
                    self.show_menu(event.position())
                    return True
                elif event.button() == Qt.MouseButton.LeftButton:
                    if clicked and isinstance(clicked, ImageMarkerItem):
                        if modifiers & Qt.KeyboardModifier.ControlModifier:
                            clicked.setSelected(not clicked.isSelected())
                        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                            clicked.setSelected(True)
                        else:
                            if not clicked.isSelected():
                                self.scene.clearSelection()
                                clicked.setSelected(True)

                        self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, ImageMarkerItem)]
                        if clicked.isSelected():
                            self.is_dragging = True
                            self.drag_start = scene_pos
                            self.item_starts = {item: item.pos() for item in self.selected_items}
                        return True
                    elif modifiers & Qt.KeyboardModifier.ControlModifier:
                        self.is_selecting_box = True
                        self.box_start = event.position()
                        self.rubber_band.setGeometry(QRectF(self.box_start, self.box_start).toRect())
                        self.rubber_band.show()
                        return True
                    else:
                        self.scene.clearSelection()
                        self.selected_items = []
                        self.is_panning = True
                        self.pan_start = event.globalPosition()
                        self.view.setCursor(Qt.CursorShape.ClosedHandCursor)
                        return True
            elif etype == QEvent.Type.MouseMove:
                if self.is_dragging:
                    delta = self.view.mapToScene(event.position().toPoint()) - self.drag_start
                    for item, start in self.item_starts.items():
                        item.setPos(start + delta)
                    self.scene.update()
                    self.minimap.update()
                    return True
                elif self.is_selecting_box:
                    self.rubber_band.setGeometry(QRectF(self.box_start, event.position()).toRect().normalized())
                    return True
                elif self.is_panning:
                    delta = event.globalPosition() - self.pan_start
                    self.pan_start = event.globalPosition()
                    h, v = self.view.horizontalScrollBar(), self.view.verticalScrollBar()
                    h.setValue(int(h.value() - delta.x()))
                    v.setValue(int(v.value() - delta.y()))
                    self.minimap.update()
                    return True
            elif etype == QEvent.Type.MouseButtonRelease:
                if self.is_dragging:
                    self.is_dragging = False
                    self.save_state()
                    self.scene.update()
                    self.minimap.update()
                    return True
                if self.is_selecting_box:
                    self.is_selecting_box = False
                    self.rubber_band.hide()
                    rect = QRectF(self.view.mapToScene(self.rubber_band.geometry()).boundingRect())
                    if not (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier):
                        self.scene.clearSelection()
                    for item in self.scene.items(rect):
                        if isinstance(item, ImageMarkerItem):
                            item.setSelected(True)
                    self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, ImageMarkerItem)]
                    self.scene.update()
                    return True
                if self.is_panning:
                    self.is_panning = False
                    self.view.setCursor(Qt.CursorShape.ArrowCursor)
                    return True
            elif etype == QEvent.Type.Wheel:
                modifiers = QApplication.keyboardModifiers()
                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    selected = [i for i in self.scene.selectedItems() if isinstance(i, ImageMarkerItem)]
                    if selected:
                        factor = 1.08 if event.angleDelta().y() > 0 else (1.0 / 1.08)
                        for item in selected:
                            item.item_scale = max(0.3, min(4.0, item.item_scale * factor))
                            item.prepareGeometryChange()
                        self.save_state()
                        self.scene.update()
                        return True

                factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
                if ZOOM_MIN < self.view.transform().m11() * factor < ZOOM_MAX:
                    self.view.scale(factor, factor)
                    self.minimap.update()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal,
                                                                               Qt.Key.Key_Minus):
            selected = [i for i in self.scene.selectedItems() if isinstance(i, ImageMarkerItem)]
            if selected:
                factor = 1.12 if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal) else (1.0 / 1.12)
                for item in selected:
                    item.item_scale = max(0.3, min(4.0, item.item_scale * factor))
                    item.prepareGeometryChange()
                self.save_state()
                self.scene.update()
                event.accept()
                return

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in [i for i in self.scene.selectedItems() if isinstance(i, ImageMarkerItem)]:
                self.scene.removeItem(item)
            self.selected_items.clear()
            self.save_state()
            self.scene.update()
            self.minimap.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def show_menu(self, pos):
        scene_pos = self.view.mapToScene(pos.toPoint())
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #241c14; color: #f0e0d0; border: 1px solid #4a3828;")
        f_act = menu.addAction("📁 Add Folder Link")
        i_act = menu.addAction("📄 Add File Link")
        action = menu.exec(self.view.mapToGlobal(pos.toPoint()))
        if action in (f_act, i_act):
            path = QFileDialog.getExistingDirectory(self, "Select Folder") if action == f_act else \
            QFileDialog.getOpenFileName(self, "Select File")[0]
            if path:
                item = ImageMarkerItem(path, action == f_act, scene_pos.x(), scene_pos.y())
                self.scene.addItem(item)
                self.scene.clearSelection()
                item.setSelected(True)
                self.selected_items = [item]
                self.save_state()
                self.scene.update()
                self.minimap.update()

    def save_state(self):
        data = {
            "hd_image_path": self.hd_image_path,
            "items": [{
                "path": i.path,
                "is_dir": i.is_dir,
                "x": i.pos().x(),
                "y": i.pos().y(),
                "scale": i.item_scale
            } for i in self.scene.items() if isinstance(i, ImageMarkerItem)]
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

    def load_state(self):
        if not os.path.exists(STATE_FILE): return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("items", []):
                    if os.path.exists(entry["path"]):
                        item = ImageMarkerItem(
                            entry["path"],
                            entry["is_dir"],
                            entry["x"],
                            entry["y"],
                            scale_factor=entry.get("scale", 1.0)
                        )
                        self.scene.addItem(item)
        except Exception as e:
            print(f"Error loading state: {e}")


def run_modality(hd_image_path=""):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(hd_image_path=hd_image_path)
    window.show()
    sys.exit(app.exec())