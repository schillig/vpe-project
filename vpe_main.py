"""
Project: Vibe Programming Environment (VPE) - Build 0.10
Target OS: Linux Mint Only
Description: Inline "Run" buttons in the File Manager, Quick Commit, Persistent Web Sessions.
Architecture: PySide6 (Qt) with QStyledItemDelegate, QFileSystemModel, and POSIX PTY.
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
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtCore import QUrl, Qt, QSocketNotifier, QDir, QRegularExpression, QSize, Signal, QRect
from PySide6.QtGui import QAction, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor, QPainter

class PythonHighlighter(QSyntaxHighlighter):
    """Real-time syntax highlighter for Python using Qt's native text document system."""
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


class NativeLinuxTerminal(QPlainTextEdit):
    """Native Linux terminal emulator utilizing a POSIX pseudo-terminal."""
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

    # --- NEW: Command Injection Function ---
    def send_command(self, command: str):
        """Programmatically inputs a command into the bash shell."""
        if not command.endswith("\n"):
            command += "\n"
        os.write(self.master_fd, command.encode())


class RunFileDelegate(QStyledItemDelegate):
    """Custom Delegate to draw and handle clicks for a 'Run' button on .py files."""
    run_requested = Signal(str)

    def paint(self, painter, option, index):
        # Let Qt draw the standard file icon and text first
        super().paint(painter, option, index)
        
        model = index.model()
        if hasattr(model, 'filePath'):
            path = model.filePath(index)
            # Check if it's a python file
            if os.path.isfile(path) and path.endswith('.py'):
                rect = option.rect
                # Create a small button rect aligned to the right edge
                btn_rect = QRect(rect.right() - 32, rect.top() + (rect.height() - 20) // 2, 24, 20)
                
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing)
                
                # Draw the background of the button
                painter.setBrush(QColor("#2d2d2d"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(btn_rect, 4, 4)
                
                # Draw the green play icon
                painter.setPen(QColor("#98c379")) 
                font = painter.font()
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(btn_rect, Qt.AlignCenter, "▶")
                
                painter.restore()

    def editorEvent(self, event, model, option, index):
        """Intercepts mouse clicks in the tree view."""
        if event.type() == event.Type.MouseButtonRelease:
            path = model.filePath(index)
            if os.path.isfile(path) and path.endswith('.py'):
                rect = option.rect
                btn_rect = QRect(rect.right() - 32, rect.top() + (rect.height() - 20) // 2, 24, 20)
                # Check if the click landed exactly on our play button
                if btn_rect.contains(event.position().toPoint()):
                    self.run_requested.emit(path)
                    return True # Consume the event so it doesn't also open the file
        return super().editorEvent(event, model, option, index)


class BreadcrumbNavigation(QWidget):
    """Custom widget for Ghost Breadcrumb Navigation."""
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


class LanguageEnvironment(QWidget):
    """Language-specific workspace containing AI, File Tree, Editor, and Terminal."""
    def __init__(self, gemini_url: str, root_path: str):
        super().__init__()
        self.current_file_path = None
        self.root_path = root_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        self.web_profile = QWebEngineProfile("VPE_Gemini_Session", self)
        self.web_page = QWebEnginePage(self.web_profile, self)
        
        self.ai_view = QWebEngineView()
        self.ai_view.setPage(self.web_page)
        self.ai_view.setUrl(QUrl(gemini_url))
        self.main_splitter.addWidget(self.ai_view)
        
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        
        # --- File Explorer Pane (Sidebar) ---
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
        
        # --- NEW: Bind the Run Delegate to the Tree ---
        self.run_delegate = RunFileDelegate()
        self.run_delegate.run_requested.connect(self.execute_python_script)
        self.tree.setItemDelegateForColumn(0, self.run_delegate)
        # ----------------------------------------------
        
        self.tree.setStyleSheet("""
            QTreeView { background-color: #21252b; color: #abb2bf; border: none; font-size: 10pt; }
            QTreeView::item { padding: 4px; }
            QTreeView::item:selected { background-color: #2c313a; color: #ffffff; }
        """)
        self.tree.doubleClicked.connect(self.handle_tree_double_click)
        self.sidebar_layout.addWidget(self.tree)
        
        self.set_workspace_root(self.root_path)

        # --- Editor & Terminal Pane ---
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

        commit_code_btn = QAction("📋 Commit Code", self)
        commit_code_btn.triggered.connect(self.commit_code_from_clipboard)
        self.editor_toolbar.addAction(commit_code_btn)

        undo_commit_btn = QAction("↩️ Undo Commit", self)
        undo_commit_btn.triggered.connect(self.undo_commit_and_save)
        self.editor_toolbar.addAction(undo_commit_btn)

        self.editor_layout.addWidget(self.editor_toolbar)

        self.editor = QTextEdit()
        self.editor.setStyleSheet("background-color: #282c34; color: #abb2bf; border: none; padding: 10px;")
        font = QFont("Ubuntu Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("# Start typing, then hit Ctrl+S to save...\n# Or click '📋 Commit Code' to paste and save from clipboard.")
        self.highlighter = PythonHighlighter(self.editor.document())
        
        self.editor_layout.addWidget(self.editor)

        self.terminal = NativeLinuxTerminal()
        
        self.edit_term_splitter.addWidget(self.editor_container)
        self.edit_term_splitter.addWidget(self.terminal)
        self.edit_term_splitter.setSizes([600, 300])
        
        self.workspace_splitter.addWidget(self.sidebar_container)
        self.workspace_splitter.addWidget(self.edit_term_splitter)
        self.workspace_splitter.setSizes([250, 750])
        
        self.main_splitter.addWidget(self.workspace_splitter)
        self.main_splitter.setSizes([400, 1000])
        
        layout.addWidget(self.main_splitter)

    # --- NEW: Execution Logic ---
    def execute_python_script(self, file_path):
        """Changes terminal directory to file location and executes it."""
        # Auto-save the file if it's currently open in the editor
        if self.current_file_path == file_path:
            self.save_current_file()
            
        working_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # Inject the cd and run command into the native shell
        cmd = f"cd '{working_dir}' && python3 '{file_name}'"
        self.terminal.send_command(cmd)
    # ----------------------------

    def commit_code_from_clipboard(self):
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text:
            QMessageBox.information(self, "Empty Clipboard", "There is no text in your clipboard to commit.")
            return

        self.editor.selectAll()
        self.editor.insertPlainText(clipboard_text)
        self.save_current_file()
        
        parent = self.window()
        if hasattr(parent, 'statusBar'):
            parent.statusBar().showMessage("Code committed from clipboard and saved.", 4000)

    def undo_commit_and_save(self):
        self.editor.undo()
        self.save_current_file()
        
        parent = self.window()
        if hasattr(parent, 'statusBar'):
            parent.statusBar().showMessage("Last commit undone and file saved.", 4000)

    def set_workspace_root(self, path):
        if os.path.isdir(path):
            self.root_path = path
            self.file_model.setRootPath(self.root_path)
            self.tree.setRootIndex(self.file_model.index(self.root_path))
            self.breadcrumb.build_path(self.root_path)

    def open_workspace_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace Folder", self.root_path)
        if dir_path:
            self.set_workspace_root(dir_path)

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
            if not target_dir.exists(folder_name):
                target_dir.mkdir(folder_name)
            else:
                QMessageBox.warning(self, "Warning", "A folder with that name already exists.")

    def save_current_file(self):
        content = self.editor.toPlainText()
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save New File", self.root_path, "Python Files (*.py);;Text Files (*.txt);;All Files (*)")
            if file_path:
                self.current_file_path = file_path
            else:
                return False 

        try:
            with open(self.current_file_path, 'w') as f: f.write(content)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed: {e}")
            return False


class VPEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.setApplicationName("VPE")
        
        self.setWindowTitle("VPE - Vibe Programming Environment (Linux Mint)")
        self.resize(1500, 950)

        self.toolbar = QToolBar("Main Controls")
        self.addToolBar(self.toolbar)
        
        save_action = QAction("💾 Save (Ctrl+S)", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_active_env)
        self.toolbar.addAction(save_action)
        
        github_action = QAction("☁️ Sync to Git/GitHub", self)
        github_action.triggered.connect(self.trigger_github_backup)
        self.toolbar.addAction(github_action)

        self.tab_manager = QTabWidget()
        self.tab_manager.setStyleSheet("QTabBar::tab { height: 30px; width: 150px; }")
        self.setCentralWidget(self.tab_manager)

        self.initialize_environments()

    def initialize_environments(self):
        python_env = LanguageEnvironment(
            gemini_url="https://gemini.google.com/app",
            root_path=QDir.currentPath()
        )
        self.tab_manager.addTab(python_env, "🐍 Python Vibe")

    def save_active_env(self):
        current_env = self.tab_manager.currentWidget()
        if isinstance(current_env, LanguageEnvironment):
            if current_env.save_current_file():
                if current_env.current_file_path:
                    self.statusBar().showMessage(f"Saved: {os.path.basename(current_env.current_file_path)}", 3000)

    def trigger_github_backup(self):
        current_env = self.tab_manager.currentWidget()
        if not isinstance(current_env, LanguageEnvironment): return

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = VPEWindow()
    window.show()
    sys.exit(app.exec())
