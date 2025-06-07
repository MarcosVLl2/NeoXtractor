from PySide6 import QtCore, QtGui

from .camera import Camera, OrthogonalDirection

ORTHOGONAL_KEY_MAP = {
    QtCore.Qt.Key.Key_1: OrthogonalDirection.FRONT,
    QtCore.Qt.Key.Key_3: OrthogonalDirection.RIGHT,
    QtCore.Qt.Key.Key_7: OrthogonalDirection.TOP
}

class CameraController:
    def __init__(self):
        self.camera = Camera()

        self.zoom_speed = 2.5

        self._last_mouse_pos = QtCore.QPointF(0, 0)

        self._mouse_pressed_buttons = {
            QtCore.Qt.MouseButton.LeftButton: False,
            QtCore.Qt.MouseButton.RightButton: False,
            QtCore.Qt.MouseButton.MiddleButton: False
        }

        self._keyboard_pressed_keys = {}

    def _camera_mouse_pressed_event(self, event: QtGui.QMouseEvent):
        self._last_mouse_pos = event.position()
        self._mouse_pressed_buttons[event.button()] = True

    def _camera_mouse_released_event(self, event: QtGui.QMouseEvent):
        self._mouse_pressed_buttons[event.button()] = False
        if not any(self._mouse_pressed_buttons.values()):
            self._last_mouse_pos = QtCore.QPointF(0, 0)

    def _camera_mouse_moved_event(self, event: QtGui.QMouseEvent):
        if not any(self._mouse_pressed_buttons.values()):
            return

        current_pos = event.position()
        delta = current_pos - self._last_mouse_pos
        self._last_mouse_pos = current_pos

        if self._mouse_pressed_buttons[QtCore.Qt.MouseButton.LeftButton]:
            self.camera.orbit(delta.x(), delta.y())
        elif self._mouse_pressed_buttons[QtCore.Qt.MouseButton.RightButton]:
            self.camera.pan(delta.x(), delta.y())

    def _camera_wheel_event(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y() / 100.0
        self.camera.dolly(-delta * self.zoom_speed)

    def _camera_key_pressed_event(self, event: QtGui.QKeyEvent):
        self._keyboard_pressed_keys[event.key()] = True

        if event.key() in ORTHOGONAL_KEY_MAP:
            self.camera.orthogonal(ORTHOGONAL_KEY_MAP[QtCore.Qt.Key(event.key())],
                                   self._keyboard_pressed_keys.get(QtCore.Qt.Key.Key_Control, False))

    def _camera_key_released_event(self, event: QtGui.QKeyEvent):
        if event.key() in self._keyboard_pressed_keys:
            del self._keyboard_pressed_keys[event.key()]

    def _camera_update(self):
        if not self._keyboard_pressed_keys:
            return

        forward = 0
        right = 0
        sprinting = self._keyboard_pressed_keys.get(QtCore.Qt.Key.Key_Shift, False)

        if self._keyboard_pressed_keys.get(QtCore.Qt.Key.Key_W, False):
            forward += 1
        if self._keyboard_pressed_keys.get(QtCore.Qt.Key.Key_S, False):
            forward -= 1
        if self._keyboard_pressed_keys.get(QtCore.Qt.Key.Key_A, False):
            right -= 1
        if self._keyboard_pressed_keys.get(QtCore.Qt.Key.Key_D, False):
            right += 1

        speed = 0.1 if not sprinting else 0.2

        self.camera.move(QtGui.QVector4D(right * speed, 0, -forward * speed, 0))
