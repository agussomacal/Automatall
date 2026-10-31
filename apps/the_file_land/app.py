import json
import math
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Set

import yaml

from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QEvent, QLineF
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QPixmap,
    QMouseEvent, QKeyEvent, QPainterPath, QPolygonF
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QMenu, QDialog, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog,
    QGraphicsDropShadowEffect, QFrame, QHBoxLayout, QWidget, QCheckBox, QRubberBand,
    QComboBox, QSpinBox
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
ZOOM_MIN = 0.01
ZOOM_MAX = 5.0


# --- Hex Grid Math & Engine ---
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
        points.append(QPointF(center.x() + size * math.cos(angle_rad),
                              center.y() + size * math.sin(angle_rad)))
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
        center_pt = hex_to_pixel(q, r, hex_size)
        self.setPos(center_pt)

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

        if self.isSelected():
            painter.setBrush(QBrush(QColor(255, 240, 200, 220)))
            painter.setPen(QPen(QColor(218, 165, 32), 3))
            painter.drawRoundedRect(self.boundingRect(), 8, 8)

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

        painter.setPen(QColor(240, 230, 210) if not self.isSelected() else QColor(40, 30, 20))
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


class HexTopographyMap(QGraphicsItem):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.setZValue(-10)

    def boundingRect(self) -> QRectF:
        return QRectF(-200000, -200000, 400000, 400000)

    def paint(self, painter: QPainter, option, widget):
        view = self.scene().views()[0] if self.scene() else None
        if not view:
            return

        topo_config = SETTINGS.get("topography", {})
        if not topo_config.get("enabled", True):
            bg_color = SETTINGS.get("appearance", {}).get("background_color", "#1b365d")
            painter.fillRect(view.mapToScene(view.viewport().rect()).boundingRect(), QBrush(QColor(bg_color)))
            return

        rect = view.mapToScene(view.viewport().rect()).boundingRect()

        ocean_color = QColor(topo_config.get("ocean_color", "#1b365d"))
        painter.fillRect(rect, QBrush(ocean_color))

        scale = view.transform().m11()
        if scale < 0.02:
            return

        hex_size = topo_config.get("hex_size", 55.0)
        land_color = QColor(topo_config.get("land_color", "#d8c29d"))
        coast_color = QColor(topo_config.get("coastline_color", "#6b533b"))
        wave_color = QColor(topo_config.get("wave_color", "#284b7d"))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if scale > 0.15:
            painter.setPen(QPen(wave_color, 1.5, Qt.PenStyle.SolidLine))
            step_w = hex_size * 3
            start_x = math.floor(rect.left() / step_w) * step_w
            end_x = math.ceil(rect.right() / step_w) * step_w
            start_y = math.floor(rect.top() / step_w) * step_w
            end_y = math.ceil(rect.bottom() / step_w) * step_w

            y = start_y
            while y <= end_y:
                x = start_x
                while x <= end_x:
                    painter.drawArc(QRectF(x, y, 20, 10), 0, 180 * 16)
                    x += step_w * 2
                y += step_w * 2

        for (q, r), tile_data in self.mw.hex_grid_data.items():
            center = hex_to_pixel(q, r, hex_size)
            if not rect.contains(center):
                if abs(center.x() - rect.center().x()) > rect.width() / 2 + hex_size * 2:
                    continue
                if abs(center.y() - rect.center().y()) > rect.height() / 2 + hex_size * 2:
                    continue

            poly = get_hex_polygon(center, hex_size)
            terrain = tile_data.get("terrain", "ocean")

            if terrain == "land":
                painter.setBrush(QBrush(land_color))
                painter.setPen(QPen(coast_color, 1.5))
                painter.drawPolygon(poly)
            else:
                grid_color = QColor(SETTINGS.get("appearance", {}).get("grid_color", "#2c4c7c"))
                grid_color.setAlphaF(SETTINGS.get("appearance", {}).get("grid_alpha", 0.3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(grid_color, 0.5))
                if scale > 0.3:
                    painter.drawPolygon(poly)


# --- Mini-Map Widget ---
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
            mx = (pt.x() + world_range / 2) / world_range * w
            my = (pt.y() + world_range / 2) / world_range * h
            return QPointF(mx, my)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(216, 194, 157)))
        for (q, r), tile in self.mw.hex_grid_data.items():
            if tile.get("terrain") == "land":
                topo_config = SETTINGS.get("topography", {})
                hex_size = topo_config.get("hex_size", 55.0)
                pt = hex_to_pixel(q, r, hex_size)
                mpt = world_to_mini(pt)
                painter.drawEllipse(mpt, 2.5, 2.5)

        painter.setBrush(QBrush(QColor(218, 165, 32)))
        for item in self.mw.scene.items():
            if isinstance(item, SpatialItem):
                mpt = world_to_mini(item.pos())
                painter.drawEllipse(mpt, 3, 3)

        view = self.mw.view
        viewport_scene_rect = view.mapToScene(view.viewport().rect()).boundingRect()
        top_left = world_to_mini(viewport_scene_rect.topLeft())
        bottom_right = world_to_mini(viewport_scene_rect.bottomRight())

        cam_rect = QRectF(top_left, bottom_right)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
        painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
        painter.drawRect(cam_rect)

    def mousePressEvent(self, event: QMouseEvent):
        self.pan_to_minimap_click(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        self.pan_to_minimap_click(event.position())

    def pan_to_minimap_click(self, pos: QPointF):
        world_range = 10000.0
        w, h = self.width(), self.height()
        wx = (pos.x() / w) * world_range - world_range / 2
        wy = (pos.y() / h) * world_range - world_range / 2
        self.mw.view.centerOn(wx, wy)
        self.update()


# --- Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map Explorer Settings")
        self.resize(460, 320)
        self.setStyleSheet("background-color: #241c14; color: #f0e0d0;")

        layout = QVBoxLayout()

        topo_config = SETTINGS.get("topography", {})
        self.topo_checkbox = QCheckBox("Enable Topographic Map & Water Waves")
        self.topo_checkbox.setChecked(topo_config.get("enabled", True))
        layout.addWidget(self.topo_checkbox)

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
        self.setWindowTitle("The File Land - Hex Map Explorer")
        self.resize(1200, 800)

        self.hex_grid_data: Dict[Tuple[int, int], dict] = {}
        self.regions: Dict[str, Set[Tuple[int, int]]] = {}

        self.scene = QGraphicsScene()
        bg_color = SETTINGS.get("appearance", {}).get("background_color", "#1b365d")
        self.scene.setBackgroundBrush(QColor(bg_color))

        self.topo_item = HexTopographyMap(self)
        self.scene.addItem(self.topo_item)

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

        # Top Bar & Terrain Brush Toolbar
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #241c14; border-bottom: 1px solid #3c2e20;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(15, 8, 15, 8)

        title_label = QLabel("🗺️ The File Land (Hex Edition)")
        title_label.setStyleSheet("color: #e0d0b0; font-weight: bold; font-size: 14pt;")
        top_layout.addWidget(title_label)

        top_layout.addSpacing(30)

        brush_label = QLabel("🖌️ Brush Tool:")
        brush_label.setStyleSheet("color: #f0e0d0;")
        top_layout.addWidget(brush_label)

        self.brush_mode_checkbox = QCheckBox("Paint Mode")
        self.brush_mode_checkbox.setStyleSheet("color: #f0e0d0; font-weight: bold;")
        top_layout.addWidget(self.brush_mode_checkbox)

        self.terrain_combo = QComboBox()
        self.terrain_combo.addItems(["Land", "Ocean"])
        self.terrain_combo.setStyleSheet("background-color: #382c20; color: #f0e0d0; padding: 3px;")
        top_layout.addWidget(self.terrain_combo)

        radius_label = QLabel("Radius:")
        radius_label.setStyleSheet("color: #f0e0d0;")
        top_layout.addWidget(radius_label)

        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 4)
        self.radius_spin.setValue(1)
        self.radius_spin.setStyleSheet("background-color: #382c20; color: #f0e0d0; padding: 3px;")
        top_layout.addWidget(self.radius_spin)

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

        self.minimap = MiniMapWidget(self, self.view)

        self.selected_items: List[SpatialItem] = []
        self.is_dragging_items = False
        self.is_panning_view = False
        self.is_selecting_box = False
        self.is_painting_tiles = False
        self.drag_mouse_start = QPointF()
        self.pan_mouse_start = QPointF()
        self.box_select_start = QPointF()
        self.item_start_positions = {}

        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.view.viewport())

        self.load_layout_state()
        self.view.viewport().installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.minimap.move(self.width() - self.minimap.width() - 20, self.height() - self.minimap.height() - 40)

    def set_hex_terrain(self, q: int, r: int, terrain: str, region_id: str = None):
        coord = (q, r)
        if terrain == "land":
            if not region_id:
                region_id = f"land_{q}_{r}"

            self.hex_grid_data[coord] = {"terrain": "land", "region_id": region_id}
            if region_id not in self.regions:
                self.regions[region_id] = set()
            self.regions[region_id].add(coord)

            directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
            for dq, dr in directions:
                n_coord = (q + dq, r + dr)
                if n_coord in self.hex_grid_data:
                    n_tile = self.hex_grid_data[n_coord]
                    if n_tile.get("terrain") == "land" and n_tile.get("region_id") != region_id:
                        target_reg = n_tile.get("region_id")
                        if target_reg in self.regions:
                            for cell in self.regions[target_reg]:
                                self.hex_grid_data[cell]["region_id"] = region_id
                                self.regions[region_id].add(cell)
                            del self.regions[target_reg]
        else:
            if coord in self.hex_grid_data:
                reg = self.hex_grid_data[coord].get("region_id")
                if reg and reg in self.regions:
                    self.regions[reg].discard(coord)
                del self.hex_grid_data[coord]

    def paint_brush_at(self, scene_pos: QPointF):
        topo_config = SETTINGS.get("topography", {})
        hex_size = topo_config.get("hex_size", 55.0)
        center_q, center_r = pixel_to_hex(scene_pos.x(), scene_pos.y(), hex_size)

        radius = self.radius_spin.value()
        terrain_type = self.terrain_combo.currentText().lower()

        target_hexes = get_hexes_in_radius(center_q, center_r, radius)
        for q, r in target_hexes:
            self.set_hex_terrain(q, r, terrain_type)

        self.save_layout_state()
        self.scene.update()
        self.minimap.update()

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if "defaults" not in SETTINGS:
                SETTINGS["defaults"] = {}
            if "topography" not in SETTINGS:
                SETTINGS["topography"] = {}

            SETTINGS["defaults"]["folder_icon"] = dialog.folder_path_edit.text()
            SETTINGS["defaults"]["file_icon"] = dialog.file_path_edit.text()
            SETTINGS["topography"]["enabled"] = dialog.topo_checkbox.isChecked()

            save_settings(SETTINGS)

            for item in self.scene.items():
                if isinstance(item, SpatialItem):
                    item._pixmap_cache = None
            self.scene.update()
            self.minimap.update()
            QMessageBox.information(self, "Settings", "Settings updated successfully.")

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

                    # IF PAINT MODE IS ENABLED: Paint tiles and block view panning/dragging
                    if self.brush_mode_checkbox.isChecked():
                        self.is_painting_tiles = True
                        self.paint_brush_at(scene_pos)
                        return True

                    # 1. Dragging selected items
                    if clicked_item and isinstance(clicked_item, SpatialItem) and (
                            clicked_item.isSelected() or modifiers == Qt.KeyboardModifier.ControlModifier):
                        if not clicked_item.isSelected():
                            if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                                self.scene.clearSelection()
                            clicked_item.setSelected(True)

                        self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]
                        self.is_dragging_items = True
                        self.drag_mouse_start = scene_pos
                        self.item_start_positions = {item: item.pos() for item in self.selected_items}
                        return True

                    # 2. Ctrl + Drag: Box Selection
                    elif modifiers == Qt.KeyboardModifier.ControlModifier:
                        self.is_selecting_box = True
                        self.box_select_start = mouse_event.position()
                        self.rubber_band.setGeometry(QRectF(self.box_select_start, self.box_select_start).toRect())
                        self.rubber_band.show()
                        return True

                    # 3. Standard Click (Single selection or Map Panning)
                    else:
                        if clicked_item and isinstance(clicked_item, SpatialItem):
                            if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                                self.scene.clearSelection()
                            clicked_item.setSelected(True)
                            self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]
                            return True
                        else:
                            if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                                self.scene.clearSelection()
                            self.selected_items = []
                            self.is_panning_view = True
                            self.pan_mouse_start = mouse_event.globalPosition()
                            self.view.setCursor(Qt.CursorShape.ClosedHandCursor)
                            return True

            elif etype == QEvent.Type.MouseMove:
                mouse_event = event
                if self.is_painting_tiles:
                    scene_pos = self.view.mapToScene(mouse_event.position().toPoint())
                    self.paint_brush_at(scene_pos)
                    return True
                elif self.is_dragging_items:
                    current_scene_pos = self.view.mapToScene(mouse_event.position().toPoint())
                    delta = current_scene_pos - self.drag_mouse_start
                    for item, start_pos in self.item_start_positions.items():
                        item.setPos(start_pos + delta)
                    self.scene.update()
                    self.minimap.update()
                    return True
                elif self.is_selecting_box:
                    current_pos = mouse_event.position()
                    self.rubber_band.setGeometry(QRectF(self.box_select_start, current_pos).toRect().normalized())
                    return True
                elif self.is_panning_view:
                    global_pos = mouse_event.globalPosition()
                    delta = global_pos - self.pan_mouse_start
                    self.pan_mouse_start = global_pos

                    h_bar = self.view.horizontalScrollBar()
                    v_bar = self.view.verticalScrollBar()
                    h_bar.setValue(int(h_bar.value() - delta.x()))
                    v_bar.setValue(int(v_bar.value() - delta.y()))
                    self.minimap.update()
                    return True

            elif etype == QEvent.Type.MouseButtonRelease:
                if self.is_painting_tiles:
                    self.is_painting_tiles = False
                    return True

                if self.is_dragging_items:
                    self.is_dragging_items = False

                    topo_config = SETTINGS.get("topography", {})
                    hex_size = topo_config.get("hex_size", 55.0)

                    occupied_hexes = {(it.q, it.r) for it in self.scene.items() if
                                      isinstance(it, SpatialItem) and it not in self.selected_items}

                    for item in self.selected_items:
                        target_q, target_r = pixel_to_hex(item.pos().x(), item.pos().y(), hex_size)

                        final_q, final_r = target_q, target_r
                        for sq, sr in get_spiral_hex_ring(target_q, target_r, radius=5):
                            if (sq, sr) not in occupied_hexes:
                                final_q, final_r = sq, sr
                                break

                        item.q, item.r = final_q, final_r
                        item.setPos(hex_to_pixel(final_q, final_r, hex_size))
                        occupied_hexes.add((final_q, final_r))

                    self.save_layout_state()
                    self.scene.update()
                    self.minimap.update()
                    return True

                if self.is_selecting_box:
                    self.is_selecting_box = False
                    self.rubber_band.hide()
                    rect = QRectF(self.view.mapToScene(self.rubber_band.geometry()))

                    items_in_rect = self.scene.items(rect)
                    for item in items_in_rect:
                        if isinstance(item, SpatialItem):
                            item.setSelected(True)
                    self.selected_items = [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]
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
                    self.minimap.update()
                return True

        return super().eventFilter(obj, event)

    def show_context_menu(self, pos: QPointF):
        scene_pos = self.view.mapToScene(pos.toPoint())
        topo_config = SETTINGS.get("topography", {})
        hex_size = topo_config.get("hex_size", 55.0)
        q, r = pixel_to_hex(scene_pos.x(), scene_pos.y(), hex_size)

        menu = QMenu(self)
        menu.setStyleSheet("background-color: #241c14; color: #f0e0d0; border: 1px solid #4a3828;")

        add_folder_action = menu.addAction("📁 Add Folder Link Here")
        add_file_action = menu.addAction("📄 Add File Link Here")
        toggle_hex_action = menu.addAction("🌊 Toggle Hex Terrain (Land/Ocean)")

        action = menu.exec(self.view.mapToGlobal(pos.toPoint()))

        if action == add_folder_action:
            self.add_item(q, r, is_dir=True)
        elif action == add_file_action:
            self.add_item(q, r, is_dir=False)
        elif action == toggle_hex_action:
            current = self.hex_grid_data.get((q, r), {}).get("terrain", "ocean")
            new_terrain = "land" if current == "ocean" else "ocean"
            self.set_hex_terrain(q, r, new_terrain)
            self.save_layout_state()
            self.scene.update()
            self.minimap.update()

    def add_item(self, q: int, r: int, is_dir: bool):
        topo_config = SETTINGS.get("topography", {})
        hex_size = topo_config.get("hex_size", 55.0)
        occupied_hexes = {(it.q, it.r) for it in self.scene.items() if isinstance(it, SpatialItem)}

        final_q, final_r = q, r
        for sq, sr in get_spiral_hex_ring(q, r, radius=5):
            if (sq, sr) not in occupied_hexes:
                final_q, final_r = sq, sr
                break

        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Select Folder to Map")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File to Map")

        if not path:
            return

        self.set_hex_terrain(final_q, final_r, "land")
        directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
        for dq, dr in directions:
            self.set_hex_terrain(final_q + dq, final_r + dr, "land")

        item = SpatialItem(path, is_dir, final_q, final_r)
        self.scene.addItem(item)
        self.scene.clearSelection()
        item.setSelected(True)
        self.selected_items = [item]
        self.save_layout_state()
        self.scene.update()
        self.minimap.update()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            selected = [i for i in self.scene.selectedItems() if isinstance(i, SpatialItem)]
            for item in selected:
                self.scene.removeItem(item)
            self.selected_items.clear()
            self.save_layout_state()
            self.scene.update()
            self.minimap.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def save_layout_state(self):
        data = {
            "items": [],
            "hex_grid": []
        }
        for item in self.scene.items():
            if isinstance(item, SpatialItem):
                data["items"].append({
                    "path": item.path,
                    "is_dir": item.is_dir,
                    "q": item.q,
                    "r": item.r
                })
        for (q, r), tile in self.hex_grid_data.items():
            if tile.get("terrain") == "land":
                data["hex_grid"].append({
                    "q": q,
                    "r": r,
                    "region_id": tile.get("region_id")
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

                for hex_entry in data.get("hex_grid", []):
                    q = hex_entry.get("q")
                    r = hex_entry.get("r")
                    reg = hex_entry.get("region_id")
                    if q is not None and r is not None:
                        self.set_hex_terrain(q, r, "land", reg)

                for entry in data.get("items", []):
                    path = entry.get("path")
                    q = entry.get("q", 0)
                    r = entry.get("r", 0)
                    if path and os.path.exists(path):
                        item = SpatialItem(path, entry.get("is_dir", False), q, r)
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