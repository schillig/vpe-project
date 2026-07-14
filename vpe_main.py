"""
Project: Vibe Programming Environment (VPE) - Build 1.0.3
Target OS: Linux Mint Only
Description: Added "Paste & Save" 1-click update button to the Main Controls toolbar for rapid AI iteration.
Architecture: PySide6 (Qt) Unified Interface.
"""

import sys
import os
import subprocess
import re
import pty
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, 
                             QVBoxLayout, QWidget, QTextEdit, QTabWidget,
                             QPlainTextEdit, QMessageBox, QFileSystemModel, 
                             QTreeView, QMenu, QInputDialog, QFileDialog, 
                             QStyledItemDelegate, QToolBar)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSocketNotifier, QDir, QRegularExpression, QSize, Signal, QRect, QTimer, QUrl, QSettings
from PySide6.QtGui import (QAction, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, 
                           QColor, QPainter, QTextFormat)

# --- SYSTEM PATCHES ---
os.environ["QT_API"] = "pyside6"                                        
os.environ["QSG_RHI_BACKEND"] = "opengl"                                
os.environ["QT_LOGGING_RULES"] = "qt.accessibility.atspi.warning=false" 

DEV_DIR = os.path.expanduser("~/Development")

# --- GLOBAL STYLESHEET (One Dark Pro) ---
GLOBAL_THEME = """
    QMainWindow, QWidget { background-color: #282c34; color: #abb2bf; }
    QMenuBar { background-color: #21252b; color: #abb2bf; border-bottom: 1px solid #181a1f; padding: 2px;}
    QMenuBar::item:selected { background-color: #3e4451; }
    QMenu { background-color: #282c34; border: 1px solid #181a1f; }
    QMenu::item { padding: 6px 25px; }
    QMenu::item:selected { background-color: #3e4451; }
    QToolBar { background-color: #21252b; border-bottom: 1px solid #181a1f; padding: 3px; spacing: 5px; }
    QToolButton { color: #abb2bf; font-weight: bold; font-size: 10pt; padding: 5px 10px; border-radius: 4px; }
    QToolButton:hover { background-color: #3e4451; color: #ffffff; }
    QTreeView { background-color: #21252b; border: none; font-size: 10pt; outline: none; }
    QTreeView::item:selected { background-color: #2c313a; color: #ffffff; }
    QTreeView::item:hover { background-color: #2c313a; }
    QSplitter::handle { background-color: #181a1f; }
    QTabWidget::pane { border: 1px solid #181a1f; border-top: none; }
    QTabBar::tab { background: #21252b; color: #5c6370; padding: 8px 15px; border-right: 1px solid #181a1f; }
    QTabBar::tab:selected { background: #282c34; color: #e5c07b; border-top: 2px solid #e5c07b; }
    QTabBar::tab:hover:!selected { background: #2c313a; color: #abb2bf; }
    QPlainTextEdit { background-color: #282c34; border: none; font-family: 'Ubuntu Mono', monospace; font-size: 11pt;}
    QScrollBar:vertical { border: none; background: #1e1e1e; width: 12px; }
    QScrollBar::handle:vertical { background: #4b5363; border-radius: 6px; min-height: 20px; }
    QScrollBar::handle:vertical:hover { background: #5c6370; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""

# --- HIGHLIGHTERS ---
class EditorHighlighter(QSyntaxHighlighter):
    def __init__(self, document, ext):
        super().__init__(document)
        self.rules = []
        
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#c678dd"))
        kw_fmt.setFontWeight(QFont.Bold)
        
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#98c379"))
        
        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#61afef"))
        
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#5c6370"))
        comment_fmt.setFontItalic(True)

        if ext == '.py':
            keywords = ["\\band\\b", "\\bclass\\b", "\\bdef\\b", "\\belif\\b", "\\belse\\b", "\\bfor\\b", "\\bif\\b", "\\bimport\\b", "\\bin\\b", "\\breturn\\b", "\\bTrue\\b", "\\bFalse\\b", "\\bNone\\b"]
            for word in keywords: self.rules.append((QRegularExpression(word), kw_fmt))
            self.rules.append((QRegularExpression("\\bdef\\s+([A-Za-z_]+)"), func_fmt))
            self.rules.append((QRegularExpression("\\bclass\\s+([A-Za-z_]+)"), func_fmt))
            self.rules.append((QRegularExpression("\".*?\""), str_fmt))
            self.rules.append((QRegularExpression("'.*?'"), str_fmt))
            self.rules.append((QRegularExpression("#[^\n]*"), comment_fmt))
            
        elif ext in ['.html', '.css', '.js']:
            self.rules.append((QRegularExpression("</?[a-zA-Z0-9_\\-]+>??"), func_fmt))
            keywords = ["\\bvar\\b", "\\blet\\b", "\\bconst\\b", "\\bfunction\\b", "\\bdocument\\b", "\\bwindow\\b", "\\breturn\\b"]
            for word in keywords: self.rules.append((QRegularExpression(word), kw_fmt))
            self.rules.append((QRegularExpression("\".*?\""), str_fmt))
            self.rules.append((QRegularExpression("'.*?'"), str_fmt))
            self.rules.append((QRegularExpression(""), comment_fmt))
            self.rules.append((QRegularExpression("//[^\n]*"), comment_fmt))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

# --- CORE UI COMPONENTS ---
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    def sizeHint(self): return QSize(self.editor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): self.editor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        digits = max(1, len(str(max(1, self.blockCount()))))
        return 15 + self.fontMetrics().horizontalAdvance('9') * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)

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
                painter.setPen(QColor("#4b5363"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(), Qt.AlignRight | Qt.AlignVCenter, str(blockNumber + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1 

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2c313a"))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

class NativeLinuxTerminal(QPlainTextEdit):
    ANSI_ESCAPE = re.compile(r'(?:\x1B\[[0-?]*[ -/]*[@-~])|(?:\x1B\].*?(?:\x07|\x1B\\))')

    def __init__(self, cwd=None):
        super().__init__()
        self.setStyleSheet("background-color: #1e1e1e; color: #abb2bf; font-family: 'Ubuntu Mono'; font-size: 11pt; border: none; padding: 5px;")
        self.master_fd, self.slave_fd = pty.openpty()
        
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        self.process = subprocess.Popen(["/bin/bash"], stdin=self.slave_fd, stdout=self.slave_fd, stderr=self.slave_fd, preexec_fn=os.setsid, env=env, cwd=cwd)
        
        self.notifier = QSocketNotifier(self.master_fd, QSocketNotifier.Read)
        self.notifier.activated.connect(self.read_shell_output)

    def read_shell_output(self):
        try:
            data = os.read(self.master_fd, 1024).decode(errors='ignore')
            self.insertPlainText(self.ANSI_ESCAPE.sub('', data).replace('\x07', ''))
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        except OSError: pass

    def keyPressEvent(self, event):
        text = event.text()
        if event.key() == Qt.Key_Return: text = "\n"
        elif event.key() == Qt.Key_Backspace: text = "\b"
        elif event.key() == Qt.Key_Tab: text = "\t"
        if text: os.write(self.master_fd, text.encode())

    def insertFromMimeData(self, source):
        if source.hasText(): os.write(self.master_fd, source.text().encode())

    def send_command(self, command: str):
        if not command.endswith("\n"): command += "\n"
        os.write(self.master_fd, command.encode())

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
            if self.git_statuses: self.git_statuses.clear(); return True
            return False
        try:
            result = subprocess.run(["git", "status", "-s"], cwd=self.repo_root, capture_output=True, text=True)
            new_statuses = {}
            for line in result.stdout.splitlines():
                if len(line) < 3: continue
                status, file_rel_path = line[:2], line[3:].strip().strip('"')
                if "->" in file_rel_path: file_rel_path = file_rel_path.split("->")[-1].strip()
                abs_path = os.path.abspath(os.path.join(self.repo_root, file_rel_path))

                if "??" in status or "A" in status: new_statuses[abs_path] = "untracked"
                elif any(c in status for c in "MDRC"): new_statuses[abs_path] = "modified"

            folder_statuses = {}
            for fpath in new_statuses:
                parent = os.path.dirname(fpath)
                while parent.startswith(self.repo_root) and parent != self.repo_root:
                    folder_statuses[parent] = "modified"
                    parent = os.path.dirname(parent)

            combined = {**new_statuses, **folder_statuses}
            if self.git_statuses != combined:
                self.git_statuses = combined
                return True
        except Exception: pass
        return False

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.ForegroundRole:
            path = self.filePath(index)
            status = self.git_statuses.get(path)
            if status == "untracked": return QColor("#98c379")
            elif status == "modified": return QColor("#e5c07b")
            return QColor("#abb2bf")
        return super().data(index, role)

# --- MAIN UNIFIED IDE ---
class VPEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.setApplicationName("VPE")
        self.setWindowTitle("VPE 1.0.3 - Professional Edition")
        self.resize(1400, 900)
        self.settings = QSettings("VibeCorp", "VPE_IDE")
        self.current_workspace = self.settings.value("last_workspace", DEV_DIR)
        
        self.setup_menus()
        self.setup_toolbar()
        self.setup_ui()
        self.set_workspace(self.current_workspace)

        # Background Timers
        self.git_timer = QTimer(self)
        self.git_timer.timeout.connect(self.update_git_tree)
        self.git_timer.start(2000)
        
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)

        # Load states
        if self.settings.value("window_geometry"): self.restoreGeometry(self.settings.value("window_geometry"))
        if self.settings.value("window_state"): self.restoreState(self.settings.value("window_state"))

    def setup_menus(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("📁 Create New Project...", self.create_new_project)
        file_menu.addAction("📂 Switch Workspace...", self.open_workspace_dialog)
        file_menu.addSeparator()
        save_act = file_menu.addAction("💾 Save Active File")
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_active_tab)
        file_menu.addSeparator()
        file_menu.addAction("❌ Exit", self.close)

        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        snip_act = tools_menu.addAction("📸 Area Snip (Screenshot)")
        snip_act.setShortcut("Ctrl+Shift+S")
        snip_act.triggered.connect(self.trigger_screenshot)
        tools_menu.addAction("🌲 Copy Project Tree", self.copy_project_tree)

        # Environment Menu
        env_menu = menubar.addMenu("Environment")
        env_menu.addAction("📦 Build Virtual Env", self.build_venv)
        env_menu.addAction("🟢 Start/Stop Venv", self.toggle_venv)
        env_menu.addSeparator()
        env_menu.addAction("🚀 Compile to App", self.make_app)

        # Source Control Menu
        git_menu = menubar.addMenu("Source Control")
        git_menu.addAction("🛠️ Initialize Repo & Shield", self.init_git)
        git_menu.addAction("📥 Pull", self.git_pull)
        git_menu.addAction("📤 Commit & Push", self.git_push)
        
        # View Menu
        view_menu = menubar.addMenu("View")
        view_menu.addAction("👁️ Toggle Hidden Files", self.toggle_hidden).setCheckable(True)

    def setup_toolbar(self):
        self.toolbar = QToolBar("Main Controls")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        save_act = QAction("💾 Save File", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_active_tab)
        self.toolbar.addAction(save_act)
        
        # --- NEW PASTE & SAVE BUTTON ---
        paste_save_act = QAction("📋 Paste & Save", self)
        paste_save_act.triggered.connect(self.paste_and_save)
        self.toolbar.addAction(paste_save_act)
        # -------------------------------
        
        self.toolbar.addSeparator()

        snip_act = QAction("📸 Area Snip", self)
        snip_act.setShortcut("Ctrl+Shift+S")
        snip_act.triggered.connect(self.trigger_screenshot)
        self.toolbar.addAction(snip_act)

        tree_act = QAction("🌲 Copy Tree", self)
        tree_act.triggered.connect(self.copy_project_tree)
        self.toolbar.addAction(tree_act)
        
        self.toolbar.addSeparator()

        pull_act = QAction("📥 Git Pull", self)
        pull_act.triggered.connect(self.git_pull)
        self.toolbar.addAction(pull_act)

        push_act = QAction("📤 Git Push", self)
        push_act.triggered.connect(self.git_push)
        self.toolbar.addAction(push_act)

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel (File Explorer)
        self.file_model = GitAwareFileSystemModel()
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        for i in range(1, 4): self.tree.setColumnHidden(i, True)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self.handle_tree_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.main_splitter.addWidget(self.tree)

        # Center Panel (Editor & Terminal)
        self.center_splitter = QSplitter(Qt.Vertical)
        
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_tab)
        self.editor_tabs.currentChanged.connect(self.on_tab_changed)
        self.center_splitter.addWidget(self.editor_tabs)

        self.terminal = NativeLinuxTerminal()
        self.center_splitter.addWidget(self.terminal)
        self.center_splitter.setSizes([700, 200])
        
        self.main_splitter.addWidget(self.center_splitter)

        # Right Panel (Live Web Preview - Hidden by default)
        self.preview_view = QWebEngineView()
        self.preview_view.setStyleSheet("background-color: #ffffff;")
        self.preview_view.hide() 
        self.main_splitter.addWidget(self.preview_view)

        self.main_splitter.setSizes([250, 900, 0])
        main_layout.addWidget(self.main_splitter)
        self.setCentralWidget(central_widget)

    # --- RESTORED TOOLS & WORKFLOW MACROS ---
    def trigger_screenshot(self):
        try:
            subprocess.Popen(["gnome-screenshot", "-a", "-c"])
            self.statusBar().showMessage("📸 Select an area to copy to your clipboard!", 6000)
        except FileNotFoundError:
            QMessageBox.warning(self, "Missing Tool", "Linux Mint's 'gnome-screenshot' utility is missing.")

    def copy_project_tree(self):
        if not self.current_workspace: return
        def build_tree(path, prefix=""):
            if not os.path.exists(path): return ""
            tree_str = ""
            try: items = os.listdir(path)
            except PermissionError: return ""
            items = [i for i in items if i not in ['.git', '__pycache__', 'node_modules', '.venv']]
            items.sort()
            for i, item in enumerate(items):
                is_last = (i == len(items) - 1)
                tree_str += f"{prefix}{'└── ' if is_last else '├── '}{item}\n"
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    tree_str += build_tree(item_path, prefix + ('    ' if is_last else '│   '))
            return tree_str

        final_tree = f"Project: {os.path.basename(self.current_workspace)}/\n" + build_tree(self.current_workspace)
        QApplication.clipboard().setText(final_tree)
        self.statusBar().showMessage("🌲 Project Tree copied to clipboard!", 4000)

    def paste_and_save(self):
        editor = self.editor_tabs.currentWidget()
        if not editor:
            QMessageBox.warning(self, "No Active Tab", "Please open a file to paste code into.")
            return
            
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text:
            self.statusBar().showMessage("⚠️ Clipboard is empty!", 4000)
            return
            
        # Select all existing text and overwrite with clipboard
        editor.selectAll()
        editor.insertPlainText(clipboard_text)
        
        # Save immediately
        self.save_active_tab()
        self.statusBar().showMessage(f"✅ Pasted and saved to {os.path.basename(editor.file_path)}!", 4000)

    # --- TAB & FILE MANAGEMENT ---
    def handle_tree_click(self, index):
        path = self.file_model.filePath(index)
        if os.path.isdir(path): self.set_workspace(path)
        elif os.path.isfile(path): self.open_file_in_tab(path)

    def open_file_in_tab(self, file_path):
        for i in range(self.editor_tabs.count()):
            if self.editor_tabs.widget(i).file_path == file_path:
                self.editor_tabs.setCurrentIndex(i)
                return

        editor = CodeEditor(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                editor.setPlainText(f.read())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read file: {e}")
            return

        ext = os.path.splitext(file_path)[1].lower()
        editor.highlighter = EditorHighlighter(editor.document(), ext)
        editor.document().setModified(False)
        editor.textChanged.connect(lambda: self.preview_timer.start(500))

        idx = self.editor_tabs.addTab(editor, os.path.basename(file_path))
        self.editor_tabs.setCurrentIndex(idx)

    def close_tab(self, index):
        editor = self.editor_tabs.widget(index)
        if editor.document().isModified():
            reply = QMessageBox.question(self, "Unsaved Changes", f"Save changes to {os.path.basename(editor.file_path)}?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes: self.save_active_tab()
            elif reply == QMessageBox.Cancel: return
        self.editor_tabs.removeTab(index)
        editor.deleteLater()

    def on_tab_changed(self, index):
        if index == -1: 
            self.preview_view.hide()
            return
            
        editor = self.editor_tabs.widget(index)
        if editor.file_path.endswith(('.html', '.js', '.css')):
            if self.preview_view.isHidden():
                sizes = self.main_splitter.sizes()
                self.preview_view.show()
                if sizes[2] == 0: self.main_splitter.setSizes([sizes[0], int(sizes[1] * 0.6), int(sizes[1] * 0.4)])
            self.render_preview()
        else:
            self.preview_view.hide()

    def save_active_tab(self):
        editor = self.editor_tabs.currentWidget()
        if not editor: return
        try:
            with open(editor.file_path, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
            editor.document().setModified(False)
            self.statusBar().showMessage(f"Saved {os.path.basename(editor.file_path)}", 3000)
            self.update_git_tree()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def render_preview(self):
        editor = self.editor_tabs.currentWidget()
        if editor and editor.file_path.endswith(('.html', '.css', '.js')):
            self.preview_view.setHtml(editor.toPlainText(), QUrl.fromLocalFile(self.current_workspace + os.sep))

    # --- WORKSPACE & TERMINAL ---
    def set_workspace(self, path):
        if not os.path.isdir(path): return
        self.current_workspace = path
        self.file_model.setRootPath(path)
        self.tree.setRootIndex(self.file_model.index(path))
        self.file_model.set_repo_root(path)
        
        # Reset Terminal
        self.terminal.deleteLater()
        self.terminal = NativeLinuxTerminal(cwd=path)
        self.center_splitter.addWidget(self.terminal)
        self.setWindowTitle(f"VPE 1.0.3 - {os.path.basename(path)}")
        self.statusBar().showMessage(f"Workspace loaded: {path}")

    def create_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Enter new project name:")
        if ok and name:
            new_path = os.path.join(self.current_workspace, name)
            if not os.path.exists(new_path):
                os.makedirs(new_path)
                self.set_workspace(new_path)

    def open_workspace_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace", DEV_DIR)
        if dir_path: self.set_workspace(dir_path)

    def toggle_hidden(self, checked):
        filters = QDir.AllEntries | QDir.NoDotAndDotDot
        if checked: filters |= QDir.Hidden
        self.file_model.setFilter(filters)

    def build_venv(self):
        self.terminal.clear()
        cmd = f"cd '{self.current_workspace}' && python3 -m venv .venv && source .venv/bin/activate"
        req_path = os.path.join(self.current_workspace, "requirements.txt")
        if os.path.exists(req_path): cmd += " && pip install -r requirements.txt"
        self.terminal.send_command(cmd + "\n")

    def toggle_venv(self):
        self.terminal.send_command(f"cd '{self.current_workspace}' && source .venv/bin/activate\n")

    def make_app(self):
        editor = self.editor_tabs.currentWidget()
        if not editor or not editor.file_path.endswith('.py'):
            QMessageBox.warning(self, "No Python File", "Please open a .py file to compile.")
            return
            
        name, ok = QInputDialog.getText(self, "Make App", "Linux Mint Start Menu Name:", text=os.path.basename(editor.file_path).replace('.py', ''))
        if ok and name:
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_').lower()
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)
            desktop_path = os.path.join(desktop_dir, f"{safe_name}.desktop")
            
            py_path = os.path.join(self.current_workspace, ".venv", "bin", "python") if os.path.exists(os.path.join(self.current_workspace, ".venv")) else "python3"
            
            content = f"[Desktop Entry]\nVersion=1.0\nName={name}\nExec='{py_path}' '{editor.file_path}'\nIcon=python\nTerminal=true\nType=Application\nCategories=Development;\n"
            with open(desktop_path, 'w') as f: f.write(content)
            os.chmod(desktop_path, 0o755)
            subprocess.run(["update-desktop-database", desktop_dir])
            QMessageBox.information(self, "Success", f"'{name}' added to Linux Mint Start Menu.")

    # --- GIT PIPELINE ---
    def update_git_tree(self):
        if self.file_model.update_git_status(): self.tree.viewport().update()

    def init_git(self):
        if os.path.exists(os.path.join(self.current_workspace, ".git")):
            QMessageBox.information(self, "Git", "Already a repo.")
            return
        self.git_timer.stop()
        subprocess.run(["git", "init"], cwd=self.current_workspace)
        with open(os.path.join(self.current_workspace, ".gitignore"), "w") as f:
            f.write(".venv/\nvenv/\n__pycache__/\n.buildozer/\n")
        self.file_model.set_repo_root(self.current_workspace)
        self.update_git_tree()
        self.git_timer.start(2000)
        QMessageBox.information(self, "Success", "Git Initialized with Shield.")

    def git_pull(self):
        res = subprocess.run(["git", "pull"], cwd=self.current_workspace, capture_output=True, text=True)
        QMessageBox.information(self, "Pull Result", res.stdout if res.returncode == 0 else res.stderr)

    def git_push(self):
        msg, ok = QInputDialog.getText(self, "Commit", "Message:", text=f"VPE Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if ok and msg:
            subprocess.run(["git", "add", "-A"], cwd=self.current_workspace)
            subprocess.run(["git", "commit", "-m", msg], cwd=self.current_workspace)
            res = subprocess.run(["git", "push"], cwd=self.current_workspace, capture_output=True, text=True)
            status = "✅ Pushed to GitHub" if res.returncode == 0 else "✅ Local Commit OK.\n⚠️ Remote push failed (check terminal)."
            QMessageBox.information(self, "Push Status", status)

    # --- NEMO CONTEXT MENU ---
    def show_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        path = self.file_model.filePath(index) if index.isValid() else self.current_workspace
        
        menu = QMenu()
        run_act = menu.addAction("▶️ Run Python Script") if path.endswith('.py') else None
        menu.addSeparator()
        new_f_act = menu.addAction("📄 New File")
        new_d_act = menu.addAction("📁 New Folder")
        menu.addSeparator()
        del_act = menu.addAction("🗑️ Move to Trash (gio)")
        nemo_act = menu.addAction("📂 Open in Nemo")

        act = menu.exec(self.tree.viewport().mapToGlobal(pos))
        
        if act == run_act:
            py_path = os.path.join(self.current_workspace, ".venv", "bin", "python") if os.path.exists(os.path.join(self.current_workspace, ".venv")) else "python3"
            self.terminal.send_command(f"cd '{os.path.dirname(path)}' && '{py_path}' '{os.path.basename(path)}'\n")
        elif act == new_f_act:
            name, ok = QInputDialog.getText(self, "New File", "Name:")
            if ok and name: open(os.path.join(path if os.path.isdir(path) else os.path.dirname(path), name), 'w').close()
        elif act == new_d_act:
            name, ok = QInputDialog.getText(self, "New Folder", "Name:")
            if ok and name: os.makedirs(os.path.join(path if os.path.isdir(path) else os.path.dirname(path), name))
        elif act == del_act:
            if QMessageBox.question(self, "Trash", f"Move {os.path.basename(path)} to trash?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                subprocess.run(["gio", "trash", path])
        elif act == nemo_act:
            subprocess.Popen(["nemo", path if os.path.isdir(path) else os.path.dirname(path)])

    def closeEvent(self, event):
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if editor.document().isModified():
                self.editor_tabs.setCurrentIndex(i)
                reply = QMessageBox.question(self, "Unsaved Changes", f"Save changes to {os.path.basename(editor.file_path)}?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if reply == QMessageBox.Yes: self.save_active_tab()
                elif reply == QMessageBox.Cancel: 
                    event.ignore()
                    return

        self.settings.setValue("last_workspace", self.current_workspace)
        self.settings.setValue("window_geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_THEME)
    window = VPEWindow()
    window.show()
    sys.exit(app.exec())