"""
Pyc/Bindict file viewer - displays parsed dictionaries as Python dict
"""

import sys
from pathlib import Path

# 确保可以导入 core 模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from core.npk.class_types import NPKEntry
from gui.widgets.viewer import Viewer


class PythonHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for Python code"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._formats = {}
        
        # Keywords
        keyword_format = QtGui.QTextCharFormat()
        keyword_format.setForeground(QtGui.QColor("#569CD6"))
        keyword_format.setFontWeight(QtGui.QFont.Bold)
        
        keywords = [
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "class", "continue", "def", "del", "elif", "else", "except",
            "finally", "for", "from", "global", "if", "import", "in", "is",
            "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
            "while", "with", "yield"
        ]
        for word in keywords:
            self._formats[word] = keyword_format
        
        # Strings
        string_format = QtGui.QTextCharFormat()
        string_format.setForeground(QtGui.QColor("#CE9178"))
        self._formats["string"] = string_format
        
        # Numbers
        number_format = QtGui.QTextCharFormat()
        number_format.setForeground(QtGui.QColor("#B5CEA8"))
        self._formats["number"] = number_format
        
        # Comments
        comment_format = QtGui.QTextCharFormat()
        comment_format.setForeground(QtGui.QColor("#6A9955"))
        self._formats["comment"] = comment_format
    
    def highlightBlock(self, text: str):
        """Highlight a block of text"""
        import re
        
        # Highlight strings
        string_pattern = r"('([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\")"
        for match in re.finditer(string_pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self._formats["string"])
        
        # Highlight comments
        comment_pattern = r"#[^\n]*"
        for match in re.finditer(comment_pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self._formats["comment"])
        
        # Highlight numbers
        number_pattern = r"\b\d+\.?\d*\b"
        for match in re.finditer(number_pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self._formats["number"])
        
        # Highlight keywords
        word_pattern = r"\b\w+\b"
        for match in re.finditer(word_pattern, text):
            word = match.group()
            if word in self._formats:
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, self._formats[word])


class PycViewer(Viewer):
    """Python Compiled (.pyc) / Binary Dictionary Viewer"""
    
    name = "Python Compiled / Dictionary"
    accepted_extensions = ["pyc"]
    allow_unsupported_extensions = False
    
    def __init__(self):
        super().__init__()
        self._parser = None
        self._parser_error = None
        self._current_data = None
        
        self._text_edit = QtWidgets.QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QtGui.QFont("Consolas", 10))
        
        # 添加语法高亮
        self._highlighter = PythonHighlighter(self._text_edit.document())
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._text_edit)
        
        # 延迟导入 parser，避免启动时出错
        self._init_parser()
    
    def _init_parser(self):
        """延迟初始化 parser"""
        try:
            from bindict.parser import BindictParser
            self._parser = BindictParser()
        except ImportError as e:
            self._parser_error = str(e)
            self._text_edit.setPlainText(f"# Bindict module not available: {self._parser_error}")
    
    def _format_value(self, value, indent=0):
        """Format value as Python code"""
        spaces = "  " * indent
        nl = "\n"
        
        if isinstance(value, set):
            if not value:
                return "set()"
            items = []
            for v in sorted(value, key=lambda x: (type(x).__name__, str(x))):
                items.append(self._format_value(v, indent + 1))
            if len(items) == 1:
                return f"set([{items[0]}])"
            items_str = ("," + nl).join(f"{spaces}  {item}" for item in items)
            return f"set([{nl}{items_str}{nl}{spaces}])"
        elif isinstance(value, tuple):
            if len(value) == 1:
                return f"({self._format_value(value[0], indent)},)"
            else:
                items = ", ".join(self._format_value(v, indent) for v in value)
                return f"({items})"
        elif isinstance(value, list):
            if not value:
                return "[]"
            items = ("," + nl).join(f"{spaces}  {self._format_value(v, indent + 1)}" for v in value)
            return f"[{nl}{items}{nl}{spaces}]"
        elif isinstance(value, dict):
            if not value:
                return "{}"
            items = []
            sorted_keys = sorted(value.keys(), key=lambda k: (type(k).__name__, str(k)))
            for k in sorted_keys:
                key_str = self._format_value(k, indent + 1)
                value_str = self._format_value(value[k], indent + 1)
                items.append(f"{spaces}  {key_str}: {value_str}")
            items_str = ("," + nl).join(items)
            return f"{{{nl}{items_str}{nl}{spaces}}}"
        elif isinstance(value, str):
            escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
            return f"'{escaped}'"
        elif isinstance(value, bool):
            return "True" if value else "False"
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, float):
            return repr(value)
        elif value is None:
            return "None"
        else:
            return str(value)
    
    def set_file(self, file: NPKEntry):
        # 如果 parser 还没初始化，尝试初始化
        if self._parser is None and self._parser_error is None:
            self._init_parser()
        
        if self._parser is None:
            self._text_edit.setPlainText(f"# Parser error: {self._parser_error}")
            return
        
        data = file.data
        
        # Try extracting from pyc
        result = self._parser.extract_from_pyc(data)
        if result:
            self._current_data = result
            formatted = self._format_value(result)
            self._text_edit.setPlainText(formatted)
        else:
            self._text_edit.setPlainText("# No bindict data found in this pyc file")
    
    def unload_file(self):
        self._current_data = None
        self._text_edit.clear()