# Python & Conda Environment Manager

A PyQt6-based desktop application for discovering, managing, and interacting with Python virtual environments and Conda environments on your system.

## Features

- **Automatic Environment Detection**: Scans directories to find:
  - Standard Python virtual environments (`venv`, `virtualenv`)
  - Conda environments
- **Tree View Display**: Visualizes discovered environments in a hierarchical structure
- **Context Menu Actions**:
  - Open terminal in the virtual environment folder
  - Open terminal in the parent folder with environment activated
  - Run Python scripts found inside or outside the environment
- **Cross-Platform Support**: Works on Windows, macOS, and Linux
- **Dark Mode UI**: Modern dark theme stylesheet for comfortable viewing

## Requirements

- Python 3.8+
- PyQt6

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install PyQt6
   ```

## Usage

Run the application:
```bash
python venv_manager.py
```

1. **Select Directory**: Use the "Browse..." button or manually enter a root directory path to scan
2. **Scan**: Click "Scan" to search for virtual environments within the selected directory
3. **Interact**: Right-click on any detected environment to:
   - Open a terminal with the environment activated
   - Run Python scripts found in or near the environment

## Platform-Specific Notes

### Windows
- Uses `cmd.exe` for terminal operations
- Supports both `.bat` activation scripts for standard venvs and `conda activate` for Conda environments

### macOS
- Uses AppleScript to control the Terminal app
- Requires Terminal app to be installed (default on macOS)

### Linux
- Automatically detects and uses available terminal emulators in this priority order:
  - gnome-terminal
  - konsole
  - xfce4-terminal
  - x-terminal-emulator
  - xterm
  - alacritty
  - kitty

## Project Structure

```
.
├── main.py              # Main application file
└── README.md            # This file
```

## How It Works

1. **Scanning**: The `VenvSearchWorker` thread walks through the directory tree looking for:
   - `conda-meta` folders (Conda environments)
   - `bin/activate` or `Scripts/activate` files (Python venvs)

2. **Tree Building**: Discovered paths are organized into a tree structure showing the hierarchy relative to the scanned root directory

3. **Script Discovery**: When right-clicking an environment, the app searches for:
   - Python files inside the venv (excluding dependency folders like `lib`, `bin`, etc.)
   - Python files in the parent directory (outside the venv)

4. **Terminal Launch**: Based on the OS, the app constructs appropriate commands to:
   - Change to the working directory
   - Activate the environment
   - Optionally run a selected Python script

## Customization

The application includes a comprehensive dark mode stylesheet. You can modify the `QApplication.setStyleSheet()` call in the `__main__` block to customize colors and styling.

## License

This project is provided as-is for educational and practical use.
