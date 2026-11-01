import json
import math
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Set
import yaml

from PyQt6.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap, QMouseEvent, QKeyEvent, QPolygonF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QMenu, QDialog, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog,
    QGraphicsDropShadowEffect, QFrame, QHBoxLayout, QWidget, QCheckBox, QRubberBand,
    QComboBox, QSpinBox
)

APP_PATH = Path(__file__).parent
STATE_FILE = APP_PATH / "layout_state.json"
SETTINGS_FILE = APP_PATH / "settings.yaml"


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(settings, f, sort_keys=False, allow_unicode=True)
    except Exception as e:
        print(f"Error saving settings: {e}")


SETTINGS = load_settings()

ZOOM_MIN = 0.01
ZOOM_MAX = 5.0


def pixel_to_hex(x: float, y: float, size: float) -> Tuple[int, int]:
    q = (math.sqrt(3) / 3 * x - 1 / 3 * y) / size
    r = (2 / 3 * y) / size
    return axial_round(q, r)


def axial_round(q_frac: float, r_frac: float) -> Tuple[int, int]:
    s_frac = -q_frac - r_frac
    q = round(q_frac)
    r = round(r_frac)
    s = round(s_frac)
    q_diff = abs(q - q_frac)
    r_diff = abs(r - r_frac)
    s_diff = abs(s - s_frac)
    if q_diff > r_diff and q_diff > s_diff:
        q = -r - s
    elif r_diff > s_diff:
        r = -q - s
    return (q, r)


def hex_to_pixel(q: int, r: int, size: float) -> QPointF:
    x = size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
    y = size * (3 / 2 * r)
    return QPointF(x, y)


def get_hex_polygon(center: QPointF, size: float) -> QPolygonF:
    points = []
    for i in range(6):
        angle_deg = 60 * i - 30
        angle_rad = math.radians(angle_deg)
        points.append(QPointF(center.x() + size * math.cos(angle_rad), center.y() + size * math.sin(angle_rad)))
    return QPolygonF(points)


def get_hexes_in_radius(q: int, r: int, radius: int) -> List[Tuple[int, int]]:
    results = []
    for dq in range(-radius, radius + 1):
        for dr in range(max(-radius, -dq - radius), min(radius, -dq + radius) + 1):
            results.append((q + dq, r + dr))
    return results


def get_spiral_hex_ring(q: int, r: int, radius: int) -> List[Tuple[int, int]]:
    results = [(q, r)]
    for k in range(1, radius + 1):
        curr_q = q + k
        curr_r = r - k
        for i in range(6):
            for _ in range(k):
                results.append((curr_q, curr_r))
                directions = [(0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0)]
                dq, dr = directions[i]
                curr_q += dq
                curr_r += dr
    return results


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


class SpatialItem(QGraphicsItem):
    def __init__(self, path: str, is_dir: bool, q: int, r: int, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_dir = is_dir
        self.name = os.path.basename(path) or path
        self.q = q
        self.r = r
        self.width = 90
        self.height = 95

        topo_config = SETTINGS.get("topography", {})
        hex_size = topo_config.get("hex_size", 55.0)
        self.setPos(hex_to_pixel(q, r, hex_size))
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
        if view and view.transform().m11() < SETTINGS.get("appearance", {}).get("lod_threshold_zoom", 0.5):
            painter.setBrush(QBrush(QColor(180, 160, 130)))
            painter.drawEllipse(QPointF(0, 0), 6, 6)
            return

        painter.setOpacity(1.0 if self.isSelected() else 0.65)
        if not self._pixmap_cache:
            self._pixmap_cache = get_system_icon(self.path, self.is_dir)

        scale_factor = max(0.5, min(1.5, view.transform().m11() if view else 1.0))
        scaled_pixmap = self._pixmap_cache.scaled(int(54 * scale_factor), int(54 * scale_factor),
                                                  Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)

        painter.drawPixmap(QPointF(-scaled_pixmap.width() / 2, -self.height / 2 + 5), scaled_pixmap)

        painter.setBrush(QBrush(QColor(15, 12, 10, 230)))
        painter.setPen(QPen(QColor(218, 165, 32), 1) if self.isSelected() else QPen(QColor(60, 50, 40), 1))
        text_bg_rect = QRectF(-self.width / 2, self.height / 2 - 36, self.width, 32)
        painter.drawRoundedRect(text_bg_rect, 5, 5)

        painter.setPen(QColor(255, 248, 230))
        font = QFont(SETTINGS.get("appearance", {}).get("font_family", "Georgia"), 10)
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


class HexTopographyMap(QGraphicsItem):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.setZValue(-10)

    def boundingRect(self) -> QRectF:
        return QRectF(-200000, -200000, 400000, 400000)

    def paint(self, painter: QPainter, option, widget):
        view = self.scene().views()[0] if self.scene() else None
        if not view: return
        topo_config = SETTINGS.get("topography", {})
        if not topo_config.get("enabled", True):
            painter.fillRect(view.mapToScene(view.viewport().rect()).boundingRect(),
                             QBrush(QColor(SETTINGS.get("appearance", {}).get("background_color", "#1b365d"))))
            return

        rect = view.mapToScene(view.viewport().rect()).boundingRect()
        ocean_color = QColor(topo_config.get("ocean_color", "#1b365d"))
        painter.fillRect(rect, QBrush(ocean_color))
        scale = view.transform().m11()
        if scale < 0.02: return

        hex_size = topo_config.get("hex_size", 55.0)
        land_color = QColor(topo_config.get("land_color", "#d8c29d"))
        forest_color = QColor("#345e38")
        mountain_color = QColor("#787878")
        desert_color = QColor("#d4a359")
        coast_color = QColor(topo_config.get("coastline_color", "#6b533b"))
        wave_color = QColor(topo_config.get("wave_color", "#284b7d"))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if scale > 0.15:
            painter.setPen(QPen(wave_color, 1.5, Qt.PenStyle.SolidLine))
            step_w = hex_size * 3
            for y in range(int(math.floor(rect.top() / step_w) * step_w),
                           int(math.ceil(rect.bottom() / step_w) * step_w) + 1, int(step_w * 2)):
                for x in range(int(math.floor(rect.left() / step_w) * step_w),
                               int(math.ceil(rect.right() / step_w) * step_w) + 1, int(step_w * 2)):
                    painter.drawArc(QRectF(x, y, 20, 10), 0, 180 * 16)

        item_locations = {(item.q, item.r): item for item in self.mw.scene.items() if isinstance(item, SpatialItem)}

        for (q, r), tile_data in self.mw.hex_grid_data.items():
            center = hex_to_pixel(q, r, hex_size)
            if not rect.contains(center): continue
            poly = get_hex_polygon(center, hex_size)
            terrain = tile_data.get("terrain", "land")

            if terrain == "forest":
                painter.setBrush(QBrush(forest_color))
                painter.setPen(QPen(QColor(20, 40, 20), 1.5))
            elif terrain == "mountain":
                painter.setBrush(QBrush(mountain_color))
                painter.setPen(QPen(QColor(40, 40, 40), 1.5))
            elif terrain == "desert":
                painter.setBrush(QBrush(desert_color))
                painter.setPen(QPen(QColor(100, 70, 30), 1.5))
            elif terrain == "land":
                painter.setBrush(QBrush(land_color))
                painter.setPen(QPen(coast_color, 1.5))
            else:
                grid_color = QColor(SETTINGS.get("appearance", {}).get("grid_color", "#2c4c7c"))
                grid_color.setAlphaF(SETTINGS.get("appearance", {}).get("grid_alpha", 0.3))
                painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                painter.setPen(QPen(grid_color, 0.5))
            painter.drawPolygon(poly)

        for (q, r), item in item_locations.items():
            center = hex_to_pixel(q, r, hex_size)
            if not rect.contains(center): continue
            poly = get_hex_polygon(center, hex_size)
            painter.setBrush(QBrush(QColor(248, 245, 235) if item.is_dir else QColor(255, 248, 180)))
            painter.setPen(QPen(QColor(40, 30, 20) if item.is_dir else QColor(180, 40, 30), 2.5))
            painter.drawPolygon(poly)


class MiniMapWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.setFixedSize(180, 140)
        self.setStyleSheet("background-color: rgba(26, 21, 16, 210); border: 2px solid #5a4430; border-radius: 6px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QBrush(QColor(27, 54, 93)))
        world_range = 10000.0
        w, h = self.width(), self.height()

        def world_to_mini(pt: QPointF):
            return QPointF((pt.x() + world_range / 2) / world_range * w, (pt.y() + world_range / 2) / world_range * h)

        for (q, r), tile in self.mw.hex_grid_data.items():
            if tile.get("terrain") != "ocean":
                painter.setBrush(QBrush(QColor(216, 194, 157)))
                painter.setPen(Qt.PenStyle.NoPen)
                topo_config = SETTINGS.get("topography", {})
                painter.drawEllipse(world_to_mini(hex_to_pixel(q, r, topo_config.get("hex_size", 55.0))), 2.5, 2.5)

        painter.setBrush(QBrush(QColor(218, 165, 32)))
        for item in self.mw.scene.items():
            if isinstance(item, SpatialItem):
                painter.drawEllipse(world_to_mini(item.pos()), 3, 3)

    def mousePressEvent(self, event: QMouseEvent):
        self.pan(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        self.pan(event.position())

    def pan(self, pos: QPointF):
        world_range = 10000.0
        self.mw.view.centerOn((pos.x() / self.width()) * world_range - world_range / 2,
                              (pos.y() / self.height()) * world_range - world_range / 2)
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("The File Land - Hexagon Modality")
        self.resize(1200, 800)
        self.hex_grid_data = {}
        self.regions = {}

        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor(SETTINGS.get("appearance", {}).get("background_color", "#1b365d")))
        self.scene.addItem(HexTopographyMap(self))

        self.view = QGraphicsView(self.scene)
        self.view.setSceneRect(-100000, -100000, 200000, 200000)
        self.view.centerOn(0, 0)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #241c14; border-bottom: 1px solid #3c2e20;")
        top_layout = QHBoxLayout(top_bar)

        title = QLabel("🗺️ Hex Map Explorer")
        title.setStyleSheet("color: #e0d0b0; font-weight: bold; font-size: 14pt;")
        top_layout.addWidget(title)
        top_layout.addSpacing(20)

        self.brush_mode_checkbox = QCheckBox("Paint Mode")
        self.brush_mode_checkbox.setStyleSheet("color: #f0e0d0; font-weight: bold;")
        top_layout.addWidget(self.brush_mode_checkbox)

        self.terrain_combo = QComboBox()
        self.terrain_combo.addItems(["Land", "Forest", "Mountain", "Desert", "Ocean"])
        self.terrain_combo.setStyleSheet("background-color: #382c20; color: #f0e0d0; padding: 3px;")
        top_layout.addWidget(self.terrain_combo)

        top_layout.addWidget(QLabel("Radius:"))
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 4)
        self.radius_spin.setValue(1)
        self.radius_spin.setStyleSheet("background-color: #382c20; color: #f0e0d0; padding: 3px;")
        top_layout.addWidget(self.radius_spin)

        top_layout.addStretch()
        layout.addWidget(top_bar)
        layout.addWidget(self.view)
        self.setCentralWidget(central)

        self.minimap = MiniMapWidget(self, self.view)
        self.selected_items = []
        self.is_dragging = False
        self.is_panning = False
        self.is_painting = False
        self.drag_start = QPointF()
        self.pan_start = QPointF()
        self.item_starts = {}

        self.load_state()
        self.view.viewport().installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.minimap.move(self.width() - self.minimap.width() - 20, self.height() - self.minimap.height() - 40)

    def set_hex_terrain(self, q: int, r: int, terrain: str):
        coord = (q, r)
        if terrain != "ocean":
            self.hex_grid_data[coord] = {"terrain": terrain}
        else:
            if coord in self.hex_grid_data:
                del self.hex_grid_data[coord]

    def paint_brush_at(self, scene_pos: QPointF):
        topo_config = SETTINGS.get("topography", {})
        hex_size = topo_config.get("hex_size", 55.0)
        center_q, center_r = pixel_to_hex(scene_pos.x(), scene_pos.y(), hex_size)
        for q, r in get_hexes_in_radius(center_q, center_r, self.radius_spin.value()):
            self.set_hex_terrain(q, r, self.terrain_combo.currentText().lower())
        self.save_state()
        self.scene.update()
        self.minimap.update()

    def eventFilter(self, obj, event):
        if obj == self.view.viewport():
            etype = event.type()
            if etype == QEvent.Type.MouseButtonPress:
                scene_pos = self.view.mapToScene(event.position().toPoint())
                clicked = self.scene.itemAt(scene_pos, self.view.transform())
                if event.button() == Qt.MouseButton.RightButton:
                    self.show_menu(event.position())
                    return True
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.brush_mode_checkbox.isChecked():
                        self.is_painting = True
                        self.paint_brush_at(scene_pos)
                        return True
                    if clicked and isinstance(clicked, SpatialItem):
                        if not clicked.isSelected():
                            self.scene.clearSelection()
                            clicked.setSelected(True)
                        self.selected_items = [clicked]
                        self.is_dragging = True
                        self.drag_start = scene_pos
                        self.item_starts = {clicked: clicked.pos()}
                        return True
                    else:
                        self.scene.clearSelection()
                        self.is_panning = True
                        self.pan_start = event.globalPosition()
                        self.view.setCursor(Qt.CursorShape.ClosedHandCursor)
                        return True
            elif etype == QEvent.Type.MouseMove:
                if self.is_painting:
                    self.paint_brush_at(self.view.mapToScene(event.position().toPoint()))
                    return True
                elif self.is_dragging:
                    delta = self.view.mapToScene(event.position().toPoint()) - self.drag_start
                    for item, start in self.item_starts.items():
                        item.setPos(start + delta)
                    self.scene.update()
                    return True
                elif self.is_panning:
                    delta = event.globalPosition() - self.pan_start
                    self.pan_start = event.globalPosition()
                    h, v = self.view.horizontalScrollBar(), self.view.verticalScrollBar()
                    h.setValue(int(h.value() - delta.x()))
                    v.setValue(int(v.value() - delta.y()))
                    return True
            elif etype == QEvent.Type.MouseButtonRelease:
                if self.is_painting:
                    self.is_painting = False
                    return True
                if self.is_dragging:
                    self.is_dragging = False
                    topo_config = SETTINGS.get("topography", {})
                    hex_size = topo_config.get("hex_size", 55.0)
                    for item in self.selected_items:
                        q, r = pixel_to_hex(item.pos().x(), item.pos().y(), hex_size)
                        item.q, item.r = q, r
                        item.setPos(hex_to_pixel(q, r, hex_size))
                    self.save_state()
                    self.scene.update()
                    return True
                if self.is_panning:
                    self.is_panning = False
                    self.view.setCursor(Qt.CursorShape.ArrowCursor)
                    return True
            elif etype == QEvent.Type.Wheel:
                factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
                if ZOOM_MIN < self.view.transform().m11() * factor < ZOOM_MAX:
                    self.view.scale(factor, factor)
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]:
                self.scene.removeItem(item)
            self.save_state()
            self.scene.update()
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
                topo_config = SETTINGS.get("topography", {})
                q, r = pixel_to_hex(scene_pos.x(), scene_pos.y(), topo_config.get("hex_size", 55.0))
                item = SpatialItem(path, action == f_act, q, r)
                self.scene.addItem(item)
                self.save_state()
                self.scene.update()

    def save_state(self):
        data = {
            "items": [{"path": i.path, "is_dir": i.is_dir, "q": i.q, "r": i.r} for i in self.scene.items() if
                      isinstance(i, SpatialItem)],
            "hex_grid": [{"q": q, "r": r, "terrain": t["terrain"]} for (q, r), t in self.hex_grid_data.items()]
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
                for h in data.get("hex_grid", []):
                    self.hex_grid_data[(h["q"], h["r"])] = {"terrain": h["terrain"]}
                for entry in data.get("items", []):
                    if os.path.exists(entry["path"]):
                        self.scene.addItem(SpatialItem(entry["path"], entry["is_dir"], entry["q"], entry["r"]))
        except Exception as e:
            print(f"Error loading state: {e}")


def run_modality():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())