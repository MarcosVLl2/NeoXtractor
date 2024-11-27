import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont

class HexViewerApp(QMainWindow):
    def __init__(self, npkdata):
        super().__init__()
        self.setWindowTitle("Hex Viewer")
        self.setGeometry(100, 100, 670, 700)
        self.npkdata = npkdata

        self.init_ui()
        self.display_hex_view()  # Automatically display the hex view of npkdata

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout()

        # Hex Viewer
        self.hex_viewer = QTextEdit()
        self.hex_viewer.setReadOnly(True)
        self.hex_viewer.setFont(QFont("Courier", 10))
        main_layout.addWidget(self.hex_viewer)

        # Main widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def display_hex_view(self):
        try:
            # Limit data to the first 64 KB for performance
            max_size = 64 * 1024  # 64 KB
            content = self.npkdata[:max_size]
            truncated = len(self.npkdata) > max_size

            # Display hex content
            self.hex_viewer.setText(self.format_hex_view(content))

            if truncated:
                self.hex_viewer.append("\n[Output truncated for large data]")
        except Exception as e:
            self.hex_viewer.setText(f"Error processing data: {e}")

    def format_hex_view(self, content):
        # Add the header lines
        header = (
            "Offset   | 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f | ASCII\n"
            "---------------------------------------------------------\n"
        )
        lines = []

        for i in range(0, len(content), 16):
            chunk = content[i:i + 16]
            hex_chunk = " ".join(f"{byte:02X}" for byte in chunk)
            ascii_chunk = "".join(chr(byte) if 32 <= byte <= 126 else "░" for byte in chunk)
            lines.append(f"{i:08X} | {hex_chunk.ljust(47)} | {ascii_chunk}")

        return header + "\n".join(lines)
