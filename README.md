# CleanSweep

CleanSweep is a Qt5-based GUI application for efficiently cleaning up unnecessary files and directories on your system.

## Overview

CleanSweep can search for and delete the following temporary and system files:

- **Windows-related files**
  - Zone.Identifier files (download file identification information)
  - Thumbs.db (thumbnail cache files)

- **macOS-related files and directories**
  - .DS_Store (Finder display settings files)
  - ._* (resource fork files)
  - .AppleDouble/ (resource fork directories)
  - .fseventsd/ (file system event logs)
  - .Spotlight-V100/ (Spotlight index)
  - .AppleDB/ (AppleShare database)
  - .AppleDesktop/ (desktop database)
  - .TemporaryItems/ (temporary file storage directories)
  - Network Trash Folder/ (network trash folders)

## Key Features

### Search Functionality
- **Threaded search**: Asynchronous search that doesn't freeze the UI
- **Real-time progress display**: Shows currently searching directories
- **Cancel function**: Ability to interrupt long-running searches
- **System directory exclusion**: Automatically excludes Windows Program Files, Windows, and AppData directories

### Search Target Selection
- **File type selection**: Individual selection of file types to delete
- **Directory selection**: Choose target directories for search
  - User profile/home directory
  - All drives (with capacity and type display)
  - Network drive support
  - Custom directory addition
- **Bulk selection**: Easy selection with "Check All" buttons

### Safe Deletion Features
- **Trash movement**: Local files are safely moved to trash
- **Network path support**: Proper handling of UNC paths
- **Detailed error reporting**: Detailed cause display when deletion fails
- **Selective updates**: Option to re-search, removing only successfully deleted files from the list

## System Requirements (Runtime)

- Windows, macOS, or Linux

## System Requirements (Development)

- Windows, macOS, or Linux
- Python 3.10 or higher
- PyQt5

## Development

### Installing Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Direct Execution
```bash
python clean_sweep.py
```

## Creating Executable Files

### Windows Environment
Create executable file using PowerShell script:
```powershell
.\make.ps1
```

### Unix-based Environment (Linux/macOS)
Create executable file using shell script:
```bash
bash ./make.sh
```

Executable files will be generated in the `dist/` folder.

## Important Notes

- **Backup Recommended**: Please backup important data beforehand
- **Administrator Rights**: Some system files may require administrator privileges
- **Network Drives**: Files on network drives are deleted directly (not moved to trash)
