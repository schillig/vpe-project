"""
Project: Vibe Programming Environment (VPE) - Build 0.58
Target OS: Linux Mint Only
Description: Clean Room Terminal Architecture + Automated Git Initialization & Shield Generation (Anti-Freeze Patch).
Architecture: PySide6 (Qt) with isolated QFileSystemModels per environment tab.
"""

import sys
import os

# --- SYSTEM PATCHES (Linux Mint Qt6 Fixes) ---
os.environ["QT_API"] = "pyside6"                                        
os.environ["QSG_RHI_BACKEND"] = "opengl"                                
os.environ["QT_LOGGING_RULES"] = "qt.accessibility.atspi.warning=false" 
# --------------------------------------------------------

import pty
import subprocess
import re
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, 
                             QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QTabWidget,
                             QPlainTextEdit, QToolBar, QMessageBox, QPushButton,
                             QFileSystemModel, QTreeView, QHeaderView, QMenu, QToolButton,
                             QInputDialog, QFileDialog, QLabel, QStyledItemDelegate)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSocketNotifier, QDir, QRegularExpression, QSize, Signal, QRect, QTimer, QUrl, QSettings
from PySide6.QtGui import (QAction, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, 
                           QColor, QPainter, QTextFormat, QDesktopServices, QTextCursor)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog

# --- GLOBAL SETTINGS & SANDBOX PATHS ---
DEV_DIR = os.path.expanduser("~/Development")
PYTHON_DEV_DIR = os.path.join(DEV_DIR, "Python")
WEB_DEV_DIR = os.path.join(DEV_DIR, "Web")

for d in [DEV_DIR, PYTHON_DEV_DIR, WEB_DEV_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

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
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
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
    ANSI_ESCAPE = re.compile(r'(?:\x1B\[[0-?]*[ -/]*[@-~])|(?:\x1B\].*?(?:\x07|\x1B\\))')

    def __init__(self, cwd=None):
        super().__init__()
        self.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc; font-family: 'Ubuntu Mono', 'Monospace'; font-size: 11pt; border: none;")
        self.master_fd, self.slave_fd = pty.openpty()
        
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        
        self.process = subprocess.Popen(
            ["/bin/bash"], 
            stdin=self.slave_fd, 
            stdout=self.slave_fd, 
            stderr=self.slave_fd, 
            preexec_fn=os.setsid, 
            env=env,
            cwd=cwd
        )
        
        self.notifier = QSocketNotifier(self.master_fd, QSocketNotifier.Read)
        self.notifier.activated.connect(self.read_shell_output)

    def read_shell_output(self):
        try:
            data = os.read(self.master_fd, 1024).decode(errors='ignore')
            clean_data = self.ANSI_ESCAPE.sub('', data).replace('\x07', '')
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

    def insertFromMimeData(self, source):
        if source.hasText():
            text = source.text()
            os.write(self.master_fd, text.encode())

    def send_command(self, command: str):
        if not command.endswith("\n"):
            command += "\n"
        os.write(self.master_fd, command.encode())


class RunFileDelegate(QStyledItemDelegate):
    run_requested = Signal(str)

    def __init__(self, env_type="python"):
        super().__init__()
        self.env_type = env_type

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        model = index.model()
        if hasattr(model, 'filePath'):
            path = model.filePath(index)
            is_py = path.endswith('.py')
            is_html = path.endswith('.html')
            
            should_paint = False
            if self.env_type == "python" and is_py:
                should_paint = True
            elif self.env_type == "web" and is_html:
                should_paint = True

            if os.path.isfile(path) and should_paint:
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
            is_py = path.endswith('.py')
            is_html = path.endswith('.html')
            
            should_run = False
            if self.env_type == "python" and is_py:
                should_run = True
            elif self.env_type == "web" and is_html:
                should_run = True

            if os.path.isfile(path) and should_run:
                rect = option.rect
                btn_rect = QRect(rect.right() - 32, rect.top() + (rect.height() - 20) // 2, 24, 20)
                if btn_rect.contains(event.position().toPoint()):
                    self.run_requested.emit(path)
                    return True 
        return super().editorEvent(event, model, option, index)


class BreadcrumbNavigation(QWidget):
    def __init__(self, navigation_callback, base_dir):
        super().__init__()
        self.navigation_callback = navigation_callback
        self.base_dir = base_dir
        self.furthest_path = base_dir
        
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

        relative_path = self.furthest_path.replace(self.base_dir, "")
        parts = [p for p in relative_path.split(os.sep) if p]
        
        base_name = os.path.basename(self.base_dir)
        root_btn = QPushButton(f"{base_name}/")
        root_btn.setCursor(Qt.PointingHandCursor)
        root_btn.setProperty("state", "active" if active_path == self.base_dir else "parent")
        root_btn.clicked.connect(lambda: self.navigation_callback(self.base_dir))
        self.layout.addWidget(root_btn)

        current_path = self.base_dir
        is_past_active = (active_path == self.base_dir)

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


class GitAwareFileSystemModel(QFileSystemModel):
    def __init__(self):
        super().__init__()
        self.git_statuses = {}
        self.repo_root = ""
        self.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)

    def set_repo_root(self, path):
        if not path or not os.path.exists(path): return
        try:
            res = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True, check=True)
            self.repo_root = res.stdout.strip()
        except subprocess.CalledProcessError:
            self.repo_root = path
        self.update_git_status()

    def update_git_status(self):
        if not self.repo_root or not os.path.exists(os.path.join(self.repo_root, ".git")):
            if self.git_statuses:
                self.git_statuses.clear()
                return True
            return False

        try:
            result = subprocess.run(["git", "status", "-s"], cwd=self.repo_root, capture_output=True, text=True)
            new_statuses = {}
            
            for line in result.stdout.splitlines():
                if len(line) < 3: continue
                status_code = line[:2]
                file_rel_path = line[3:].strip()
                
                if "->" in file_rel_path:
                    file_rel_path = file_rel_path.split("->")[-1].strip()
                file_rel_path = file_rel_path.strip('"')

                abs_path = os.path.abspath(os.path.join(self.repo_root, file_rel_path))

                if "??" in status_code or "A" in status_code:
                    new_statuses[abs_path] = "untracked"
                elif "M" in status_code or "D" in status_code or "R" in status_code or "C" in status_code:
                    new_statuses[abs_path] = "modified"

            folder_statuses = {}
            for fpath, state in new_statuses.items():
                parent = os.path.dirname(fpath)
                while parent.startswith(self.repo_root) and parent != self.repo_root:
                    folder_statuses[parent] = "modified"
                    parent = os.path.dirname(parent)

            combined = {**new_statuses, **folder_statuses}
            if self.git_statuses != combined:
                self.git_statuses = combined
                return True
        except Exception:
            pass
        return False

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.ForegroundRole:
            path = self.filePath(index)
            status = self.git_statuses.get(path)
            if status == "untracked":
                return QColor("#98c379")
            elif status == "modified":
                return QColor("#e5c07b")
            return QColor("#abb2bf")
        return super().data(index, role)


# --- ISOLATED ENVIRONMENTS ---
class PythonEnvironment(QWidget):
    def __init__(self, root_path: str):
        super().__init__()
        self.current_file_path = None
        self.base_dir = PYTHON_DEV_DIR 
        self.root_path = root_path
        self.last_search_term = "" 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)
        
        self.sidebar_toolbar = QToolBar()
        self.sidebar_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; }
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
            QMenu { background-color: #282c34; color: #abb2bf; border: 1px solid #181a1f; }
            QMenu::item { padding: 6px 20px; font-weight: bold; }
            QMenu::item:selected { background-color: #3e4451; color: #ffffff; }
        """)

        self.workspace_menu_btn = QToolButton(self)
        self.workspace_menu_btn.setText("🗂️ Workspace")
        self.workspace_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.workspace_menu = QMenu(self.workspace_menu_btn)
        
        action_new_proj = self.workspace_menu.addAction("📁 Create New Project")
        action_new_proj.triggered.connect(self.create_new_folder)

        action_init_git = self.workspace_menu.addAction("🛠️ Initialize Git Repo")
        action_init_git.triggered.connect(self.initialize_git_repo)
        
        self.workspace_menu.addSeparator()
        
        action_show_hidden = self.workspace_menu.addAction("👁️ Show Hidden Files")
        action_show_hidden.setCheckable(True)
        action_show_hidden.triggered.connect(self.toggle_hidden_files)
        
        self.workspace_menu_btn.setMenu(self.workspace_menu)
        self.sidebar_toolbar.addWidget(self.workspace_menu_btn)
        
        self.sidebar_layout.addWidget(self.sidebar_toolbar)

        self.breadcrumb = BreadcrumbNavigation(self.change_workspace, base_dir=self.base_dir) 
        self.sidebar_layout.addWidget(self.breadcrumb)

        self.file_model = GitAwareFileSystemModel()
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True) 
        self.tree.setIconSize(QSize(32, 32))
        
        self.run_delegate = RunFileDelegate(env_type="python")
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

        self.git_timer = QTimer(self)
        self.git_timer.timeout.connect(self.update_git_and_redraw)
        self.git_timer.start(2000)

        self.edit_term_splitter = QSplitter(Qt.Vertical)
        
        self.editor_container = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_container)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(0)

        self.editor_toolbar = QToolBar()
        self.editor_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; }
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
            QMenu { background-color: #282c34; color: #abb2bf; border: 1px solid #181a1f; }
            QMenu::item { padding: 6px 20px; font-weight: bold; }
            QMenu::item:selected { background-color: #3e4451; color: #ffffff; }
        """)

        self.file_menu_btn = QToolButton(self)
        self.file_menu_btn.setText("📄 File")
        self.file_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.file_menu = QMenu(self.file_menu_btn)
        action_open = self.file_menu.addAction("📂 Open File")
        action_open.triggered.connect(self.action_file_open)
        action_save = self.file_menu.addAction("💾 Save")
        action_save.triggered.connect(self.save_current_file)
        action_save_as = self.file_menu.addAction("📝 Save As...")
        action_save_as.triggered.connect(self.action_file_save_as)
        self.file_menu.addSeparator()
        action_print_preview = self.file_menu.addAction("🔍 Print Preview")
        action_print_preview.triggered.connect(self.action_file_print_preview)
        action_print = self.file_menu.addAction("🖨️ Print")
        action_print.triggered.connect(self.action_file_print)
        self.file_menu_btn.setMenu(self.file_menu)
        self.editor_toolbar.addWidget(self.file_menu_btn)
        
        self.edit_menu_btn = QToolButton(self)
        self.edit_menu_btn.setText("✏️ Edit")
        self.edit_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.edit_menu = QMenu(self.edit_menu_btn)
        action_undo = self.edit_menu.addAction("↩️ Undo")
        action_undo.triggered.connect(lambda: self.editor.undo())
        action_redo = self.edit_menu.addAction("↪️ Redo")
        action_redo.triggered.connect(lambda: self.editor.redo())
        self.edit_menu.addSeparator()
        action_cut = self.edit_menu.addAction("✂️ Cut")
        action_cut.triggered.connect(lambda: self.editor.cut())
        action_copy = self.edit_menu.addAction("📋 Copy")
        action_copy.triggered.connect(lambda: self.editor.copy())
        action_paste = self.edit_menu.addAction("📥 Paste")
        action_paste.triggered.connect(lambda: self.editor.paste())
        action_delete = self.edit_menu.addAction("🗑️ Delete")
        action_delete.triggered.connect(self.action_edit_delete)
        self.edit_menu.addSeparator()
        action_select_all = self.edit_menu.addAction("☑️ Select All")
        action_select_all.triggered.connect(lambda: self.editor.selectAll())
        self.edit_menu_btn.setMenu(self.edit_menu)
        self.editor_toolbar.addWidget(self.edit_menu_btn)

        self.search_menu_btn = QToolButton(self)
        self.search_menu_btn.setText("🔍 Search")
        self.search_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.search_menu = QMenu(self.search_menu_btn)
        action_find = self.search_menu.addAction("🔎 Find...")
        action_find.triggered.connect(self.action_search_find)
        action_find_next = self.search_menu.addAction("⏩ Find Next")
        action_find_next.triggered.connect(self.action_search_find_next)
        action_replace = self.search_menu.addAction("🔄 Replace...")
        action_replace.triggered.connect(self.action_search_replace)
        self.search_menu_btn.setMenu(self.search_menu)
        self.editor_toolbar.addWidget(self.search_menu_btn)

        self.commit_code_btn = QAction("📋 Commit Code", self)
        self.commit_code_btn.triggered.connect(self.commit_code_from_clipboard)
        self.editor_toolbar.addAction(self.commit_code_btn)

        self.undo_commit_btn = QAction("↩️ Undo Commit", self)
        self.undo_commit_btn.triggered.connect(self.undo_commit_and_save)
        self.editor_toolbar.addAction(self.undo_commit_btn)

        self.editor_layout.addWidget(self.editor_toolbar)

        self.editor = CodeEditor()
        self.editor.setStyleSheet("QPlainTextEdit { background-color: #282c34; color: #abb2bf; border: none; }")
        self.editor.document().setDocumentMargin(10) 
        font = QFont("Ubuntu Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("# Start typing, then hit Ctrl+S to save...\n# Or copy text from your browser and click '📋 Commit Code'.")
        
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor_layout.addWidget(self.editor)

        self.terminal_container = QWidget()
        self.terminal_layout = QVBoxLayout(self.terminal_container)
        self.terminal_layout.setContentsMargins(0, 0, 0, 0)
        self.terminal_layout.setSpacing(0)

        self.terminal_toolbar = QToolBar()
        self.terminal_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; border-top: 1px solid #181a1f;}
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
        """)

        self.copy_log_btn = QAction("📝 Copy Log", self)
        self.copy_log_btn.triggered.connect(self.copy_terminal_log)
        self.terminal_toolbar.addAction(self.copy_log_btn)

        self.venv_btn = QAction("📦 Build venv", self)
        self.venv_btn.triggered.connect(self.setup_venv)
        self.terminal_toolbar.addAction(self.venv_btn)

        self.venv_toggle_btn = QAction("🟢 Start venv", self)
        self.venv_toggle_btn.triggered.connect(self.toggle_venv)
        self.terminal_toolbar.addAction(self.venv_toggle_btn)

        self.make_app_btn = QAction("🚀 Make App", self)
        self.make_app_btn.triggered.connect(self.create_desktop_shortcut)
        self.terminal_toolbar.addAction(self.make_app_btn)

        self.terminal_layout.addWidget(self.terminal_toolbar)

        self.terminal = NativeLinuxTerminal(cwd=self.root_path)
        self.terminal_layout.addWidget(self.terminal)

        self.edit_term_splitter.addWidget(self.editor_container)
        self.edit_term_splitter.addWidget(self.terminal_container) 
        self.edit_term_splitter.setSizes([600, 300])
        
        self.workspace_splitter.addWidget(self.sidebar_container)
        self.workspace_splitter.addWidget(self.edit_term_splitter)
        self.workspace_splitter.setSizes([250, 1000])
        
        layout.addWidget(self.workspace_splitter)

        self.auto_open_main_file()

    def auto_open_main_file(self):
        target_file = None
        for pref in ["main.py", "app.py", "vpe_main.py"]:
            temp = os.path.join(self.root_path, pref)
            if os.path.isfile(temp):
                target_file = temp
                break
        
        if not target_file:
            try:
                for f in os.listdir(self.root_path):
                    if f.endswith('.py') and os.path.isfile(os.path.join(self.root_path, f)):
                        target_file = os.path.join(self.root_path, f)
                        break
            except Exception: pass
        
        if target_file:
            try:
                with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                    self.editor.setPlainText(f.read())
                self.current_file_path = target_file
                self.editor.document().setModified(False)
            except Exception: pass

    def action_search_find(self):
        text, ok = QInputDialog.getText(self, "Find", "Find what:", text=self.last_search_term)
        if ok and text:
            self.last_search_term = text
            if not self.editor.find(text):
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.Start)
                self.editor.setTextCursor(cursor)
                if not self.editor.find(text):
                    QMessageBox.information(self, "Find", f"Cannot find '{text}'")

    def action_search_find_next(self):
        if self.last_search_term:
            if not self.editor.find(self.last_search_term):
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.Start)
                self.editor.setTextCursor(cursor)
                if not self.editor.find(self.last_search_term):
                    QMessageBox.information(self, "Find", f"Cannot find '{self.last_search_term}'")
        else:
            self.action_search_find()

    def action_search_replace(self):
        find_text, ok1 = QInputDialog.getText(self, "Replace", "Find what:", text=self.last_search_term)
        if not (ok1 and find_text): return
        self.last_search_term = find_text
        
        replace_text, ok2 = QInputDialog.getText(self, "Replace", "Replace with:")
        if not ok2: return

        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            
        self.action_search_find_next()

    def action_edit_delete(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        self.editor.setTextCursor(cursor)

    def action_file_open(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", self.root_path, "Python Files (*.py);;All Files (*)")
        if file_path:
            if not self.check_unsaved_changes(): return
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.editor.setPlainText(f.read())
                self.current_file_path = file_path
                self.editor.document().setModified(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def action_file_save_as(self):
        old_path = self.current_file_path
        self.current_file_path = None
        if not self.save_current_file():
            self.current_file_path = old_path

    def action_file_print_preview(self):
        printer = QPrinter()
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self.editor.print_)
        preview.exec()

    def action_file_print(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.Accepted:
            self.editor.print_(printer)

    def create_desktop_shortcut(self):
        if not self.current_file_path or not self.current_file_path.endswith('.py'):
            QMessageBox.warning(self, "No Python File", "Please open and save a Python (.py) file first before creating an app shortcut.")
            return
            
        default_name = os.path.splitext(os.path.basename(self.current_file_path))[0].replace("_", " ").title()
        app_name, ok = QInputDialog.getText(self, "Make App", "Enter the name for your Linux Mint Start Menu shortcut:", text=default_name)
        
        if ok and app_name:
            venv_python = os.path.join(self.root_path, ".venv", "bin", "python")
            if os.path.exists(venv_python):
                exec_cmd = f"'{venv_python}' '{self.current_file_path}'"
            else:
                exec_cmd = f"python3 '{self.current_file_path}'"
                
            reply = QMessageBox.question(self, "Terminal Option", 
                                         "Does this app have a graphical window (GUI)?\n\nChoose 'Yes' for visual apps (hides terminal).\nChoose 'No' for command-line apps.",
                                         QMessageBox.Yes | QMessageBox.No)
            terminal_val = "false" if reply == QMessageBox.Yes else "true"
            
            safe_filename = "".join(c for c in app_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_').lower()
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)
            desktop_path = os.path.join(desktop_dir, f"{safe_filename}.desktop")
            
            desktop_entry = f"""[Desktop Entry]
Version=1.0
Name={app_name}
Comment=Created with VPE
Exec={exec_cmd}
Icon=python
Terminal={terminal_val}
Type=Application
Categories=Development;
"""
            try:
                with open(desktop_path, 'w') as f:
                    f.write(desktop_entry)
                
                os.chmod(desktop_path, 0o755)
                subprocess.run(["update-desktop-database", desktop_dir])
                
                QMessageBox.information(self, "Success!", f"'{app_name}' has been compiled and added to your Linux Mint Start Menu!\n\nOpen your menu and search for it to launch.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create app shortcut:\n{e}")

    def toggle_venv(self):
        if "Start" in self.venv_toggle_btn.text():
            venv_path = os.path.join(self.root_path, ".venv")
            if not os.path.exists(venv_path):
                QMessageBox.warning(self, "No venv", "No virtual environment found.\nPlease click '📦 Build venv' first.")
                return
            self.terminal.send_command(f"cd '{self.root_path}' && source .venv/bin/activate\n")
            self.venv_toggle_btn.setText("🔴 Stop venv")
        else:
            self.terminal.send_command("deactivate\n")
            self.venv_toggle_btn.setText("🟢 Start venv")

    def toggle_hidden_files(self, checked):
        filters = QDir.AllEntries | QDir.NoDotAndDotDot
        if checked:
            filters |= QDir.Hidden
        self.file_model.setFilter(filters)

    def check_unsaved_changes(self):
        if hasattr(self, 'editor') and self.editor.document().isModified():
            filename = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{filename}' has unsaved changes.\nDo you want to save them before proceeding?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                return self.save_current_file()
            elif reply == QMessageBox.Cancel:
                return False
        return True

    def change_workspace(self, path):
        if path == self.root_path: return
        if not self.check_unsaved_changes(): return
        self.set_workspace_root(path)
        self.editor.clear()
        self.current_file_path = None
        self.editor.document().setModified(False)
        self.venv_toggle_btn.setText("🟢 Start venv") 
        
        self.terminal.deleteLater()
        self.terminal = NativeLinuxTerminal(cwd=self.root_path)
        self.terminal_layout.addWidget(self.terminal)
        
        self.auto_open_main_file()

    def setup_venv(self):
        venv_path = os.path.join(self.root_path, ".venv")
        if os.path.exists(venv_path):
            reply = QMessageBox.question(self, "Virtual Environment Exists", 
                                         "A .venv folder is already here.\n\nDo you want to Nuke & Rebuild it?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._create_and_populate_venv(nuke=True)
            else:
                self.terminal.clear()
                self.terminal.send_command(f"cd '{self.root_path}' && source .venv/bin/activate\n")
                self.venv_toggle_btn.setText("🔴 Stop venv") 
        else:
            self._create_and_populate_venv(nuke=False)

    def _create_and_populate_venv(self, nuke=False):
        self.terminal.clear()
        cmd = f"cd '{self.root_path}' && "
        if nuke: cmd += "rm -rf .venv && "
        req_path = os.path.join(self.root_path, "requirements.txt")
        if os.path.exists(req_path):
            cmd += "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt\n"
        else:
            cmd += "python3 -m venv .venv && source .venv/bin/activate\n"
        self.terminal.send_command(cmd)
        self.venv_toggle_btn.setText("🔴 Stop venv") 

    def update_git_and_redraw(self):
        if self.file_model.update_git_status():
            self.tree.viewport().update()

    def execute_script(self, file_path):
        if self.current_file_path == file_path:
            self.save_current_file()
        working_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        if file_path.endswith('.py'):
            self.terminal.clear()
            venv_python = os.path.join(self.root_path, ".venv", "bin", "python")
            if os.path.exists(venv_python):
                cmd = f"cd '{working_dir}' && '{venv_python}' '{file_name}'"
            else:
                cmd = f"cd '{working_dir}' && python3 '{file_name}'"
            self.terminal.send_command(cmd + "\n")

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

    def copy_terminal_log(self):
        log_text = self.terminal.toPlainText()
        if log_text.strip():
            QApplication.clipboard().setText(log_text)
            self.copy_log_btn.setText("✅ Log Copied!")
            QTimer.singleShot(2000, lambda: self.copy_log_btn.setText("📝 Copy Log"))
        else:
            QMessageBox.information(self, "Empty Log", "The terminal is empty.")

    def set_workspace_root(self, path):
        if os.path.isdir(path):
            self.root_path = path
            self.file_model.setRootPath(self.root_path)
            self.tree.setRootIndex(self.file_model.index(self.root_path))
            self.file_model.set_repo_root(self.root_path)
            self.breadcrumb.build_path(self.root_path)
            self.update_git_and_redraw()

    def open_workspace_dialog(self):
        start_dir = self.root_path if self.root_path.startswith(self.base_dir) else self.base_dir
        dir_path = QFileDialog.getExistingDirectory(self, "Select Python Workspace", start_dir)
        if dir_path: 
            if not dir_path.startswith(self.base_dir):
                QMessageBox.warning(self, "Sandbox Violation", f"Python projects must be located within:\n{self.base_dir}")
                return
            self.change_workspace(dir_path)

    def handle_tree_double_click(self, index):
        path = self.file_model.filePath(index)
        if os.path.isdir(path):
            self.change_workspace(path)
        elif os.path.isfile(path):
            allowed_exts = ('.py', '.txt', '.md', '.json', '.csv', '.dat', '.db', '.sqlite', '.ini')
            if '.' in os.path.basename(path) and not path.lower().endswith(allowed_exts):
                QMessageBox.warning(self, "Environment Lockout", 
                                  f"The Python Vibe tab is restricted to backend and data files.\n\nPlease open frontend files (like {os.path.basename(path)}) in the Web Vibe tab.")
                return

            if path == self.current_file_path: return
            if not self.check_unsaved_changes(): return
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
                self.editor.setPlainText(content)
                self.current_file_path = path
                self.editor.document().setModified(False) 
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def create_new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if ok and folder_name:
            target_dir = QDir(self.root_path)
            if not target_dir.exists(folder_name): target_dir.mkdir(folder_name)

    def initialize_git_repo(self):
        git_path = os.path.join(self.root_path, ".git")
        if os.path.exists(git_path):
            QMessageBox.information(self, "Git", "This workspace is already a Git repository!")
            return

        reply = QMessageBox.question(self, "Initialize Git?", 
                                     f"Do you want to initialize a new Git repository in:\n{os.path.basename(self.root_path)}?\n\n(This will also auto-generate a protective .gitignore shield)",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # PAUSE TIMER to prevent PySide thread from locking while git indexes the file system
                self.git_timer.stop()
                
                # Write shield first
                subprocess.run(["git", "init"], cwd=self.root_path, check=True, capture_output=True)
                
                gitignore_path = os.path.join(self.root_path, ".gitignore")
                if not os.path.exists(gitignore_path):
                    with open(gitignore_path, "w") as f:
                        f.write(".venv/\nvenv/\n__pycache__/\n.buildozer/\n")
                
                # Update UI
                self.file_model.set_repo_root(self.root_path)
                self.update_git_and_redraw()
                
                # Restart TIMER
                self.git_timer.start(2000)
                
                QMessageBox.information(self, "Success", "✅ Git repository initialized!\n✅ Protective .gitignore shield generated.")
                
            except Exception as e:
                self.git_timer.start(2000)
                QMessageBox.critical(self, "Error", f"Could not initialize Git:\n{e}")

    def save_current_file(self):
        content = self.editor.toPlainText()
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save New File", self.root_path, "Python Files (*.py);;All Files (*)")
            if file_path: self.current_file_path = file_path
            else: return False 
        try:
            with open(self.current_file_path, 'w') as f: f.write(content)
            self.editor.document().setModified(False)
            self.update_git_and_redraw()
            return True
        except: return False


class WebEnvironment(QWidget):
    def __init__(self, root_path: str):
        super().__init__()
        self.current_file_path = None
        self.base_dir = WEB_DEV_DIR 
        self.root_path = root_path
        self.last_search_term = "" 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)
        
        self.sidebar_toolbar = QToolBar()
        self.sidebar_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; }
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
            QMenu { background-color: #282c34; color: #abb2bf; border: 1px solid #181a1f; }
            QMenu::item { padding: 6px 20px; font-weight: bold; }
            QMenu::item:selected { background-color: #3e4451; color: #ffffff; }
        """)

        self.workspace_menu_btn = QToolButton(self)
        self.workspace_menu_btn.setText("🗂️ Workspace")
        self.workspace_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.workspace_menu = QMenu(self.workspace_menu_btn)
        
        action_new_proj = self.workspace_menu.addAction("📁 Create New Project")
        action_new_proj.triggered.connect(self.create_new_folder)

        action_init_git = self.workspace_menu.addAction("🛠️ Initialize Git Repo")
        action_init_git.triggered.connect(self.initialize_git_repo)
        
        self.workspace_menu.addSeparator()
        
        action_show_hidden = self.workspace_menu.addAction("👁️ Show Hidden Files")
        action_show_hidden.setCheckable(True)
        action_show_hidden.triggered.connect(self.toggle_hidden_files)
        
        self.workspace_menu_btn.setMenu(self.workspace_menu)
        self.sidebar_toolbar.addWidget(self.workspace_menu_btn)
        
        self.sidebar_layout.addWidget(self.sidebar_toolbar)

        self.breadcrumb = BreadcrumbNavigation(self.change_workspace, base_dir=self.base_dir) 
        self.sidebar_layout.addWidget(self.breadcrumb)

        self.file_model = GitAwareFileSystemModel()
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True) 
        self.tree.setIconSize(QSize(32, 32))
        
        self.run_delegate = RunFileDelegate(env_type="web")
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

        self.git_timer = QTimer(self)
        self.git_timer.timeout.connect(self.update_git_and_redraw)
        self.git_timer.start(2000)

        self.edit_term_splitter = QSplitter(Qt.Vertical)
        
        self.editor_container = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_container)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(0)

        self.editor_toolbar = QToolBar()
        self.editor_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; }
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
            QMenu { background-color: #282c34; color: #abb2bf; border: 1px solid #181a1f; }
            QMenu::item { padding: 6px 20px; font-weight: bold; }
            QMenu::item:selected { background-color: #3e4451; color: #ffffff; }
        """)

        self.file_menu_btn = QToolButton(self)
        self.file_menu_btn.setText("📄 File")
        self.file_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.file_menu = QMenu(self.file_menu_btn)
        action_open = self.file_menu.addAction("📂 Open File")
        action_open.triggered.connect(self.action_file_open)
        action_save = self.file_menu.addAction("💾 Save")
        action_save.triggered.connect(self.save_current_file)
        action_save_as = self.file_menu.addAction("📝 Save As...")
        action_save_as.triggered.connect(self.action_file_save_as)
        self.file_menu.addSeparator()
        action_print_preview = self.file_menu.addAction("🔍 Print Preview")
        action_print_preview.triggered.connect(self.action_file_print_preview)
        action_print = self.file_menu.addAction("🖨️ Print")
        action_print.triggered.connect(self.action_file_print)
        self.file_menu_btn.setMenu(self.file_menu)
        self.editor_toolbar.addWidget(self.file_menu_btn)
        
        self.edit_menu_btn = QToolButton(self)
        self.edit_menu_btn.setText("✏️ Edit")
        self.edit_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.edit_menu = QMenu(self.edit_menu_btn)
        action_undo = self.edit_menu.addAction("↩️ Undo")
        action_undo.triggered.connect(lambda: self.editor.undo())
        action_redo = self.edit_menu.addAction("↪️ Redo")
        action_redo.triggered.connect(lambda: self.editor.redo())
        self.edit_menu.addSeparator()
        action_cut = self.edit_menu.addAction("✂️ Cut")
        action_cut.triggered.connect(lambda: self.editor.cut())
        action_copy = self.edit_menu.addAction("📋 Copy")
        action_copy.triggered.connect(lambda: self.editor.copy())
        action_paste = self.edit_menu.addAction("📥 Paste")
        action_paste.triggered.connect(lambda: self.editor.paste())
        action_delete = self.edit_menu.addAction("🗑️ Delete")
        action_delete.triggered.connect(self.action_edit_delete)
        self.edit_menu.addSeparator()
        action_select_all = self.edit_menu.addAction("☑️ Select All")
        action_select_all.triggered.connect(lambda: self.editor.selectAll())
        self.edit_menu_btn.setMenu(self.edit_menu)
        self.editor_toolbar.addWidget(self.edit_menu_btn)

        self.search_menu_btn = QToolButton(self)
        self.search_menu_btn.setText("🔍 Search")
        self.search_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.search_menu = QMenu(self.search_menu_btn)
        action_find = self.search_menu.addAction("🔎 Find...")
        action_find.triggered.connect(self.action_search_find)
        action_find_next = self.search_menu.addAction("⏩ Find Next")
        action_find_next.triggered.connect(self.action_search_find_next)
        action_replace = self.search_menu.addAction("🔄 Replace...")
        action_replace.triggered.connect(self.action_search_replace)
        self.search_menu_btn.setMenu(self.search_menu)
        self.editor_toolbar.addWidget(self.search_menu_btn)

        self.commit_code_btn = QAction("📋 Commit Code", self)
        self.commit_code_btn.triggered.connect(self.commit_code_from_clipboard)
        self.editor_toolbar.addAction(self.commit_code_btn)

        self.undo_commit_btn = QAction("↩️ Undo Commit", self)
        self.undo_commit_btn.triggered.connect(self.undo_commit_and_save)
        self.editor_toolbar.addAction(self.undo_commit_btn)

        self.editor_layout.addWidget(self.editor_toolbar)

        self.editor = CodeEditor()
        self.editor.setStyleSheet("QPlainTextEdit { background-color: #282c34; color: #abb2bf; border: none; }")
        self.editor.document().setDocumentMargin(10)
        font = QFont("Ubuntu Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("\n<h1>Hello Web Vibe!</h1>")
        self.highlighter = WebHighlighter(self.editor.document())
        self.editor_layout.addWidget(self.editor)
        
        self.terminal_container = QWidget()
        self.terminal_layout = QVBoxLayout(self.terminal_container)
        self.terminal_layout.setContentsMargins(0, 0, 0, 0)
        self.terminal_layout.setSpacing(0)

        self.terminal_toolbar = QToolBar()
        self.terminal_toolbar.setStyleSheet("""
            QToolBar { background-color: #282c34; border: none; padding: 4px; border-top: 1px solid #181a1f;}
            QToolButton { font-size: 11pt; font-weight: bold; padding: 6px 12px; color: #abb2bf; border-radius: 4px; }
            QToolButton:hover { background-color: #3e4451; color: #ffffff; }
        """)

        self.copy_log_btn = QAction("📝 Copy Log", self)
        self.copy_log_btn.triggered.connect(self.copy_terminal_log)
        self.terminal_toolbar.addAction(self.copy_log_btn)

        self.terminal_layout.addWidget(self.terminal_toolbar)

        self.terminal = NativeLinuxTerminal(cwd=self.root_path)
        self.terminal_layout.addWidget(self.terminal)

        self.edit_term_splitter.addWidget(self.editor_container)
        self.edit_term_splitter.addWidget(self.terminal_container)
        self.edit_term_splitter.setSizes([500, 200])

        self.preview_view = QWebEngineView()
        self.preview_view.setStyleSheet("background-color: #ffffff;")
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.update_live_preview)
        self.editor.textChanged.connect(lambda: self.render_timer.start(500))

        self.workspace_splitter.addWidget(self.sidebar_container)
        self.workspace_splitter.addWidget(self.edit_term_splitter)
        self.workspace_splitter.addWidget(self.preview_view)
        
        self.workspace_splitter.setSizes([200, 500, 500]) 
        layout.addWidget(self.workspace_splitter)
        self.update_live_preview()
        
        self.auto_open_main_file()

    def auto_open_main_file(self):
        target_file = None
        for pref in ["index.html", "main.html"]:
            temp = os.path.join(self.root_path, pref)
            if os.path.isfile(temp):
                target_file = temp
                break
        
        if not target_file:
            try:
                for f in os.listdir(self.root_path):
                    if f.endswith('.html') and os.path.isfile(os.path.join(self.root_path, f)):
                        target_file = os.path.join(self.root_path, f)
                        break
            except Exception: pass
            
        if target_file:
            try:
                with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                    self.editor.setPlainText(f.read())
                self.current_file_path = target_file
                self.editor.document().setModified(False)
            except Exception: pass

    def action_search_find(self):
        text, ok = QInputDialog.getText(self, "Find", "Find what:", text=self.last_search_term)
        if ok and text:
            self.last_search_term = text
            if not self.editor.find(text):
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.Start)
                self.editor.setTextCursor(cursor)
                if not self.editor.find(text):
                    QMessageBox.information(self, "Find", f"Cannot find '{text}'")

    def action_search_find_next(self):
        if self.last_search_term:
            if not self.editor.find(self.last_search_term):
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.Start)
                self.editor.setTextCursor(cursor)
                if not self.editor.find(self.last_search_term):
                    QMessageBox.information(self, "Find", f"Cannot find '{self.last_search_term}'")
        else:
            self.action_search_find()

    def action_search_replace(self):
        find_text, ok1 = QInputDialog.getText(self, "Replace", "Find what:", text=self.last_search_term)
        if not (ok1 and find_text): return
        self.last_search_term = find_text
        
        replace_text, ok2 = QInputDialog.getText(self, "Replace", "Replace with:")
        if not ok2: return

        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            
        self.action_search_find_next()

    def action_edit_delete(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        self.editor.setTextCursor(cursor)

    def action_file_open(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", self.root_path, "Web Files (*.html *.css *.js);;All Files (*)")
        if file_path:
            if not self.check_unsaved_changes(): return
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.editor.setPlainText(f.read())
                self.current_file_path = file_path
                self.editor.document().setModified(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def action_file_save_as(self):
        old_path = self.current_file_path
        self.current_file_path = None
        if not self.save_current_file():
            self.current_file_path = old_path

    def action_file_print_preview(self):
        printer = QPrinter()
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self.editor.print_)
        preview.exec()

    def action_file_print(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.Accepted:
            self.editor.print_(printer)

    def toggle_hidden_files(self, checked):
        filters = QDir.AllEntries | QDir.NoDotAndDotDot
        if checked:
            filters |= QDir.Hidden
        self.file_model.setFilter(filters)

    def check_unsaved_changes(self):
        if hasattr(self, 'editor') and self.editor.document().isModified():
            filename = os.path.basename(self.current_file_path) if self.current_file_path else "Untitled"
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{filename}' has unsaved changes.\nDo you want to save them before proceeding?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                return self.save_current_file()
            elif reply == QMessageBox.Cancel:
                return False
        return True

    def change_workspace(self, path):
        if path == self.root_path: return
        if not self.check_unsaved_changes(): return
        self.set_workspace_root(path)
        self.editor.clear()
        self.current_file_path = None
        self.editor.document().setModified(False)
        
        self.terminal.deleteLater()
        self.terminal = NativeLinuxTerminal(cwd=self.root_path)
        self.terminal_layout.addWidget(self.terminal)
        
        self.auto_open_main_file()

    def update_git_and_redraw(self):
        if self.file_model.update_git_status():
            self.tree.viewport().update()

    def execute_script(self, file_path):
        if self.current_file_path == file_path:
            self.save_current_file()
        working_dir = os.path.dirname(file_path)
        if file_path.endswith('.html'):
            self.terminal.clear()
            abs_path = os.path.abspath(file_path)
            file_uri = f"file://{abs_path}"
            cmd = (f"cd '{working_dir}' && "
                   f"if command -v google-chrome > /dev/null; then google-chrome --app='{file_uri}'; "
                   f"elif command -v brave-browser > /dev/null; then brave-browser --app='{file_uri}'; "
                   f"elif command -v firefox > /dev/null; then firefox --new-window '{file_uri}'; "
                   f"else xdg-open '{file_uri}'; fi")
            self.terminal.send_command(cmd + "\n")

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

    def copy_terminal_log(self):
        log_text = self.terminal.toPlainText()
        if log_text.strip():
            QApplication.clipboard().setText(log_text)
            self.copy_log_btn.setText("✅ Log Copied!")
            QTimer.singleShot(2000, lambda: self.copy_log_btn.setText("📝 Copy Log"))
        else:
            QMessageBox.information(self, "Empty Log", "The terminal is empty.")

    def set_workspace_root(self, path):
        if os.path.isdir(path):
            self.root_path = path
            self.file_model.setRootPath(self.root_path)
            self.tree.setRootIndex(self.file_model.index(self.root_path))
            self.file_model.set_repo_root(self.root_path)
            self.breadcrumb.build_path(self.root_path)
            self.update_git_and_redraw()

    def open_workspace_dialog(self):
        start_dir = self.root_path if self.root_path.startswith(self.base_dir) else self.base_dir
        dir_path = QFileDialog.getExistingDirectory(self, "Select Web Workspace", start_dir)
        if dir_path: 
            if not dir_path.startswith(self.base_dir):
                QMessageBox.warning(self, "Sandbox Violation", f"Web projects must be located within:\n{self.base_dir}")
                return
            self.change_workspace(dir_path)

    def handle_tree_double_click(self, index):
        path = self.file_model.filePath(index)
        if os.path.isdir(path):
            self.change_workspace(path)
        elif os.path.isfile(path):
            allowed_exts = ('.html', '.css', '.js', '.json', '.md', '.txt')
            if '.' in os.path.basename(path) and not path.lower().endswith(allowed_exts):
                QMessageBox.warning(self, "Environment Lockout", 
                                  f"The Web Vibe tab is restricted to frontend files.\n\nPlease open backend files (like {os.path.basename(path)}) in the Python Vibe tab.")
                return

            if path == self.current_file_path: return
            if not self.check_unsaved_changes(): return
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
                self.editor.setPlainText(content)
                self.current_file_path = path
                self.editor.document().setModified(False) 
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def create_new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if ok and folder_name:
            target_dir = QDir(self.root_path)
            if not target_dir.exists(folder_name): target_dir.mkdir(folder_name)

    def initialize_git_repo(self):
        git_path = os.path.join(self.root_path, ".git")
        if os.path.exists(git_path):
            QMessageBox.information(self, "Git", "This workspace is already a Git repository!")
            return

        reply = QMessageBox.question(self, "Initialize Git?", 
                                     f"Do you want to initialize a new Git repository in:\n{os.path.basename(self.root_path)}?\n\n(This will also auto-generate a protective .gitignore shield)",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # PAUSE TIMER to prevent PySide thread from locking while git indexes the file system
                self.git_timer.stop()
                
                # Write shield first
                subprocess.run(["git", "init"], cwd=self.root_path, check=True, capture_output=True)
                
                gitignore_path = os.path.join(self.root_path, ".gitignore")
                if not os.path.exists(gitignore_path):
                    with open(gitignore_path, "w") as f:
                        f.write(".venv/\nvenv/\n__pycache__/\n.buildozer/\n")
                
                # Update UI
                self.file_model.set_repo_root(self.root_path)
                self.update_git_and_redraw()
                
                # Restart TIMER
                self.git_timer.start(2000)
                
                QMessageBox.information(self, "Success", "✅ Git repository initialized!\n✅ Protective .gitignore shield generated.")
                
            except Exception as e:
                self.git_timer.start(2000)
                QMessageBox.critical(self, "Error", f"Could not initialize Git:\n{e}")

    def save_current_file(self):
        content = self.editor.toPlainText()
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save New File", self.root_path, "Web Files (*.html *.css *.js);;All Files (*)")
            if file_path: self.current_file_path = file_path
            else: return False 
        try:
            with open(self.current_file_path, 'w') as f: f.write(content)
            self.editor.document().setModified(False)
            self.update_git_and_redraw()
            return True
        except: return False


# --- MAIN APPLICATION ---
class VPEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.setApplicationName("VPE")
        self.setWindowTitle("VPE - Vibe Programming Environment (Linux Mint)")
        self.resize(1300, 900)
        
        self.settings = QSettings("VibeCorp", "VPE_IDE")

        self.toolbar = QToolBar("Main Controls")
        self.addToolBar(self.toolbar)
        
        save_action = QAction("💾 Save Env (Ctrl+S)", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_active_env)
        self.toolbar.addAction(save_action)

        screenshot_action = QAction("📸 Area Snip", self)
        screenshot_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        screenshot_action.triggered.connect(self.trigger_screenshot)
        self.toolbar.addAction(screenshot_action)
        
        tree_action = QAction("🌲 Copy Tree", self)
        tree_action.triggered.connect(self.copy_project_tree)
        self.toolbar.addAction(tree_action)
        
        git_pull_action = QAction("📥 Git Pull", self)
        git_pull_action.triggered.connect(self.trigger_github_pull)
        self.toolbar.addAction(git_pull_action)
        
        git_push_action = QAction("📤 Git Push", self)
        git_push_action.triggered.connect(self.trigger_github_push)
        self.toolbar.addAction(git_push_action)

        self.tab_manager = QTabWidget()
        self.tab_manager.setStyleSheet("""
            QTabBar::tab { height: 35px; width: 160px; font-weight: bold; background: #2d2d2d; color: #8b9eb0;}
            QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-bottom: 2px solid #61afef; }
            QTabWidget::pane { border: none; }
        """)
        self.setCentralWidget(self.tab_manager)

        self.initialize_environments()
        
        if self.settings.value("window_geometry"):
            self.restoreGeometry(self.settings.value("window_geometry"))
        if self.settings.value("window_state"):
            self.restoreState(self.settings.value("window_state"))

    def initialize_environments(self):
        py_root = self.settings.value("python_root_path", PYTHON_DEV_DIR)
        web_root = self.settings.value("web_root_path", WEB_DEV_DIR)
        
        if not py_root.startswith(PYTHON_DEV_DIR) or not os.path.isdir(py_root): 
            py_root = PYTHON_DEV_DIR
        if not web_root.startswith(WEB_DEV_DIR) or not os.path.isdir(web_root): 
            web_root = WEB_DEV_DIR
        
        self.python_env = PythonEnvironment(root_path=py_root)
        self.tab_manager.addTab(self.python_env, "🐍 Python Vibe")
        
        self.web_env = WebEnvironment(root_path=web_root)
        self.tab_manager.addTab(self.web_env, "🌐 Web Vibe")

    def closeEvent(self, event):
        if not self.python_env.check_unsaved_changes():
            event.ignore()
            return
        if not self.web_env.check_unsaved_changes():
            event.ignore()
            return
            
        self.settings.setValue("python_root_path", self.python_env.root_path)
        self.settings.setValue("web_root_path", self.web_env.root_path)
        self.settings.setValue("window_geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        super().closeEvent(event)

    def trigger_screenshot(self):
        try:
            subprocess.Popen(["gnome-screenshot", "-a", "-c"])
            self.statusBar().showMessage("📸 Select an area to copy to your clipboard, then paste it into Gemini!", 6000)
        except FileNotFoundError:
            QMessageBox.warning(self, "Missing Dependency", "Linux Mint's 'gnome-screenshot' utility could not be found.")

    def copy_project_tree(self):
        current_env = self.tab_manager.currentWidget()
        if not hasattr(current_env, 'root_path'): return
        
        root_dir = current_env.root_path
        
        def build_tree(path, prefix=""):
            if not os.path.exists(path): return ""
            tree_str = ""
            try:
                items = os.listdir(path)
            except PermissionError:
                return ""
                
            items = [i for i in items if i not in ['.git', '__pycache__', 'node_modules', '.venv', '.idea']]
            items.sort()
            
            for i, item in enumerate(items):
                is_last = (i == len(items) - 1)
                connector = "└── " if is_last else "├── "
                tree_str += f"{prefix}{connector}{item}\n"
                
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    extension = "    " if is_last else "│   "
                    tree_str += build_tree(item_path, prefix + extension)
            return tree_str

        project_name = os.path.basename(root_dir)
        final_tree = f"Project: {project_name}/\n" + build_tree(root_dir)
        
        QApplication.clipboard().setText(final_tree)
        self.statusBar().showMessage("🌲 Project Tree copied to clipboard!", 4000)

    def save_active_env(self):
        current_env = self.tab_manager.currentWidget()
        if hasattr(current_env, 'save_current_file'):
            if current_env.save_current_file():
                if current_env.current_file_path:
                    self.statusBar().showMessage(f"Saved: {os.path.basename(current_env.current_file_path)}", 3000)

    def trigger_github_pull(self):
        current_env = self.tab_manager.currentWidget()
        if not hasattr(current_env, 'root_path'): return
        repo_dir = current_env.root_path

        if not os.path.exists(os.path.join(repo_dir, ".git")):
            QMessageBox.information(self, "Git Pull", "This folder is not a Git repository.")
            return

        try:
            result = subprocess.run(["git", "pull"], cwd=repo_dir, capture_output=True, text=True)
            if result.returncode == 0:
                QMessageBox.information(self, "Git Pull Success", result.stdout)
                if hasattr(current_env, 'update_git_and_redraw'):
                    current_env.update_git_and_redraw()
            else:
                QMessageBox.warning(self, "Git Pull Failed", result.stderr)
        except Exception as e:
            QMessageBox.critical(self, "Git Error", str(e))

    def trigger_github_push(self):
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
        msg, ok = QInputDialog.getText(self, "Git Commit", "Enter commit message:", text=default_msg)
        
        if ok and msg:
            try:
                subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True, capture_output=True)
                result = subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, capture_output=True, text=True)
                
                if "nothing to commit" in result.stdout:
                    QMessageBox.information(self, "Git Push", "Working tree clean. No changes to commit.")
                    return
                
                push_result = subprocess.run(["git", "push"], cwd=repo_dir, capture_output=True, text=True)
                
                if push_result.returncode == 0: status = "✅ Success!\n\nChanges committed and pushed."
                else: status = "✅ Local Commit Successful!\n\n⚠️ Could not push to GitHub. Check terminal to run 'git push -u origin main'."
                    
                QMessageBox.information(self, "Push Status", status)
                self.statusBar().showMessage("Git push process finished.", 5000)
                
                if hasattr(current_env, 'update_git_and_redraw'):
                    current_env.update_git_and_redraw()

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
