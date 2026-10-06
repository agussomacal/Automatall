# apps/calculator/app.py
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib


class CalculatorApp(Gtk.Window):
    """Simple calculator app"""

    def __init__(self):
        super().__init__(title="Calculator")
        self.set_default_size(250, 320)
        self.set_resizable(False)

        self.display_value = "0"
        self.pending_operation = None
        self.first_operand = None

        # Main layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(10)
        main_vbox.set_border_width(10)

        # Display
        self.display = Gtk.Entry()
        self.display.set_hexpand(True)
        self.display.set_max_width_chars(15)
        self.display.set_alignment(1.0)  # Right-aligned
        self.display.set_text("0")
        self.display.set_editable(False)
        main_vbox.pack_start(self.display, False, False, 0)

        # Buttons grid
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.set_row_spacing(5)

        buttons = [
            ('C', 0, 0), ('±', 1, 0), ('%', 2, 0), ('÷', 3, 0),
            ('7', 0, 1), ('8', 1, 1), ('9', 2, 1), ('×', 3, 1),
            ('4', 0, 2), ('5', 1, 2), ('6', 2, 2), ('-', 3, 2),
            ('1', 0, 3), ('2', 1, 3), ('3', 2, 3), ('+', 3, 3),
            ('0', 0, 4, 2), ('.', 2, 4), ('=', 3, 4),
        ]

        for btn_config in buttons:
            label = btn_config[0]
            col = btn_config[1]
            row = btn_config[2]
            colspan = btn_config[3] if len(btn_config) > 3 else 1

            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.on_button_click, label)
            btn.set_size_request(50, 50)

            # Style operators differently
            if label in ['÷', '×', '-', '+', '=']:
                btn.get_style_context().add_class('operator-btn')

            grid.attach(btn, col, row, colspan, 1)

        main_vbox.pack_start(grid, True, True, 0)
        self.add(main_vbox)

    def on_button_click(self, button, label):
        current = self.display.get_text()

        if label == 'C':
            self.display_value = "0"
            self.pending_operation = None
            self.first_operand = None
            self.display.set_text("0")

        elif label == '=':
            if self.pending_operation and self.first_operand is not None:
                second = float(self.display_value)
                result = self.calculate(self.first_operand, second, self.pending_operation)
                self.display_value = str(result)
                self.display.set_text(str(result))
                self.pending_operation = None
                self.first_operand = None

        elif label in ['÷', '×', '-', '+']:
            self.first_operand = float(self.display_value)
            self.pending_operation = label
            self.display_value = "0"

        elif label == '±':
            if self.display_value.startswith('-'):
                self.display_value = self.display_value[1:]
            else:
                self.display_value = '-' + self.display_value
            self.display.set_text(self.display_value)

        elif label == '%':
            self.display_value = str(float(self.display_value) / 100)
            self.display.set_text(self.display_value)

        elif label == '.':
            if '.' not in self.display_value:
                self.display_value += '.'
                self.display.set_text(self.display_value)

        else:
            # Number
            if self.display_value == "0" and label != '.':
                self.display_value = label
            else:
                self.display_value += label
            self.display.set_text(self.display_value)

    def calculate(self, a, b, op):
        if op == '+': return a + b
        if op == '-': return a - b
        if op == '×': return a * b
        if op == '÷': return a / b if b != 0 else 0
        return b


def launch():
    """Entry point"""
    app = CalculatorApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()
