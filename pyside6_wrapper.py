import sys
import platform

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QTimer

from vibeplot import EarthOrbitApp


class Panda3DWidget(QWidget):
    """A QWidget that embeds a Panda3D window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panda_app = None
        self.init_panda3d()

    def init_panda3d(self):
        """Initialize the Panda3D application embedded in this widget."""
        # Get the native window handle (platform-specific)
        if platform.system() == "Windows":
            win_handle = int(self.winId())
        elif platform.system() == "Darwin":  # macOS
            win_handle = int(self.winId())
        else:  # Linux
            win_handle = int(self.winId())

        # Create the Panda3D app with the parent window handle
        self.panda_app = EarthOrbitApp(parent_window=win_handle)

    def closeEvent(self, event):
        """Clean up when the widget is closed."""
        if self.panda_app:
            self.panda_app.destroy()
        event.accept()


class MainWindow(QMainWindow):
    """Main PySide6 window that contains the embedded Panda3D widget."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibePlot - PySide6 + Panda3D")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add some PySide6 controls
        controls_layout = QHBoxLayout()

        self.info_label = QLabel("VibePlot - 3D Orbital Visualization")
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        controls_layout.addWidget(self.info_label)

        self.reset_button = QPushButton("Reset View")
        self.reset_button.clicked.connect(self.reset_view)
        controls_layout.addWidget(self.reset_button)

        self.pause_button = QPushButton("Pause/Resume")
        self.pause_button.clicked.connect(self.toggle_pause)
        controls_layout.addWidget(self.pause_button)

        layout.addLayout(controls_layout)

        # Create and add the Panda3D widget
        self.panda_widget = Panda3DWidget()
        layout.addWidget(self.panda_widget)

        # Set up a timer to keep Panda3D running
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_panda3d)
        self.timer.start(16)  # ~60 FPS

    def update_panda3d(self):
        """Update the Panda3D application."""
        if self.panda_widget.panda_app:
            # Let Panda3D process its tasks
            try:
                self.panda_widget.panda_app.taskMgr.step()
            except (AttributeError, RuntimeError):
                # In case the app is destroyed or taskMgr is not available
                pass

    def reset_view(self):
        """Reset the camera view in Panda3D."""
        if self.panda_widget.panda_app:
            self.panda_widget.panda_app.recenter_on_earth()

    def toggle_pause(self):
        """Toggle pause in the Panda3D animation."""
        if self.panda_widget.panda_app:
            self.panda_widget.panda_app.toggle_scene_animation()

    def closeEvent(self, event):
        """Clean up when the main window is closed."""
        self.timer.stop()
        if self.panda_widget:
            self.panda_widget.closeEvent(event)
        event.accept()


def main():

    # Create the PySide6 application
    app = QApplication(sys.argv)

    # Create and show the main window
    window = MainWindow()
    window.show()

    # Run the PySide6 event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
