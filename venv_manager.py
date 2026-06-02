import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QTreeView, QFileDialog, QLabel, QMenu
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QCursor
from PyQt6.QtCore import QThread, pyqtSignal, Qt

class VenvSearchWorker(QThread):
    """Background worker to scan folders for Python and Conda virtual environments."""
    folder_found = pyqtSignal(str, str)  # Emits (absolute_path, env_type)
    finished = pyqtSignal()

    def __init__(self, root_dir):
        super().__init__()
        self.root_dir = root_dir
        self.is_running = True

    def run(self):
        python_indicators = [
            os.path.join("bin", "activate"),
            os.path.join("Scripts", "activate")
        ]

        for root, dirs, _ in os.walk(self.root_dir):
            if not self.is_running:
                break
            
            # 1. Check for Conda Environment
            if "conda-meta" in dirs:
                self.folder_found.emit(os.path.abspath(root), "Conda")
                dirs.clear()
                continue

            # 2. Check for Standard Python Virtual Environment
            is_python_venv = any(os.path.exists(os.path.join(root, p)) for p in python_indicators)
            if is_python_venv:
                self.folder_found.emit(os.path.abspath(root), "Python")
                dirs.clear()
                continue
                
        self.finished.emit()

    def stop(self):
        self.is_running = False


class VenvTreeViewApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python & Conda Environment Manager")
        self.resize(950, 650)
        
        self.worker = None
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Top Bar Configuration
        top_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        
        home_directory = os.path.expanduser("~")
        self.path_input.setText(home_directory)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_folder)
        
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self.start_scan)
        
        top_layout.addWidget(self.path_input, stretch=3)
        top_layout.addWidget(browse_btn)
        top_layout.addWidget(self.scan_btn)
        layout.addLayout(top_layout)

        # Tree View Setup
        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Detected Environments Structure"])
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setHeaderHidden(False)
        
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tree_view)

        # Status Label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.setCentralWidget(main_widget)

    def browse_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Root Directory", self.path_input.text())
        if dir_path:
            self.path_input.setText(dir_path)

    def start_scan(self):
        root_dir = self.path_input.text().strip()
        if not root_dir or not os.path.isdir(root_dir):
            self.status_label.setText("Error: Please select a valid folder path.")
            return

        self.tree_model.removeRows(0, self.tree_model.rowCount())
        self.scan_btn.setEnabled(False)
        self.status_label.setText(f"Scanning paths inside {root_dir}...")

        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        self.worker = VenvSearchWorker(root_dir)
        self.worker.folder_found.connect(self.add_venv_to_tree)
        self.worker.finished.connect(self.scan_finished)
        self.worker.start()

    def add_venv_to_tree(self, venv_path, env_type):
        root_dir = os.path.abspath(self.path_input.text().strip())
        rel_path = os.path.relpath(venv_path, root_dir)
        
        if rel_path == ".":
            path_parts = [os.path.basename(root_dir)]
        else:
            path_parts = [os.path.basename(root_dir)] + rel_path.split(os.sep)

        current_item = self.tree_model.invisibleRootItem()
        total_parts = len(path_parts)

        for index, part in enumerate(path_parts):
            if index == total_parts - 1:
                display_text = f"{part} [{env_type}]"
            else:
                display_text = part

            found = False
            for row in range(current_item.rowCount()):
                child = current_item.child(row)
                if child.text() == display_text or child.text().startswith(f"{part} ["):
                    current_item = child
                    found = True
                    break
            
            if not found:
                new_item = QStandardItem(display_text)
                new_item.setEditable(False)
                if index == total_parts - 1:
                    new_item.setData((venv_path, env_type), Qt.ItemDataRole.UserRole)
                current_item.appendRow(new_item)
                current_item = new_item
                
        self.tree_view.expandAll()

    def scan_finished(self):
        self.scan_btn.setEnabled(True)
        self.status_label.setText("Scan complete.")

    def show_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return

        item = self.tree_model.itemFromIndex(index)
        data = item.data(Qt.ItemDataRole.UserRole)
        
        if not data:
            return
            
        venv_path, env_type = data
        parent_path = os.path.dirname(venv_path)
        menu = QMenu(self)
        
        # Action 1: Open Terminal inside venv root folder
        term_venv_action = menu.addAction(f"Open Terminal in venv folder ({env_type})")
        term_venv_action.triggered.connect(lambda: self.launch_terminal(venv_path, env_type, working_dir=venv_path))
        
        # Action 2: Open Terminal inside parent folder (Activated)
        term_parent_action = menu.addAction(f"Open Terminal in parent folder ({env_type})")
        term_parent_action.triggered.connect(lambda: self.launch_terminal(venv_path, env_type, working_dir=parent_path))
        
        menu.addSeparator()

        # Gather and categorize Python files
        inside_files = self.find_inside_python_files(venv_path)
        outside_files = self.find_outside_python_files(parent_path, venv_path)

        if inside_files or outside_files:
            run_submenu = menu.addMenu("Run Python File inside Environment")
            
            def add_script_action(file_path, is_inside):
                file_name = os.path.basename(file_path)
                label_prefix = "[Inside] " if is_inside else "[Outside] "
                action_text = f"{label_prefix}{file_name}"
                
                if len(action_text) > 50:
                    action_text = f"{label_prefix}...{file_name[-35:]}"
                
                # Use HTML for reliable coloring in QMenu across all themes
                color_hex = "#4ade80" if is_inside else "#60a5fa" # Brighter variants for dark mode
                colored_text = f'<span style="color: {color_hex}; font-weight: bold;">{action_text}</span>'
                
                file_action = run_submenu.addAction(colored_text)
                
                target_wd = venv_path if is_inside else parent_path
                file_action.triggered.connect(
                    lambda checked, p=venv_path, t=env_type, f=file_path, wd=target_wd: 
                    self.launch_terminal(p, t, script_path=f, working_dir=wd)
                )

            for f_path in outside_files:
                add_script_action(f_path, is_inside=False)
                
            for f_path in inside_files:
                add_script_action(f_path, is_inside=True)
        else:
            disabled_action = menu.addAction("No standalone Python scripts found")
            disabled_action.setEnabled(False)

        menu.exec(QCursor.pos())

    def find_inside_python_files(self, venv_path):
        """Finds .py scripts inside the venv folder while skipping dependencies."""
        py_files = []
        ignore_folders = {"bin", "lib", "lib64", "include", "share", "conda-meta", "Scripts"}
        
        for root, dirs, files in os.walk(venv_path):
            dirs[:] = [d for d in dirs if d not in ignore_folders]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
        return py_files

    def find_outside_python_files(self, parent_path, venv_path):
        """Finds .py scripts located in the parent directory, skipping the venv itself."""
        py_files = []
        try:
            for entry in os.scandir(parent_path):
                if entry.is_dir() and os.path.abspath(entry.path) == os.path.abspath(venv_path):
                    continue
                
                if entry.is_file() and entry.name.endswith(".py"):
                    py_files.append(entry.path)
        except (PermissionError, FileNotFoundError):
            pass
        return py_files

    def launch_terminal(self, venv_path, env_type, working_dir=None, script_path=None):
        """Launches a terminal, activates the environment, and optionally runs a script."""
        if working_dir is None:
            working_dir = venv_path
            
        os_name = sys.platform
        
        if os_name == "win32":
            activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
            if env_type == "Conda" and not os.path.exists(activate_script):
                env_name = os.path.basename(venv_path)
                cmd = f'cmd.exe /k "conda activate {env_name}"'
            else:
                cmd = f'cmd.exe /k "call \\"{activate_script}\\""'
            
            if script_path:
                cmd += f' && python \\"{script_path}\\"'
                
            subprocess.Popen(cmd, cwd=working_dir, shell=True)
            
        elif os_name == "darwin":
            if env_type == "Conda":
                env_name = os.path.basename(venv_path)
                activate_cmd = f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate {env_name}"
            else:
                activate_path = os.path.join(venv_path, 'bin', 'activate')
                activate_cmd = f"source '{activate_path}'"
                
            script_cmd = f" && python '{script_path}'" if script_path else ""
            
            applescript = f'''
            tell application "Terminal"
                do script "cd '{working_dir}'; {activate_cmd}{script_cmd}"
                activate
            end tell
            '''
            subprocess.Popen(["osascript", "-e", applescript])
            
        else:
            # Linux
            if env_type == "Conda":
                env_name = os.path.basename(venv_path)
                activate_cmd = f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate {env_name}"
            else:
                activate_path = os.path.join(venv_path, 'bin', 'activate')
                activate_cmd = f"source '{activate_path}'"
                
            script_cmd = f" && python '{script_path}'" if script_path else ""
            
            terminals = [
                ["gnome-terminal", "--", "bash", "-c"],
                ["konsole", "-e", "bash", "-c"],
                ["xfce4-terminal", "-x", "bash", "-c"],
                ["x-terminal-emulator", "-e", "bash", "-c"],
                ["xterm", "-e", "bash", "-c"],
                ["alacritty", "-e", "bash", "-c"],
                ["kitty", "bash", "-c"]
            ]
            
            cmd_str = f"cd '{working_dir}'; {activate_cmd}{script_cmd}; exec bash"
            
            launched = False
            for term in terminals:
                try:
                    subprocess.Popen(term + [cmd_str], cwd=working_dir)
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            
            if not launched:
                self.status_label.setText("Error: Could not find a supported terminal emulator.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Comprehensive Dark Mode Stylesheet
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        QLineEdit {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px;
        }
        QLineEdit:focus {
            border: 1px solid #0078d7;
        }
        QPushButton {
            background-color: #3c3c3c;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        QTreeView {
            background-color: #252525;
            color: #e0e0e0;
            border: 1px solid #444444;
            border-radius: 4px;
            alternate-background-color: #2a2a2a;
        }
        QTreeView::item {
            padding: 5px;
        }
        QTreeView::item:hover {
            background-color: #3a3a3a;
        }
        QTreeView::item:selected {
            background-color: #0078d7;
            color: #ffffff;
        }
        QHeaderView::section {
            background-color: #333333;
            color: #e0e0e0;
            padding: 6px;
            border: 1px solid #444444;
            font-weight: bold;
        }
        QMenu {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 6px;
        }
        QMenu::item {
            padding: 6px 24px;
        }
        QMenu::item:selected {
            background-color: #3d3d3d;
        }
        QMenu::separator {
            height: 1px;
            background: #444444;
            margin: 4px 12px;
        }
        QLabel {
            color: #b0b0b0;
        }
        QScrollBar:vertical {
            background: #2b2b2b;
            width: 10px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #555555;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #666666;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)
    
    window = VenvTreeViewApp()
    window.show()
    sys.exit(app.exec())
