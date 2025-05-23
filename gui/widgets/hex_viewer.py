"""Provides Hex viewing related widgets"""

import struct
#import uuid
from PySide6 import QtWidgets, QtCore, QtGui

def decode_uleb128(data, pos):
    """Decode an unsigned LEB128 value from the data at the given position."""
    result = 0
    shift = 0
    offset = 0

    while True:
        if pos + offset >= len(data):
            return None

        byte = data[pos + offset]
        result |= ((byte & 0x7f) << shift)
        offset += 1

        if not byte & 0x80:
            break

        shift += 7

    return result

def decode_sleb128(data, pos):
    """Decode a signed LEB128 value from the data at the given position."""
    result = 0
    shift = 0
    offset = 0

    while True:
        if pos + offset >= len(data):
            return None

        byte = data[pos + offset]
        result |= ((byte & 0x7f) << shift)
        offset += 1

        if not (byte & 0x80):
            if byte & 0x40:  # Sign bit is set
                result |= -(1 << (shift + 7))
            break

        shift += 7

    return result

class HexArea(QtWidgets.QWidget):
    """
    A widget that displays a hex view of the given data.
    """

    cursorPositionChanged = QtCore.Signal(int)  # Offset in bytes
    selectionChanged = QtCore.Signal(int, int)  # Start and end offsets

    # Data
    _data = bytearray()
    _addressing_base = 16
    _bytes_per_line = 16
    _bytes_per_group = 4
    _show_ascii = True

    # State
    _cursor_pos = 0
    _selection_start = -1
    _selection_end = -1
    _visible_lines = 0
    _total_width = 0
    _total_lines = 0

    # Colors
    _address_color = QtGui.QColor(80, 80, 80)
    _hex_color = QtGui.QColor(0, 0, 0)
    _ascii_color = QtGui.QColor(0, 0, 180)
    _highlight_bg_color = QtGui.QColor(220, 240, 255)
    _highlight_fg_color = QtGui.QColor(0, 0, 0)
    _selection_bg_color = QtGui.QColor(180, 220, 255)
    _selection_fg_color = QtGui.QColor(0, 0, 0)
    _alternate_row_color = QtGui.QColor(245, 245, 245)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self.setFocusPolicy(QtGui.Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self._main_layout = QtWidgets.QGridLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._hex_widget = QtWidgets.QWidget(self)

        self._main_layout.addWidget(self._hex_widget, 0, 0)

        self._v_scrollbar = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical, self)
        self._h_scrollbar = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal, self)
        self._v_scrollbar.setVisible(False)
        self._v_scrollbar.valueChanged.connect(self.update)
        self._h_scrollbar.setVisible(False)
        self._h_scrollbar.valueChanged.connect(self.update)
        self._main_layout.addWidget(self._v_scrollbar, 0, 1)
        self._main_layout.addWidget(self._h_scrollbar, 1, 0)

        self._corner_widget = QtWidgets.QWidget()
        self._corner_widget.setFixedSize(self._v_scrollbar.width(), self._h_scrollbar.height())
        self._corner_widget.setAutoFillBackground(True)
        self._main_layout.addWidget(self._corner_widget, 1, 1)

        self._measure_font_metrics()
        self._update_scrollbar()

    @property
    def data(self) -> bytearray:
        """Get the data being displayed."""
        return self._data

    @data.setter
    def data(self, value: bytearray):
        """Set the data to be displayed."""
        self._data = value
        self._cursor_pos = 0
        self._selection_start = -1
        self._selection_end = -1
        self._update_scrollbar()
        self.update()

    @property
    def addressing_base(self) -> int:
        """Get the addressing base."""
        return self._addressing_base

    @addressing_base.setter
    def addressing_base(self, value: int):
        """Set the addressing base."""
        if value not in (16, 10, 8):
            raise ValueError("Addressing base must be 16 (hex), 10 (decimal), or 8 (octal).")
        self._addressing_base = value
        self.update()

    @property
    def bytes_per_line(self) -> int:
        """Get the number of bytes per line."""
        return self._bytes_per_line

    @bytes_per_line.setter
    def bytes_per_line(self, value: int):
        """Set the number of bytes per line."""
        if value not in (8, 16, 32, 64):
            raise ValueError("Bytes per line must be 8, 16, 32, or 64.")
        self._bytes_per_line = value
        self._update_scrollbar()
        self.update()

    @property
    def bytes_per_group(self) -> int:
        """Get the number of bytes per group."""
        return self._bytes_per_group

    @bytes_per_group.setter
    def bytes_per_group(self, value: int):
        """Set the number of bytes per group."""
        self._bytes_per_group = value

    @property
    def show_ascii(self) -> bool:
        """Get whether to show ASCII representation."""
        return self._show_ascii

    @show_ascii.setter
    def show_ascii(self, value: bool):
        """Set whether to show ASCII representation."""
        self._show_ascii = value
        self._update_scrollbar()
        self.update()

    @property
    def cursor_byte_pos(self):
        """Get the cursor position in bytes."""
        return self._cursor_pos

    @property
    def cursor_pos(self):
        """Get the cursor position in the hex viewer."""
        column = self._cursor_pos // self._bytes_per_line
        row = self._cursor_pos - column * self._bytes_per_line
        return (row + 1, column + 1)

    def _update_scrollbar(self):
        """Update the vertical and horizontal scrollbars based on data size and viewport."""
        if len(self._data) == 0:
            self._v_scrollbar.setVisible(False)
            self._h_scrollbar.setVisible(False)
            self._corner_widget.setVisible(False)
            return

        # Calculate the width needed for full display
        address_width = self._calculate_address_width()
        hex_width = (self._char_width * 4) * self._bytes_per_line  # Width for hex columns
        if self._bytes_per_group > 1:
            hex_width += (self._bytes_per_line // self._bytes_per_group - 1) * self._char_width

        ascii_width = 0
        if self._show_ascii:
            ascii_width = int(self._char_width * 1.5) * self._bytes_per_line

        # Total content width with padding
        self._total_width = total_width = address_width + hex_width + ascii_width + self._char_width * 2 + 40

        # Calculate available width accounting for the vertical scrollbar
        available_width = self._hex_widget.width()

        # Horizontal scrollbar visibility and range
        if total_width <= available_width:
            self._h_scrollbar.setVisible(False)
            self._h_scrollbar.setValue(0)
        else:
            self._h_scrollbar.setRange(0, total_width - available_width)
            self._h_scrollbar.setPageStep(available_width)
            self._h_scrollbar.setSingleStep(self._char_width * 4)  # Scroll by 4 character widths
            self._h_scrollbar.setVisible(True)

            # Ensure current position is valid
            if self._h_scrollbar.value() > total_width - available_width:
                self._h_scrollbar.setValue(total_width - available_width)

        # Calculate how many lines can be displayed
        self._visible_lines = max(1, self._hex_widget.height() // self._char_height)

        # Calculate total lines needed to display all data
        self._total_lines = total_lines = (len(self._data) + self._bytes_per_line - 1) // self._bytes_per_line + 2

        # Vertical scrollbar visibility and range
        if total_lines <= self._visible_lines:
            # All data fits in view, no need for scrollbar
            self._v_scrollbar.setVisible(False)
            self._v_scrollbar.setValue(0)
        else:
            # Configure scrollbar for the data
            self._v_scrollbar.setRange(0, total_lines - self._visible_lines)
            self._v_scrollbar.setPageStep(self._visible_lines)
            self._v_scrollbar.setSingleStep(1)
            self._v_scrollbar.setVisible(True)

            # Ensure current position is valid
            if self._v_scrollbar.value() > total_lines - self._visible_lines:
                self._v_scrollbar.setValue(total_lines - self._visible_lines)

        if self._v_scrollbar.isVisible() and self._h_scrollbar.isVisible():
            self._corner_widget.setFixedSize(self._v_scrollbar.width(), self._h_scrollbar.height())
            self._corner_widget.setVisible(True)

    def _measure_font_metrics(self):
        """Measure font metrics for the current font."""
        self._font_metrics = QtGui.QFontMetrics(self.font())
        self._char_width = self._font_metrics.horizontalAdvance("0")
        self._char_height = self._font_metrics.height()

    def _calculate_address_width(self) -> int:
        """Calculate the width needed for address display."""
        if len(self._data) == 0:
            return 8 * self._char_width  # Minimum width

        # Calculate required width based on addressing mode and data size
        max_address = len(self._data) - 1
        min_width = len("Address") - 2

        if self._addressing_base == 16:  # Hex
            addr_chars = max(min_width, len(f"{max_address:X}"))
            return (addr_chars + 2) * self._char_width  # +2 for "0x"
        elif self._addressing_base == 8:  # Octal
            addr_chars = max(min_width, len(f"{max_address:o}"))
            return (addr_chars + 2) * self._char_width  # +2 for "0o"
        else:  # Decimal
            addr_chars = max(min_width + 2, len(str(max_address)))
            return addr_chars * self._char_width

    def _draw_header(self, painter: QtGui.QPainter, rect: QtCore.QRect, addr_width: int,
                    hex_width: int, ascii_width: int):
        """Draw the header with column addresses."""
        header_rect = QtCore.QRect(rect.left(),
                                   rect.top(),
                                   max(self._total_width, rect.width()),
                                   self._char_height + 8# Increased height
                                   )

        # Draw header background
        header_bg = QtGui.QLinearGradient(header_rect.topLeft(), header_rect.bottomLeft())
        header_bg.setColorAt(0, QtGui.QColor(240, 240, 240))
        header_bg.setColorAt(1, QtGui.QColor(220, 220, 220))
        painter.fillRect(header_rect, header_bg)

        # Draw header separator line
        painter.setPen(QtGui.QColor(180, 180, 180))
        painter.drawLine(header_rect.left(), header_rect.bottom(),
                        header_rect.right(), header_rect.bottom())

        # Draw address column header
        painter.setPen(QtGui.QColor(80, 80, 80))
        addr_rect = QtCore.QRect(rect.left(), rect.top(), addr_width, self._char_height + 8)  # Increased height
        painter.drawText(addr_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "Address")

        # Draw column separators
        painter.setPen(QtGui.QColor(180, 180, 180))
        painter.drawLine(addr_rect.right(), header_rect.top(),
                        addr_rect.right(), header_rect.bottom())

        # Draw hex column headers (00-0F)
        hex_start_x = addr_rect.right() + 10

        painter.setPen(QtGui.QColor(80, 80, 80))
        col_width = self._char_width * 4  # Increased width for hex columns
        x_offset = 0

        for i in range(self._bytes_per_line):
            # Add extra space for group separator
            if i > 0 and i % self._bytes_per_group == 0:
                x_offset += self._char_width

            column_text = f"{i:02X}"
            col_rect = QtCore.QRect(hex_start_x + i * col_width + x_offset, rect.top(),
                            col_width, self._char_height + 8)

            painter.drawText(col_rect, QtCore.Qt.AlignmentFlag.AlignCenter, column_text)

        # Draw hex/ASCII separator
        if self._show_ascii:
            painter.setPen(QtGui.QColor(180, 180, 180))
            ascii_start_x = hex_start_x + hex_width + x_offset + 5
            painter.drawLine(ascii_start_x - 5, header_rect.top(),
                            ascii_start_x - 5, header_rect.bottom())

            # Draw ASCII header
            ascii_header_rect = QtCore.QRect(ascii_start_x, rect.top(),
                                    ascii_width, self._char_height + 8)
            painter.setPen(QtGui.QColor(80, 80, 80))
            painter.drawText(ascii_header_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "ASCII")

    def _draw_hex_content(self, painter: QtGui.QPainter, rect: QtCore.QRect, addr_width: int,
                         hex_width: int, ascii_width: int):
        """Draw the hex content and ASCII representation."""
        if len(self._data) == 0:
            return

        # Calculate positions
        addr_x = rect.left()
        hex_x = addr_x + addr_width + 10

        row_height = self._char_height
        bytes_per_row = self._bytes_per_line

        # Calculate visible range
        first_row = self._v_scrollbar.value()
        visible_rows = min(self._visible_lines,
                          (len(self._data) + bytes_per_row - 1) // bytes_per_row - first_row)

        # For each visible row
        for row in range(visible_rows):
            y = rect.top() + row * row_height
            row_addr = (first_row + row) * bytes_per_row

            # Draw alternating row backgrounds
            if (first_row + row) % 2 == 1:
                painter.fillRect(QtCore.QRect(rect.left(), y, rect.width(), row_height),
                                self._alternate_row_color)

            # Draw address
            painter.setPen(self._address_color)
            addr_rect = QtCore.QRect(addr_x, y, addr_width, row_height)

            # Use minimum width of "Address" (7 chars)
            min_width = max(5, len("Address") - 2)  # -2 for the "0x" or "0o" prefix

            if self._addressing_base == 16:  # Hex
                addr_text = f"0x{row_addr:0{min_width}X}"
            elif self._addressing_base == 8:  # Octal
                addr_text = f"0o{row_addr:0{min_width}o}"
            else:  # Decimal
                addr_text = f"{row_addr:0{min_width+2}d}"  # +2 to account for missing prefix

            painter.drawText(addr_rect, QtCore.Qt.AlignmentFlag.AlignCenter, addr_text)

            # Draw bytes for this row
            max_bytes = min(bytes_per_row, len(self._data) - row_addr)
            col_width = self._char_width * 4
            x_offset = 0

            for col in range(max_bytes):
                byte_addr = row_addr + col
                byte_val = self._data[byte_addr]

                # Calculate position for this byte
                byte_x = hex_x + col * col_width

                # Add extra space for group separator
                if col > 0 and col % self._bytes_per_group == 0:
                    x_offset += self._char_width

                byte_rect = QtCore.QRect(
                    int(byte_x + self._char_width / 2 + x_offset),
                    y,
                    col_width - self._char_width,
                    row_height
                    )

                # Check if this byte is selected or cursor is here
                is_selected = (self._selection_start >= 0 and
                              byte_addr >= min(self._selection_start, self._selection_end) and
                              byte_addr <= max(self._selection_start, self._selection_end))
                is_cursor = byte_addr == self._cursor_pos

                # Draw background if selected or cursor is here
                if is_selected:
                    painter.fillRect(byte_rect, self._selection_bg_color)
                    painter.setPen(self._selection_fg_color)
                elif is_cursor:
                    painter.fillRect(byte_rect, self._highlight_bg_color)
                    painter.setPen(self._highlight_fg_color)
                else:
                    painter.setPen(self._hex_color)

                byte_text = f"{byte_val:02X}"
                painter.drawText(byte_rect, QtCore.Qt.AlignmentFlag.AlignCenter, byte_text)

            ascii_x = hex_x + hex_width + x_offset + 15

            # Draw ASCII representation
            if self._show_ascii:
                for col in range(max_bytes):
                    byte_addr = row_addr + col
                    byte_val = self._data[byte_addr]

                    # Calculate position for this ASCII char
                    char_x = ascii_x + col * int(self._char_width * 1.5)
                    char_rect = QtCore.QRect(char_x, y, int(self._char_width * 1.5), row_height)

                    # Check if this byte is selected or cursor is here
                    is_selected = (self._selection_start >= 0 and
                                  byte_addr >= min(self._selection_start, self._selection_end) and
                                  byte_addr <= max(self._selection_start, self._selection_end))
                    is_cursor = byte_addr == self._cursor_pos

                    # Draw background if selected or cursor is here
                    if is_selected:
                        painter.fillRect(char_rect, self._selection_bg_color)
                        painter.setPen(self._selection_fg_color)
                    elif is_cursor:
                        painter.fillRect(char_rect, self._highlight_bg_color)
                        painter.setPen(self._highlight_fg_color)
                    else:
                        painter.setPen(self._ascii_color)

                    # Get printable character or dot for control chars
                    if 32 <= byte_val <= 126:  # Printable ASCII
                        char = chr(byte_val)
                    else:
                        char = '.'

                    painter.drawText(char_rect, QtCore.Qt.AlignmentFlag.AlignCenter, char)

    def _ensure_cursor_visible(self):
        """Ensure the cursor is visible by scrolling if necessary."""
        if len(self._data) == 0:
            return

        cursor_line = self._cursor_pos // self._bytes_per_line

        if cursor_line < self._v_scrollbar.value():
            # Cursor is above visible area, scroll up
            self._v_scrollbar.setValue(cursor_line)
        elif cursor_line >= self._v_scrollbar.value() + self._visible_lines:
            # Cursor is below visible area, scroll down
            # TODO: Fix the bottom issue
            self._v_scrollbar.setValue(cursor_line - self._visible_lines + 1)

    def setFont(self, font: QtGui.QFont | str):
        super().setFont(font)
        self._measure_font_metrics()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        """Handle resize events to update the scrollbar and layout."""
        self._update_scrollbar()
        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Handle mouse press events."""
        if len(self._data) == 0 or event.button() != QtCore.Qt.MouseButton.LeftButton:
            return

        # Calculate which byte was clicked, if any
        byte_addr = self._byte_at_position(event.position().toPoint())
        if byte_addr >= 0 and byte_addr < len(self._data):
            self._cursor_pos = byte_addr

            if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                # Extend selection
                if self._selection_start < 0:
                    self._selection_start = byte_addr
                self._selection_end = byte_addr
            else:
                # Start new selection
                self._selection_start = byte_addr
                self._selection_end = byte_addr

            self.update()
            self.cursorPositionChanged.emit(byte_addr)
            self.selectionChanged.emit(
                min(self._selection_start, self._selection_end),
                max(self._selection_start, self._selection_end)
            )

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Handle mouse move events."""
        if len(self._data) == 0 or not event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            return

        # Extend selection if button is pressed
        byte_addr = self._byte_at_position(event.position().toPoint())
        if byte_addr >= 0 and byte_addr < len(self._data):
            self._cursor_pos = byte_addr
            self._selection_end = byte_addr

            self.update()
            self.selectionChanged.emit(
                min(self._selection_start, self._selection_end),
                max(self._selection_start, self._selection_end)
            )

    def _byte_at_position(self, pos: QtCore.QPoint) -> int:
        """Get the byte address at the given position."""
        # Adjust position for horizontal scrolling
        pos.setX(pos.x() + self._h_scrollbar.value())

        # Ignore clicks outside the content area - fully account for scrollbars
        rect = self._hex_widget.geometry()

        if not rect.contains(pos):
            return -1

        # Skip header
        rect.setTop(rect.top() + self._char_height + 8)  # Increased header height

        if pos.y() < rect.top():
            return -1

        # Calculate layout
        address_width = self._calculate_address_width()
        hex_width = (self._char_width * 4) * self._bytes_per_line  # Increased width for hex columns
        if self._bytes_per_group > 1:
            hex_width += (self._bytes_per_line // self._bytes_per_group - 1) * self._char_width

        # Check if click is in hex area or ASCII area
        hex_start_x = rect.left() + address_width + 10  # Increased spacing
        hex_end_x = hex_start_x + hex_width

        in_hex_area = pos.x() >= hex_start_x and pos.x() < hex_end_x

        in_ascii_area = False
        ascii_start_x = 0
        if self._show_ascii:
            ascii_start_x = hex_end_x + (self._bytes_per_line // self._bytes_per_group - 1) * self._char_width + 15
            ascii_end_x = ascii_start_x + int(self._char_width * 1.5) * self._bytes_per_line
            in_ascii_area = pos.x() >= ascii_start_x and pos.x() < ascii_end_x

        if not (in_hex_area or in_ascii_area):
            return -1

        # Calculate row and column
        row = (pos.y() - rect.top()) // self._char_height
        row += self._v_scrollbar.value()

        col = -1

        if in_hex_area:
            # Calculate column in hex area
            rel_x = pos.x() - hex_start_x
            col_width = self._char_width * 4  # Increased width for hex columns

            for i in range(self._bytes_per_line):
                col_x = i * col_width

                # Add extra space for group separator
                if i > 0 and i % self._bytes_per_group == 0:
                    col_x += self._char_width

                if rel_x >= col_x and rel_x < col_x + col_width:
                    col = i
                    break

        elif in_ascii_area:
            # Calculate column in ASCII area
            rel_x = pos.x() - ascii_start_x
            col = rel_x // int(self._char_width * 1.5)

        if col >= 0 and col < self._bytes_per_line:
            byte_addr = row * self._bytes_per_line + col
            if byte_addr < len(self._data):
                return byte_addr

        return -1

    def wheelEvent(self, event: QtGui.QWheelEvent):
        """Handle mouse wheel events."""
        if len(self._data) == 0:
            return

        # Check if we should scroll horizontally (with Shift key)
        if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
            # Horizontal scrolling
            if not self._h_scrollbar.isVisible():
                return

            # Calculate scroll amount
            delta = event.angleDelta().x() if event.angleDelta().x() != 0 else event.angleDelta().y()
            pixels_to_scroll = max(self._char_width * 2, abs(delta) // 4)

            if delta > 0:
                # Scroll left
                self._h_scrollbar.setValue(max(0, self._h_scrollbar.value() - pixels_to_scroll))
            else:
                # Scroll right
                max_scroll = self._h_scrollbar.maximum()
                self._h_scrollbar.setValue(min(max_scroll, self._h_scrollbar.value() + pixels_to_scroll))

        else:
            # Vertical scrolling
            if not self._v_scrollbar.isVisible():
                return

            # Calculate scroll amount
            delta = event.angleDelta().y()
            lines_to_scroll = max(1, abs(delta) // 40)

            if delta > 0:
                # Scroll up
                self._v_scrollbar.setValue(max(0, self._v_scrollbar.value() - lines_to_scroll))
            else:
                # Scroll down
                max_first_line = self._total_lines - self._visible_lines
                self._v_scrollbar.setValue(min(max_first_line, self._v_scrollbar.value() + lines_to_scroll))

        self.update()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Handle key press events."""
        if len(self._data) == 0:
            return

        if event.key() == QtGui.Qt.Key.Key_Left:
            # Move cursor left
            if self._cursor_pos > 0:
                self._cursor_pos -= 1

                # Update selection if shift is pressed
                if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                    if self._selection_start < 0:
                        self._selection_start = self._cursor_pos + 1
                    self._selection_end = self._cursor_pos
                else:
                    self._selection_start = self._selection_end = self._cursor_pos

                # Ensure cursor is visible
                self._ensure_cursor_visible()
                self.update()
                self.cursorPositionChanged.emit(self._cursor_pos)
                self.selectionChanged.emit(
                    min(self._selection_start, self._selection_end),
                    max(self._selection_start, self._selection_end)
                )

        elif event.key() == QtGui.Qt.Key.Key_Right:
            # Move cursor right
            if self._cursor_pos < len(self._data) - 1:
                self._cursor_pos += 1

                # Update selection if shift is pressed
                if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                    if self._selection_start < 0:
                        self._selection_start = self._cursor_pos - 1
                    self._selection_end = self._cursor_pos
                else:
                    self._selection_start = self._selection_end = self._cursor_pos

                # Ensure cursor is visible
                self._ensure_cursor_visible()
                self.update()
                self.cursorPositionChanged.emit(self._cursor_pos)
                self.selectionChanged.emit(
                    min(self._selection_start, self._selection_end),
                    max(self._selection_start, self._selection_end)
                )

        elif event.key() == QtGui.Qt.Key.Key_Up:
            # Move cursor up
            if self._cursor_pos >= self._bytes_per_line:
                self._cursor_pos -= self._bytes_per_line

                # Update selection if shift is pressed
                if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                    if self._selection_start < 0:
                        self._selection_start = self._cursor_pos + self._bytes_per_line
                    self._selection_end = self._cursor_pos
                else:
                    self._selection_start = self._selection_end = self._cursor_pos

                # Ensure cursor is visible
                self._ensure_cursor_visible()
                self.update()
                self.cursorPositionChanged.emit(self._cursor_pos)
                self.selectionChanged.emit(
                    min(self._selection_start, self._selection_end),
                    max(self._selection_start, self._selection_end)
                )

        elif event.key() == QtGui.Qt.Key.Key_Down:
            # Move cursor down
            if self._cursor_pos + self._bytes_per_line < len(self._data):
                self._cursor_pos += self._bytes_per_line

                # Update selection if shift is pressed
                if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                    if self._selection_start < 0:
                        self._selection_start = self._cursor_pos - self._bytes_per_line
                    self._selection_end = self._cursor_pos
                else:
                    self._selection_start = self._selection_end = self._cursor_pos

                # Ensure cursor is visible
                self._ensure_cursor_visible()
                self.update()
                self.cursorPositionChanged.emit(self._cursor_pos)
                self.selectionChanged.emit(
                    min(self._selection_start, self._selection_end),
                    max(self._selection_start, self._selection_end)
                )

        elif event.key() == QtGui.Qt.Key.Key_Home:
            # Move cursor to start of line
            line_start = (self._cursor_pos // self._bytes_per_line) * self._bytes_per_line
            self._cursor_pos = line_start

            # Update selection if shift is pressed
            if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                if self._selection_start < 0:
                    self._selection_start = line_start + self._bytes_per_line - 1
                self._selection_end = self._cursor_pos
            else:
                self._selection_start = self._selection_end = self._cursor_pos

            # Ensure cursor is visible
            self._ensure_cursor_visible()
            self.update()
            self.cursorPositionChanged.emit(self._cursor_pos)
            self.selectionChanged.emit(
                min(self._selection_start, self._selection_end),
                max(self._selection_start, self._selection_end)
            )

        elif event.key() == QtGui.Qt.Key.Key_End:
            # Move cursor to end of line
            line_start = (self._cursor_pos // self._bytes_per_line) * self._bytes_per_line
            line_end = min(line_start + self._bytes_per_line - 1, len(self._data) - 1)
            self._cursor_pos = line_end

            # Update selection if shift is pressed
            if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                if self._selection_start < 0:
                    self._selection_start = line_start
                self._selection_end = self._cursor_pos
            else:
                self._selection_start = self._selection_end = self._cursor_pos

            # Ensure cursor is visible
            self._ensure_cursor_visible()
            self.update()
            self.cursorPositionChanged.emit(self._cursor_pos)
            self.selectionChanged.emit(
                min(self._selection_start, self._selection_end),
                max(self._selection_start, self._selection_end)
            )

        elif event.key() == QtGui.Qt.Key.Key_PageUp:
            # Move cursor up one page
            old_pos = self._cursor_pos
            lines_to_move = min(self._visible_lines, self._cursor_pos // self._bytes_per_line)
            self._cursor_pos -= lines_to_move * self._bytes_per_line

            # Update selection if shift is pressed
            if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                if self._selection_start < 0:
                    self._selection_start = old_pos
                self._selection_end = self._cursor_pos
            else:
                self._selection_start = self._selection_end = self._cursor_pos

            # Ensure cursor is visible
            self._ensure_cursor_visible()
            self.update()
            self.cursorPositionChanged.emit(self._cursor_pos)
            self.selectionChanged.emit(
                min(self._selection_start, self._selection_end),
                max(self._selection_start, self._selection_end)
            )

        elif event.key() == QtGui.Qt.Key.Key_PageDown:
            # Move cursor down one page
            old_pos = self._cursor_pos
            bytes_per_page = self._visible_lines * self._bytes_per_line

            if self._cursor_pos + bytes_per_page < len(self._data):
                self._cursor_pos += bytes_per_page
            else:
                self._cursor_pos = len(self._data) - 1

            # Update selection if shift is pressed
            if event.modifiers() & QtGui.Qt.KeyboardModifier.ShiftModifier:
                if self._selection_start < 0:
                    self._selection_start = old_pos
                self._selection_end = self._cursor_pos
            else:
                self._selection_start = self._selection_end = self._cursor_pos

            # Ensure cursor is visible
            self._ensure_cursor_visible()
            self.update()
            self.cursorPositionChanged.emit(self._cursor_pos)
            self.selectionChanged.emit(
                min(self._selection_start, self._selection_end),
                max(self._selection_start, self._selection_end)
            )

        elif event.key() == QtGui.Qt.Key.Key_Escape:
            # Clear selection
            self._selection_start = self._selection_end = -1
            self.update()
            self.selectionChanged.emit(-1, -1)

        else:
            super().keyPressEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Paint the hex viewer."""
        h_offset = self._h_scrollbar.value()

        painter = QtGui.QPainter(self)
        painter.setFont(self.font())

        # Calculate basic layout measurements - avoid drawing in scrollbar area
        rect = self._hex_widget.geometry()

        # Adjust for horizontal scrolling
        painter.translate(-h_offset, 0)

        # If no data, just display a message
        if len(self._data) == 0:
            painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, "No data")
            return

        # Calculate layout
        address_width = self._calculate_address_width()
        hex_width = (self._char_width * 4) * self._bytes_per_line  # Increased width for hex columns
        if self._bytes_per_group > 1:
            # Extra space between groups
            hex_width += (self._bytes_per_line // self._bytes_per_group - 1) * self._char_width

        ascii_width = 0
        if self._show_ascii:
            ascii_width = int(self._char_width * 1.5) * self._bytes_per_line  # Increased spacing for ASCII chars

        # Draw the header
        self._draw_header(painter, rect, address_width, hex_width, ascii_width)

        # Adjusted rect for content
        header_height = self._char_height + 8  # Increased header height
        rect.setTop(rect.top() + header_height)

        # Draw content rows
        self._draw_hex_content(painter, rect, address_width, hex_width, ascii_width)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent):
        """Handle context menu events."""
        menu = QtWidgets.QMenu(self)

        # Copy actions
        copy_hex_action = QtGui.QAction("Copy as Hex", self)
        copy_hex_action.triggered.connect(self._copy_selection_as_hex)
        menu.addAction(copy_hex_action)

        copy_ascii_action = QtGui.QAction("Copy as ASCII", self)
        copy_ascii_action.triggered.connect(self._copy_selection_as_ascii)
        menu.addAction(copy_ascii_action)

        # Selection actions
        menu.addSeparator()

        select_all_action = QtGui.QAction("Select All", self)
        select_all_action.triggered.connect(self._select_all)
        menu.addAction(select_all_action)

        # Navigation actions
        menu.addSeparator()

        go_to_action = QtGui.QAction("Go to Address...", self)
        go_to_action.triggered.connect(self._go_to_address)
        menu.addAction(go_to_action)

        # Execute the menu
        menu.exec(event.globalPos())

    def _copy_selection_as_hex(self):
        """Copy the selected bytes as hex values."""
        if self._selection_start < 0 or len(self._data) == 0:
            return

        start = min(self._selection_start, self._selection_end)
        end = max(self._selection_start, self._selection_end)

        if start >= len(self._data):
            start = len(self._data) - 1
        if end >= len(self._data):
            end = len(self._data) - 1

        selected_bytes = self._data[start:end+1]
        hex_text = ' '.join(f"{b:02X}" for b in selected_bytes)

        QtWidgets.QApplication.clipboard().setText(hex_text)

    def _copy_selection_as_ascii(self):
        """Copy the selected bytes as ASCII text."""
        if self._selection_start < 0 or len(self._data) == 0:
            return

        start = min(self._selection_start, self._selection_end)
        end = max(self._selection_start, self._selection_end)

        if start >= len(self._data):
            start = len(self._data) - 1
        if end >= len(self._data):
            end = len(self._data) - 1

        selected_bytes = self._data[start:end+1]
        ascii_text = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in selected_bytes)

        QtWidgets.QApplication.clipboard().setText(ascii_text)

    def _select_all(self):
        """Select all bytes."""
        if len(self._data) == 0:
            return

        self._selection_start = 0
        self._selection_end = len(self._data) - 1
        self._cursor_pos = self._selection_end

        self.update()
        self.cursorPositionChanged.emit(self._cursor_pos)
        self.selectionChanged.emit(self._selection_start, self._selection_end)

    def _go_to_address(self):
        """Go to a specific address."""
        address, ok = QtWidgets.QInputDialog.getText(
            self, "Go to Address", "Enter address (decimal or 0x prefix for hex):"
        )

        if ok and address:
            try:
                # Try to parse as hex if it has 0x prefix
                if address.lower().startswith("0x"):
                    addr = int(address[2:], 16)
                else:
                    addr = int(address)

                # Ensure address is in range
                if 0 <= addr < len(self._data):
                    self._cursor_pos = addr
                    self._selection_start = self._selection_end = addr

                    self._ensure_cursor_visible()
                    self.update()
                    self.cursorPositionChanged.emit(self._cursor_pos)
                    self.selectionChanged.emit(addr, addr)
                else:
                    QtWidgets.QMessageBox.warning(
                        self, "Invalid Address",
                        f"Address must be between 0 and {len(self._data)-1}"
                    )
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid Address",
                    "Please enter a valid decimal or hexadecimal address"
                )

DATA_INSPECTOR_TYPES = {
    "binary": lambda data, pos, little_endian: f"{data[pos]:08b}",
    "octal": lambda data, pos, little_endian: f"{data[pos]:03o}",
    "uint8": lambda data, pos, little_endian: data[pos],
    "int8": lambda data, pos, little_endian: int.from_bytes([data[pos]], byteorder='little' if little_endian else 'big', signed=True),
    "uint16": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+2], byteorder='little' if little_endian else 'big', signed=False) if pos+1 < len(data) else None,
    "int16": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+2], byteorder='little' if little_endian else 'big', signed=True) if pos+1 < len(data) else None,
    "uint24": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+3], byteorder='little' if little_endian else 'big', signed=False) if pos+2 < len(data) else None,
    "int24": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+3], byteorder='little' if little_endian else 'big', signed=True) if pos+2 < len(data) else None,
    "uint32": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+4], byteorder='little' if little_endian else 'big', signed=False) if pos+3 < len(data) else None,
    "int32": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+4], byteorder='little' if little_endian else 'big', signed=True) if pos+3 < len(data) else None,
    "uint64": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+8], byteorder='little' if little_endian else 'big', signed=False) if pos+7 < len(data) else None,
    "int64": lambda data, pos, little_endian: int.from_bytes(data[pos:pos+8], byteorder='little' if little_endian else 'big', signed=True) if pos+7 < len(data) else None,
    "ULEB128": lambda data, pos, little_endian: decode_uleb128(data, pos),
    "SLEB128": lambda data, pos, little_endian: decode_sleb128(data, pos),
    "float16": lambda data, pos, little_endian: struct.unpack('<e' if little_endian else '>e', data[pos:pos+2])[0] if pos+1 < len(data) else None,
    "bfloat16": lambda data, pos, little_endian: struct.unpack('<f', data[pos:pos+2] + b'\x00\x00')[0] if pos+1 < len(data) else None,
    "float32": lambda data, pos, little_endian: struct.unpack('<f' if little_endian else '>f', data[pos:pos+4])[0] if pos+3 < len(data) else None,
    "float64": lambda data, pos, little_endian: struct.unpack('<d' if little_endian else '>d', data[pos:pos+8])[0] if pos+7 < len(data) else None,
    #"GUID": lambda data, pos, little_endian: str(uuid.UUID(bytes_le=bytes(data[pos:pos+16]))) if pos+15 < len(data) else None,
    "ASCII": lambda data, pos, little_endian: chr(data[pos]) if 32 <= data[pos] <= 126 else '.' if pos < len(data) else None,
    "UTF-8": lambda data, pos, little_endian: bytes([data[pos]]).decode('utf-8', errors='replace') if pos < len(data) else None,
    "UTF-16": lambda data, pos, little_endian: bytes(data[pos:pos+2]).decode('utf-16-le' if little_endian else 'utf-16-be', errors='replace') if pos+1 < len(data) else None,
    "GB18030": lambda data, pos, little_endian: bytes([data[pos]]).decode('gb18030', errors='replace') if pos < len(data) else None,
    "BIG5": lambda data, pos, little_endian: bytes([data[pos]]).decode('big5', errors='replace') if pos < len(data) else None,
    "SHIFT-JIS": lambda data, pos, little_endian: bytes([data[pos]]).decode('shift-jis', errors='replace') if pos < len(data) else None,
}

class HexViewer(QtWidgets.QWidget):
    """Main widget for the Hex Viewer."""

    # Viewer name
    name = "Hex Viewer"

    _data_inspector_labels: dict[str, QtWidgets.QLabel] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.area = HexArea(self)

        layout = QtWidgets.QVBoxLayout(self)

        self._toolbar = QtWidgets.QToolBar(self)

        # ASCII view toggle
        self._ascii_action = QtGui.QAction("ASCII View", self)
        self._ascii_action.setCheckable(True)
        self._ascii_action.setChecked(self.area.show_ascii)
        def toggle_ascii_view():
            self.area.show_ascii = self._ascii_action.isChecked()
        self._ascii_action.toggled.connect(toggle_ascii_view)
        self._toolbar.addAction(self._ascii_action)

        self._toolbar.addSeparator()

        # Data Inspector area
        self._data_inspector_action = QtGui.QAction("Data Inspector", self)
        self._data_inspector_action.setCheckable(True)
        self._data_inspector_action.setChecked(True)
        self._data_inspector_action.toggled.connect(
            lambda: self._data_inspector.setVisible(self._data_inspector_action.isChecked())
        )
        self._toolbar.addAction(self._data_inspector_action)

        self._toolbar.addSeparator()

        # Address base selector
        self._addr_base_label = QtWidgets.QLabel("Address Base:")
        self._toolbar.addWidget(self._addr_base_label)

        self._addr_base_combo = QtWidgets.QComboBox()
        self._addr_base_combo.addItems(["Hexadecimal", "Decimal", "Octal"])
        self._addr_base_combo.setCurrentIndex(0)
        def update_addressing_base(index):
            if index == 0:
                self.area.addressing_base = 16
            elif index == 1:
                self.area.addressing_base = 10
            else:
                self.area.addressing_base = 8
        self._addr_base_combo.currentIndexChanged.connect(update_addressing_base)
        self._toolbar.addWidget(self._addr_base_combo)

        self._toolbar.addSeparator()

        # Bytes per line selector
        self._bytes_per_line_label = QtWidgets.QLabel("Bytes per Line:")
        self._toolbar.addWidget(self._bytes_per_line_label)

        self._bytes_per_line_combo = QtWidgets.QComboBox()
        self._bytes_per_line_combo.addItems(["8", "16", "32", "64"])
        self._bytes_per_line_combo.setCurrentIndex(1)
        def update_bytes_per_line(index):
            self.area.bytes_per_line = int(self._bytes_per_line_combo.currentText())
            self.area.update()
        self._bytes_per_line_combo.currentIndexChanged.connect(update_bytes_per_line)
        self._toolbar.addWidget(self._bytes_per_line_combo)

        self._status_bar_layout = QtWidgets.QHBoxLayout()

        self._cursor_location = QtWidgets.QLabel("Line: 1, Column: 1")
        self._status_bar_layout.addWidget(self._cursor_location)

        self._status_bar_layout.addStretch()

        self._total_bytes_label = QtWidgets.QLabel("0 bytes in total")
        self._status_bar_layout.addWidget(self._total_bytes_label)

        center_layout = QtWidgets.QHBoxLayout()

        self._data_inspector = QtWidgets.QWidget(self)
        self._data_inspector_layout = QtWidgets.QVBoxLayout(self._data_inspector)
        self._data_inspector_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        data_inspector_label = QtWidgets.QLabel("Data Inspector")
        data_inspector_label.setStyleSheet("font-weight: bold;")
        self._data_inspector_layout.addWidget(data_inspector_label)

        value_font = QtGui.QFont("Space Mono")

        for name in DATA_INSPECTOR_TYPES:
            name_layout = QtWidgets.QHBoxLayout()
            name_label = QtWidgets.QLabel(name + ": ")
            name_layout.addWidget(name_label)
            value_label = QtWidgets.QLabel()
            value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            value_label.setFont(value_font)
            name_layout.addWidget(value_label)
            self._data_inspector_labels[name] = value_label
            self._data_inspector_layout.addLayout(name_layout)

        self._data_inspector_little_endian = QtWidgets.QCheckBox("Little Endian")
        self._data_inspector_little_endian.setChecked(True)
        self._data_inspector_little_endian.checkStateChanged.connect(self._update_data_inspector)
        self._data_inspector_layout.addWidget(self._data_inspector_little_endian)

        center_layout.addWidget(self.area, stretch=1)
        center_layout.addSpacing(5)
        center_layout.addWidget(self._data_inspector)

        layout.addWidget(self._toolbar)
        layout.addLayout(center_layout, stretch=1)
        layout.addLayout(self._status_bar_layout)

        self.area.cursorPositionChanged.connect(
            lambda:(
                self._cursor_location.setText(f"Line: {self.area.cursor_pos[0]}, Column: {self.area.cursor_pos[1]}"),
                self._update_data_inspector()
            )
        )

    def _update_data_inspector(self):
        """Update the data inspector labels based on the current cursor position."""

        if not self._data_inspector.isVisible():
            return

        if len(self.area.data) == 0:
            for label in self._data_inspector_labels.values():
                label.setText("")
            return

        little_endian = self._data_inspector_little_endian.isChecked()

        for name, label in self._data_inspector_labels.items():
            value = DATA_INSPECTOR_TYPES[name](self.area.data, self.area.cursor_byte_pos, little_endian)
            if value is not None:
                label.setText(str(value))
            else:
                label.setText("")

    def setData(self, data: bytearray):
        """Set the data to be displayed in the hex viewer."""
        self._total_bytes_label.setText(f"{len(data)} bytes in total")
        self.area.data = data
        self._update_data_inspector()
