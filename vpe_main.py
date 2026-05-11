"""
Project: Vibe Programming Environment (VPE) - Build 0.20
Target OS: Linux Mint Only
Description: Restored Independent Workspaces (Per-tab File Managers for isolated directories).
Architecture: PySide6 (Qt) with isolated QFileSystemModels per environment tab.
"""

import sys
import os
import pty
import subprocess
import re
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, 
                             QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QTabWidget,
                             QPlainTextEdit, QToolBar, QMessageBox, QPushButton,
                             QFileSystemModel, QTreeView, QHeaderView,
                             QInputDialog, QFileDialog, QLabel, QStyledItemDelegate)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSocketNotifier, QDir, QRegularExpression, QSize, Signal, QRect, QTimer, QUrl
from PySide6.QtGui import (QAction, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, 
                           QColor, QPainter, QTextFormat, QDesktopServices)

# --- HIGHLIGHTERS ---
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#c678dd")) 
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "\\band\\b", "\\bas\\b", "\\bassert\\b", "\\bbreak\\b", "\\bclass\\b", 
            "\\bcontinue\\b", "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b", 
            "\\bexcept\\b", "\\bFalse\\b", "\\bfinally\\b", "\\bfor\\b", "\\bfrom\\b", 
            "\\bglobal\\b", "\\bif\\b", "\\bimport\\b", "\\bin\\b", "\\bis\\b", 
            "\\blambda\\b", "\\bNone\\b", "\\bnonlocal\\b", "\\bnot\\b", "\\bor\\b", 
            "\\bpass\\b", "\\braise\\b", "\\breturn\\b", "\\bTrue\\b", "\\btry\\b", 
            "\\bwhile\\b", "\\bwith\\b", "\\byield\\b"
        ]
        for word in keywords: self.highlightingRules.append((QRegularExpression(word), keywordFormat))

        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#56b6c2"))
        builtins = ["\\bprint\\b", "\\blen\\b", "\\bstr\\b", "\\bint\\b", "\\bfloat\\b", 
                    "\\btype\\b", "\\blist\\b", "\\bdict\\b", "\\bset\\b", "\\brange\\b"]
        for word in builtins: self.highlightingRules.append((QRegularExpression(word), builtinFormat))

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#e5c07b"))
        self.highlightingRules.append((QRegularExpression("\\bclass\\s+([A-Za-z_]+)"), classFormat))

        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#61afef"))
        self.highlightingRules.append((QRegularExpression("\\bdef\\s+([A-Za-z_]+)"), functionFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#98c379"))
        self.highlightingRules.append((QRegularExpression("\".*?\""), stringFormat))
        self.highlightingRules.append((QRegularExpression("'.*?'"), stringFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#5c6370"))
        commentFormat.setFontItalic(True)
        self.highlightingRules.append((QRegularExpression("#[^\n]*"), commentFormat))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class WebHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        tagFormat = QTextCharFormat()
        tagFormat.setForeground(QColor("#61afef"))
        self.highlightingRules.append((QRegularExpression("</?[a-zA-Z0-9_\\-]+>??"), tagFormat))

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#c678dd"))
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = ["\\bvar\\b", "\\blet\\b", "\\bconst\\b", "\\bfunction\\b", "\\bdocument\\b", 
                    "\\bwindow\\b", "\\bif\\b", "\\belse\\b", "\\bfor\\b", "\\breturn\\b", "\\bbody\\b", "\\bdiv\\b"]
        for word in keywords: self.highlightingRules.append((QRegularExpression(word), keywordFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#98c379"))
        self.highlightingRules.append((QRegularExpression("\".*?\""), stringFormat))
        self.highlightingRules.append((QRegularExpression("'.*?'"), stringFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#5c6370"))
        commentFormat.setFontItalic(True)
        self.highlightingRules.append((QRegularExpression(""), commentFormat))
        self.highlightingRules.append((QRegularExpression("//[^\n]*"), commentFormat))
        self.highlightingRules.append((QRegularExpression("/\\*.*?\\*/"), commentFormat))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


# --- CORE UI COMPONENTS ---
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value /= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#21252b"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#5c6370"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignRight | Qt.AlignVCenter, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1 

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#2c313a") 
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)


class NativeLinuxTerminal(QPlainTextEdit):
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc; font-family: 'Ubuntu Mono', 'Monospace'; font-size: 11pt; border: none;")
        self.master_fd, self.slave_fd = pty.openpty()
        self.process = subprocess.Popen(["/bin/bash"], stdin=self.slave_fd, stdout=self.slave_fd, stderr=self.slave_fd, preexec_fn=os.setsid, env=os.environ)
        self.notifier = QSocketNotifier(self.master_fd, QSocketNotifier.Read)
        self.notifier.activated.connect(self.read_shell_output)

    def read_shell_output(self):
        try:
            data = os.read(self.master_fd, 1024).decode(errors='ignore')
            clean_data = self.ANSI_ESCAPE.sub('', data)
            self.insertPlainText(clean_data)
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        except OSError:
            pass

    def keyPressEvent(self, event):
        text = event.text()
        if event.key() == Qt.Key_Return: text = "\n"
        elif event.key() == Qt.Key_Backspace: text = "\b"
        elif event.key() == Qt.Key_Tab: text = "\t"
        if text: os.write(self.master_fd, text.encode())

    def send_command(self, command: str):
        if not command.endswith("\n"):
            command += "\n"
        os.write(self.master_fd, command.encode())


class RunFileDelegate(QStyledItemDelegate):
    """Paints dynamic Run/Open icons based on file extension."""
    run_requested = Signal(str)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        model = index.model()
        if hasattr(model, 'filePath'):
            path = model.filePath(index)
            is_py = path.endswith('.py')
            is_html = path.endswith('.html')
            
            if os.path.isfile(path) and (is_py or is_html):
                rect = option.rect
                btn_rect = QRect(rect.right() - 32, rect.top() + (rect.height() - 20) // 2, 24, 20)
                
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(QColor("#2d2d2d"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(btn_rect, 4, 4)
                
                if is_py:
                    painter.setPen(QColor("#98c379")) 
                    icon_text = "▶"
                else:
                    painter.setPen(QColor("#61afef")) 
                    icon_text = "🌐"
                
                font = painter.font()
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(btn_rect, Qt.AlignCenter, icon_text)
                painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == event.Type.MouseButtonRelease:
            path = model.filePath(index)
            if os.path.isfile(path) and (path.endswith('.py') or path.endswith('.html')):
                rect = option.rect
                btn_rect = QRect(rect.right() - 32, rect.top() + (rect.height() - 20) // 2, 24, 20)
                if btn_rect.contains(event.position().toPoint()):
                    self.run_requested.emit(path)
                    return True 
        return super().editorEvent(event, model, option, index)


class BreadcrumbNavigation(QWidget):
    def __init__(self, navigation_callback):
        super().__init__()
        self.navigation_callback = navigation_callback
        self.furthest_path = "/"
        
        self.setAttribute(Qt.WA_StyledBackground, True) 
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)
        
        self.setStyleSheet("""
            BreadcrumbNavigation { background-color: #21252b; border-bottom: 1px solid #181a1f; }
            QPushButton { background-color: transparent; border: none; font-weight: bold; font-size: 10pt; padding: 4px 6px; border-radius: 4px; }
            QPushButton[state="active"] { color: #ffffff; background-color: #3e4451; }
            QPushButton[state="parent"] { color: #8b9eb0; }
            QPushButton[state="ghost"] { color: #5c6370; }
            QPushButton:hover { background-color: #4b5263; color: #ffffff; }
            QLabel { color: #5c6370; font-weight: bold; font-size: 11pt; }
        """)

    def build_path(self, active_path):
        check_path = active_path if active_path.endswith(os.sep) else active_path + os.sep
        if not self.furthest_path.startswith(check_path) and self.furthest_path != active_path:
            self.furthest_path = active_path

        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()

        parts = [p for p in self.furthest_path.split(os.sep) if p]
        
        root_btn = QPushButton("/")
        root_btn.setCursor(Qt.PointingHandCursor)
        root_btn.setProperty("state", "active" if active_path == "/" else "parent")
        root_btn.clicked.connect(lambda: self.navigation_callback("/"))
        self.layout.addWidget(root_btn)

        current_path = "/"
        is_past_active = (active_path == "/")

        for part in parts:
            separator = QLabel("›")
            self.layout.addWidget(separator)
            
            current_path = os.path.join(current_path, part)
            btn = QPushButton(part)
            btn.setCursor(Qt.PointingHandCursor)
            
            if current_path == active_path:
                btn.setProperty("state", "active")
                is_past_active = True
            elif is_past_active:
                btn.setProperty("state", "ghost")
            else:
                btn.setProperty("state", "parent")
            
            btn.clicked.connect(lambda checked=False, target=current_path: self.navigation_callback(target))
            self.layout.addWidget(btn)
            
        self.layout.addStretch()


# --- ISOLATED ENVIRONMENTS ---
class PythonEnvironment(QWidget):
    """Isolated Workspace for Python with dedicated File Manager and Terminal."""
    def __init__(self, root_path: str):
        super().__init__()
        self.current_file_path = None
        self.root_path = root_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        
        # 1. Independent File Manager for Python Tab
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)
        
        self.sidebar_toolbar = QToolBar()
        self.sidebar_toolbar.setStyleSheet("""
            QToolBar { background-color: #2d2d2d; border: none; }
            QToolButton { font-size: 16pt; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
        """)
        
        open_folder_btn = QAction("📂 Open", self)
        open_folder_btn.triggered.connect(self.open_workspace_dialog)
        self.sidebar_toolbar.addAction(open_folder_btn)

        new_folder_btn = QAction("📁 New", self)
        new_folder_btn.triggered.connect(self.create_new_folder)
        self.sidebar_toolbar.addAction(new_folder_btn)
        
        self.sidebar_layout.addWidget(self.sidebar_toolbar)
        
        self.breadcrumb = BreadcrumbNavigation(self.set_workspace_root)
        self.sidebar_layout.addWidget(self.breadcrumb)

        self.file_model = QFileSystemModel()
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True) 
        self.tree.setIconSize(QSize(32, 32))
        
        self.run_delegate = RunFileDelegate()
        self.run_delegate.run_requested.connect(self.execute_script)
        self.tree.setItemDelegateForColumn(0, self.run_delegate)
        
        self.tree.setStyleSheet("""
            QTreeView { background-color: #21252b; color: #abb2bf; border: none; font-size: 10pt; }
            QTreeView::item { padding: 4px; }
            QTreeView::item:selected { background-color: #2c313a; color: #ffffff; }
        """)
        self.tree.doubleClicked.connect(self.handle_tree_double_click)
        self.sidebar_layout.addWidget(self.tree)
        
        self.set_workspace_root(self.root_path)

        # 2. Editor & Terminal
        self.edit_term_splitter = QSplitter(Qt.Vertical)
        
        self.editor_container = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_container)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(0)

        self.editor_toolbar = QToolBar()
        self.editor_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border-bottom: 1px solid #181a1f; padding: 4px; }
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
        """)

        self.commit_code_btn = QAction("📋 Commit Code", self)
        self.commit_code_btn.triggered.connect(self.commit_code_from_clipboard)
        self.editor_toolbar.addAction(self.commit_code_btn)

        self.undo_commit_btn = QAction("↩️ Undo Commit", self)
        self.undo_commit_btn.triggered.connect(self.undo_commit_and_save)
        self.editor_toolbar.addAction(self.undo_commit_btn)

        self.editor_layout.addWidget(self.editor_toolbar)

        self.editor = CodeEditor()
        self.editor.setStyleSheet("background-color: #282c34; color: #abb2bf; border: none; padding: 10px;")
        font = QFont("Ubuntu Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("# Start typing, then hit Ctrl+S to save...\n# Or copy text from your browser and click '📋 Commit Code'.")
        
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor_layout.addWidget(self.editor)

        self.terminal = NativeLinuxTerminal()
        
        self.edit_term_splitter.addWidget(self.editor_container)
        self.edit_term_splitter.addWidget(self.terminal)
        self.edit_term_splitter.setSizes([600, 300])
        
        self.workspace_splitter.addWidget(self.sidebar_container)
        self.workspace_splitter.addWidget(self.edit_term_splitter)
        self.workspace_splitter.setSizes([250, 1000])
        
        layout.addWidget(self.workspace_splitter)

    def execute_script(self, file_path):
        if self.current_file_path == file_path:
            self.save_current_file()
            
        if file_path.endswith('.py'):
            working_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            cmd = f"cd '{working_dir}' && python3 '{file_name}'"
            self.terminal.send_command(cmd)
        elif file_path.endswith('.html'):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def commit_code_from_clipboard(self):
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text: return
        self.editor.selectAll()
        self.editor.insertPlainText(clipboard_text)
        self.save_current_file()
        self.commit_code_btn.setText("✅ Committed!")
        QTimer.singleShot(2000, lambda: self.commit_code_btn.setText("📋 Commit Code"))

    def undo_commit_and_save(self):
        self.editor.undo()
        self.save_current_file()
        self.undo_commit_btn.setText("✅ Undone!")
        QTimer.singleShot(2000, lambda: self.undo_commit_btn.setText("↩️ Undo Commit"))

    def set_workspace_root(self, path):
        if os.path.isdir(path):
            self.root_path = path
            self.file_model.setRootPath(self.root_path)
            self.tree.setRootIndex(self.file_model.index(self.root_path))
            self.breadcrumb.build_path(self.root_path)

    def open_workspace_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace Folder", self.root_path)
        if dir_path: self.set_workspace_root(dir_path)

    def handle_tree_double_click(self, index):
        path = self.file_model.filePath(index)
        if os.path.isdir(path):
            self.set_workspace_root(path)
        elif os.path.isfile(path):
            try:
                with open(path, 'r') as f: content = f.read()
                self.editor.setPlainText(content)
                self.current_file_path = path
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def create_new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            target_dir = QDir(self.root_path)
            if not target_dir.exists(folder_name): target_dir.mkdir(folder_name)

    def save_current_file(self):
        content = self.editor.toPlainText()
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save New File", self.root_path, "Python Files (*.py);;All Files (*)")
            if file_path: self.current_file_path = file_path
            else: return False 
        try:
            with open(self.current_file_path, 'w') as f: f.write(content)
            return True
        except: return False


class WebEnvironment(QWidget):
    """Isolated Workspace for Web Dev with dedicated File Manager and Preview."""
    def __init__(self, root_path: str):
        super().__init__()
        self.current_file_path = None
        self.root_path = root_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        
        # 1. Independent File Manager for Web Tab
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)
        
        self.sidebar_toolbar = QToolBar()
        self.sidebar_toolbar.setStyleSheet("""
            QToolBar { background-color: #2d2d2d; border: none; }
            QToolButton { font-size: 16pt; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
        """)
        
        open_folder_btn = QAction("📂 Open", self)
        open_folder_btn.triggered.connect(self.open_workspace_dialog)
        self.sidebar_toolbar.addAction(open_folder_btn)

        new_folder_btn = QAction("📁 New", self)
        new_folder_btn.triggered.connect(self.create_new_folder)
        self.sidebar_toolbar.addAction(new_folder_btn)
        
        self.sidebar_layout.addWidget(self.sidebar_toolbar)
        self.breadcrumb = BreadcrumbNavigation(self.set_workspace_root)
        self.sidebar_layout.addWidget(self.breadcrumb)

        self.file_model = QFileSystemModel()
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True) 
        self.tree.setIconSize(QSize(32, 32))
        
        self.run_delegate = RunFileDelegate()
        self.run_delegate.run_requested.connect(self.execute_script)
        self.tree.setItemDelegateForColumn(0, self.run_delegate)
        
        self.tree.setStyleSheet("""
            QTreeView { background-color: #21252b; color: #abb2bf; border: none; font-size: 10pt; }
            QTreeView::item { padding: 4px; }
            QTreeView::item:selected { background-color: #2c313a; color: #ffffff; }
        """)
        self.tree.doubleClicked.connect(self.handle_tree_double_click)
        self.sidebar_layout.addWidget(self.tree)
        self.set_workspace_root(self.root_path)

        # 2. Editor & Live Preview
        self.editor_container = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_container)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(0)

        self.editor_toolbar = QToolBar()
        self.editor_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; }
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
        """)

        self.commit_code_btn = QAction("📋 Commit Code", self)
        self.commit_code_btn.triggered.connect(self.commit_code_from_clipboard)
        self.editor_toolbar.addAction(self.commit_code_btn)

        self.undo_commit_btn = QAction("↩️ Undo Commit", self)
        self.undo_commit_btn.triggered.connect(self.undo_commit_and_save)
        self.editor_toolbar.addAction(self.undo_commit_btn)

        self.editor_layout.addWidget(self.editor_toolbar)

        self.editor = CodeEditor()
        self.editor.setStyleSheet("background-color: #282c34; color: #abb2bf; border: none; padding: 10px;")
        font = QFont("Ubuntu Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("\n<h1>Hello Web Vibe!</h1>")
        self.highlighter = WebHighlighter(self.editor.document())
        self.editor_layout.addWidget(self.editor)

        self.preview_view = QWebEngineView()
        self.preview_view.setStyleSheet("background-color: #ffffff;")
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.update_live_preview)
        self.editor.textChanged.connect(lambda: self.render_timer.start(500))

        self.workspace_splitter.addWidget(self.sidebar_container)
        self.workspace_splitter.addWidget(self.editor_container)
        self.workspace_splitter.addWidget(self.preview_view)
        
        self.workspace_splitter.setSizes([200, 600, 500]) 
        layout.addWidget(self.workspace_splitter)
        self.update_live_preview()

    def execute_script(self, file_path):
        if self.current_file_path == file_path:
            self.save_current_file()
            
        if file_path.endswith('.html'):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        elif file_path.endswith('.py'):
            # Fallback for Python files in the Web tab
            working_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"cd '{working_dir}' && python3 '{file_name}'; exec bash"])

    def update_live_preview(self):
        html_content = self.editor.toPlainText()
        base_url = QUrl.fromLocalFile(self.root_path + os.sep)
        self.preview_view.setHtml(html_content, base_url)

    def commit_code_from_clipboard(self):
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text: return
        self.editor.selectAll()
        self.editor.insertPlainText(clipboard_text)
        self.save_current_file()
        self.commit_code_btn.setText("✅ Committed!")
        QTimer.singleShot(2000, lambda: self.commit_code_btn.setText("📋 Commit Code"))

    def undo_commit_and_save(self):
        self.editor.undo()
        self.save_current_file()
        self.undo_commit_btn.setText("✅ Undone!")
        QTimer.singleShot(2000, lambda: self.undo_commit_btn.setText("↩️ Undo Commit"))

    def set_workspace_root(self, path):
        if os.path.isdir(path):
            self.root_path = path
            self.file_model.setRootPath(self.root_path)
            self.tree.setRootIndex(self.file_model.index(self.root_path))
            self.breadcrumb.build_path(self.root_path)

    def open_workspace_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace Folder", self.root_path)
        if dir_path: self.set_workspace_root(dir_path)

    def handle_tree_double_click(self, index):
        path = self.file_model.filePath(index)
        if os.path.isdir(path):
            self.set_workspace_root(path)
        elif os.path.isfile(path):
            try:
                with open(path, 'r') as f: content = f.read()
                self.editor.setPlainText(content)
                self.current_file_path = path
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def create_new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            target_dir = QDir(self.root_path)
            if not target_dir.exists(folder_name): target_dir.mkdir(folder_name)

    def save_current_file(self):
        content = self.editor.toPlainText()
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save New File", self.root_path, "Web Files (*.html *.css *.js);;All Files (*)")
            if file_path: self.current_file_path = file_path
            else: return False 
        try:
            with open(self.current_file_path, 'w') as f: f.write(content)
            return True
        except: return False


# --- MAIN APPLICATION ---
class VPEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.setApplicationName("VPE")
        self.setWindowTitle("VPE - Vibe Programming Environment (Linux Mint)")
        self.resize(1300, 900)

        self.toolbar = QToolBar("Main Controls")
        self.addToolBar(self.toolbar)
        
        save_action = QAction("💾 Save Current Environment (Ctrl+S)", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_active_env)
        self.toolbar.addAction(save_action)

        screenshot_action = QAction("📸 Area Snip (to Gemini)", self)
        screenshot_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        screenshot_action.triggered.connect(self.trigger_screenshot)
        self.toolbar.addAction(screenshot_action)
        
        github_action = QAction("☁️ Sync Active Tab to GitHub", self)
        github_action.triggered.connect(self.trigger_github_backup)
        self.toolbar.addAction(github_action)

        self.tab_manager = QTabWidget()
        self.tab_manager.setStyleSheet("""
            QTabBar::tab { height: 35px; width: 160px; font-weight: bold; background: #2d2d2d; color: #8b9eb0;}
            QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-bottom: 2px solid #61afef; }
            QTabWidget::pane { border: none; }
        """)
        self.setCentralWidget(self.tab_manager)

        self.initialize_environments()

    def initialize_environments(self):
        python_env = PythonEnvironment(root_path=QDir.currentPath())
        self.tab_manager.addTab(python_env, "🐍 Python Vibe")
        
        web_env = WebEnvironment(root_path=QDir.currentPath())
        self.tab_manager.addTab(web_env, "🌐 Web Vibe")

    def trigger_screenshot(self):
        try:
            subprocess.Popen(["gnome-screenshot", "-a", "-c"])
            self.statusBar().showMessage("📸 Select an area to copy to your clipboard, then paste it into Gemini!", 6000)
        except FileNotFoundError:
            QMessageBox.warning(self, "Missing Dependency", "Linux Mint's 'gnome-screenshot' utility could not be found.")

    def save_active_env(self):
        current_env = self.tab_manager.currentWidget()
        if hasattr(current_env, 'save_current_file'):
            if current_env.save_current_file():
                if current_env.current_file_path:
                    self.statusBar().showMessage(f"Saved: {os.path.basename(current_env.current_file_path)}", 3000)

    def trigger_github_backup(self):
        current_env = self.tab_manager.currentWidget()
        if not hasattr(current_env, 'root_path'): return

        repo_dir = current_env.root_path

        if not os.path.exists(os.path.join(repo_dir, ".git")):
            reply = QMessageBox.question(self, "Initialize Git?", 
                                         "This folder is not currently a Git repository. Would you like VPE to initialize one now?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes: subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            else: return

        self.save_active_env()

        default_msg = f"VPE Auto-Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg, ok = QInputDialog.getText(self, "Git Sync", "Enter commit message:", text=default_msg)
        
        if ok and msg:
            try:
                subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True, capture_output=True)
                result = subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, capture_output=True, text=True)
                
                if "nothing to commit" in result.stdout:
                    QMessageBox.information(self, "Git Sync", "Working tree clean. No changes to commit.")
                    return
                
                push_result = subprocess.run(["git", "push"], cwd=repo_dir, capture_output=True, text=True)
                
                if push_result.returncode == 0: status = "✅ Success!\n\nChanges committed and pushed."
                else: status = "✅ Local Commit Successful!\n\n⚠️ Could not push to GitHub. Check terminal to run 'git push -u origin main'."
                    
                QMessageBox.information(self, "Sync Status", status)
                self.statusBar().showMessage("Git sync process finished.", 5000)

            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self, "Git Error", f"A Git command failed:\n{e.stderr}")


SPECIFIC_STYLESHEET = """
QTreeView QScrollBar:vertical, QPlainTextEdit QScrollBar:vertical {
    border: none; background: #1e1e1e; width: 14px;
}
QTreeView QScrollBar::handle:vertical, QPlainTextEdit QScrollBar::handle:vertical {
    background: #5c6370; min-height: 20px; border-radius: 7px;
}
QTreeView QScrollBar::handle:vertical:hover, QPlainTextEdit QScrollBar::handle:vertical:hover {
    background: #abb2bf;
}
QTreeView QScrollBar::add-line:vertical, QPlainTextEdit QScrollBar::add-line:vertical,
QTreeView QScrollBar::sub-line:vertical, QPlainTextEdit QScrollBar::sub-line:vertical {
    height: 0px; background: none;
}
QTreeView QScrollBar::add-page:vertical, QPlainTextEdit QScrollBar::add-page:vertical,
QTreeView QScrollBar::sub-page:vertical, QPlainTextEdit QScrollBar::sub-page:vertical {
    background: #282c34;
}
QTreeView QScrollBar:horizontal, QPlainTextEdit QScrollBar:horizontal {
    border: none; background: #1e1e1e; height: 14px;
}
QTreeView QScrollBar::handle:horizontal, QPlainTextEdit QScrollBar::handle:horizontal {
    background: #5c6370; min-width: 20px; border-radius: 7px;
}
QTreeView QScrollBar::handle:horizontal:hover, QPlainTextEdit QScrollBar::handle:horizontal:hover {
    background: #abb2bf;
}
QTreeView QScrollBar::add-line:horizontal, QPlainTextEdit QScrollBar::add-line:horizontal,
QTreeView QScrollBar::sub-line:horizontal, QPlainTextEdit QScrollBar::sub-line:horizontal {
    width: 0px; background: none;
}
QTreeView QScrollBar::add-page:horizontal, QPlainTextEdit QScrollBar::add-page:horizontal,
QTreeView QScrollBar::sub-page:horizontal, QPlainTextEdit QScrollBar::sub-page:horizontal {
    background: #282c34;
}
"""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(SPECIFIC_STYLESHEET)
    
    window = VPEWindow()
    window.show()
    sys.exit(app.exec())