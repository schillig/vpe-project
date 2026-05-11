"""
Project: Vibe Programming Environment (VPE) - Build 0.4
Target OS: Linux Mint Only
Description: Integrated File Explorer, Syntax Highlighting, and Automated Git/GitHub Sync.
Architecture: PySide6 (Qt) with QFileSystemModel, POSIX PTY, and Subprocess Git Integration.
"""

import sys
import os
import pty
import subprocess
import re
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, 
                             QVBoxLayout, QWidget, QTextEdit, QTabWidget,
                             QPlainTextEdit, QToolBar, QMessageBox,
                             QFileSystemModel, QTreeView, QHeaderView,
                             QInputDialog)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, QSocketNotifier, QDir, QRegularExpression
from PySide6.QtGui import QAction, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor

class PythonHighlighter(QSyntaxHighlighter):
    """Real-time syntax highlighter for Python using Qt's native text document system."""
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        # Keywords (Purple)
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

        # Built-in functions (Cyan)
        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#56b6c2"))
        builtins = ["\\bprint\\b", "\\blen\\b", "\\bstr\\b", "\\bint\\b", "\\bfloat\\b", 
                    "\\btype\\b", "\\blist\\b", "\\bdict\\b", "\\bset\\b", "\\brange\\b"]
        for word in builtins: self.highlightingRules.append((QRegularExpression(word), builtinFormat))

        # Class names (Yellow)
        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#e5c07b"))
        self.highlightingRules.append((QRegularExpression("\\bclass\\s+([A-Za-z_]+)"), classFormat))

        # Function definitions (Blue)
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#61afef"))
        self.highlightingRules.append((QRegularExpression("\\bdef\\s+([A-Za-z_]+)"), functionFormat))

        # Strings (Green)
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#98c379"))
        self.highlightingRules.append((QRegularExpression("\".*?\""), stringFormat))
        self.highlightingRules.append((QRegularExpression("'.*?'"), stringFormat))

        # Comments (Grey, Italic)
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


class LanguageEnvironment(QWidget):
    """Language-specific workspace containing AI, File Tree, Editor, and Terminal."""
    def __init__(self, gemini_url: str, root_path: str):
        super().__init__()
        self.current_file_path = None
        self.root_path = root_path
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        self.ai_view = QWebEngineView()
        self.ai_view.setUrl(QUrl(gemini_url))
        self.main_splitter.addWidget(self.ai_view)
        
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(root_path)
        
        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(root_path))
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.setStyleSheet("background-color: #252526; color: #cccccc; border: none;")
        self.tree.doubleClicked.connect(self.open_file)
        
        self.edit_term_splitter = QSplitter(Qt.Vertical)
        
        self.editor = QTextEdit()
        self.editor.setStyleSheet("background-color: #282c34; color: #abb2bf; border: none; padding: 10px;")
        font = QFont("Ubuntu Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("# Double-click a .py file to start coding...")
        self.highlighter = PythonHighlighter(self.editor.document())
        
        self.terminal = NativeLinuxTerminal()
        
        self.edit_term_splitter.addWidget(self.editor)
        self.edit_term_splitter.addWidget(self.terminal)
        self.edit_term_splitter.setSizes([600, 300])
        
        self.workspace_splitter.addWidget(self.tree)
        self.workspace_splitter.addWidget(self.edit_term_splitter)
        self.workspace_splitter.setSizes([200, 800])
        
        self.main_splitter.addWidget(self.workspace_splitter)
        self.main_splitter.setSizes([400, 1000])
        
        layout.addWidget(self.main_splitter)

    def open_file(self, index):
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f: content = f.read()
                self.editor.setPlainText(content)
                self.current_file_path = path
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def save_current_file(self):
        if self.current_file_path:
            try:
                content = self.editor.toPlainText()
                with open(self.current_file_path, 'w') as f: f.write(content)
                return True
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Save failed: {e}")
        else:
            QMessageBox.warning(self, "Warning", "No file selected from the tree to save.")
        return False


class VPEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPE - Vibe Programming Environment (Linux Mint)")
        self.resize(1500, 950)

        # Toolbar Setup
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
                self.statusBar().showMessage(f"Saved: {current_env.current_file_path}", 3000)

    def trigger_github_backup(self):
        """Automates the Git staging, committing, and pushing process."""
        current_env = self.tab_manager.currentWidget()
        if not isinstance(current_env, LanguageEnvironment):
            return

        repo_dir = current_env.root_path

        # 1. Check if it's already a Git repository
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            reply = QMessageBox.question(self, "Initialize Git?", 
                                         "This folder is not currently a Git repository. Would you like VPE to initialize one now?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            else:
                return

        # 2. Automatically save the currently open file before syncing
        self.save_active_env()

        # 3. Prompt for a commit message
        default_msg = f"VPE Auto-Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg, ok = QInputDialog.getText(self, "Git Sync", "Enter commit message:", text=default_msg)
        
        if ok and msg:
            try:
                # Stage all changes
                subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True, capture_output=True)
                
                # Commit
                result = subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, capture_output=True, text=True)
                
                # If there was nothing to commit, stop here
                if "nothing to commit" in result.stdout:
                    QMessageBox.information(self, "Git Sync", "Working tree clean. No changes to commit.")
                    return
                
                # 4. Attempt to push to remote (GitHub)
                push_result = subprocess.run(["git", "push"], cwd=repo_dir, capture_output=True, text=True)
                
                if push_result.returncode == 0:
                    status = f"✅ Success!\n\nChanges committed and pushed to remote repository."
                else:
                    # It committed successfully, but couldn't push (likely no remote origin set up yet)
                    status = f"✅ Local Commit Successful!\n\n⚠️ Could not push to GitHub.\nIf you haven't linked a remote repository yet, open your VPE Terminal and run:\ngit remote add origin <your-github-url>\ngit push -u origin main"
                    
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
