#!/usr/bin/env python3
"""Hello World Application"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class HelloWorldApp(Gtk.Window):
    """Simple hello world application"""

    def __init__(self):
        super().__init__(title="Hello World")
        self.set_default_size(300, 150)
        self.set_border_width(20)

        # Center window
        self.connect("configure-event", self.center_window)

        # Create UI
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(15)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)

        # Welcome label
        welcome_label = Gtk.Label()
        welcome_label.set_markup('<span size="xx-large" weight="bold">Hello, World!</span>')
        welcome_label.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(welcome_label, False, False, 20)

        # Message label
        message_label = Gtk.Label()
        message_label.set_text("This is your first custom app!")
        message_label.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(message_label, False, False, 0)

        # Button
        greet_btn = Gtk.Button(label="Click Me!")
        greet_btn.connect("clicked", self.on_greet)
        greet_btn.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(greet_btn, False, False, 10)

        self.add(vbox)

    def center_window(self, widget, event):
        """Window centering - simplified for cross-platform"""
        # Do nothing - GTK places windows nicely by default
        return False

    def on_greet(self, button):
        # Create a popup dialog
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Greetings!"
        )
        dialog.format_secondary_text("Welcome to SuperMicro App Manager!")
        dialog.run()
        dialog.destroy()


def launch():
    """Entry point called by main.py"""
    app = HelloWorldApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()