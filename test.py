
from vibeplot import EarthOrbitApp
from panda3d.core import AntialiasAttrib

# print('importing qt')
# # these imports are crashing! ... something is wrong here...
# # note getting installed right by pixi? in halo, it works with conda ?
# from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
# from PySide6.QtCore import Qt
# print('done importing qt')


###############################################

app = EarthOrbitApp()

# example reading trajectory from JSON file;
# app.orbit_from_json_np = app.add_orbit_from_json("traj.json", color=(1, 0, 1, 1), thickness=2.0)

# https://docs.panda3d.org/1.10/python/programming/render-attributes/antialiasing
app.render.setAntialias(AntialiasAttrib.MAuto)  # antialiasing


app.run()

# ---- attempt to use pyside6 ... isn't working yet ----
# class PandaWidget(QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setAttribute(Qt.WA_PaintOnScreen, True)
#         self.setAttribute(Qt.WA_NativeWindow, True)
#         self.setMinimumSize(800, 600)
#         self.panda_app = None
#         self.timer = QTimer(self)
#         self.timer.timeout.connect(self.step_panda)

#     def showEvent(self, event):
#         if self.panda_app is None:
#             window_handle = int(self.winId())
#             self.panda_app = EarthOrbitApp(parent_window=window_handle)
#             self.timer.start(16)  # ~60 FPS

#     def step_panda(self):
#         if self.panda_app is not None:
#             self.panda_app.taskMgr.step()

# if __name__ == "__main__":
#     print('start')
#     app = QApplication(sys.argv)
#     main_window = QMainWindow()
#     panda_widget = PandaWidget()
#     main_window.setCentralWidget(panda_widget)
#     main_window.resize(800, 600)
#     main_window.show()
#     sys.exit(app.exec())