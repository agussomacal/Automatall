

# PDF Concatenator Micro-App

## Overview

A lightweight GTK-based desktop application that allows you to merge multiple PDF files into a single document through an intuitive drag-and-drop interface with manual reordering capabilities.

## Features

- **Drag & Drop Interface** – Drag PDF files from your file manager directly into the app window
- **Persistent Drop Zone** – Dedicated area on the left side always visible for file additions
- **Manual File Ordering** – Click to select a file, then use ↑/↓ arrow keys or buttons to reorder
- **Visual Tile System** – Each added PDF displays as a numbered tile with file name and controls
- **Smart Output Folder** – Automatically suggests output location based on first file's directory
- **Real-time Feedback** – Status bar shows progress, file counts, and operation results
- **Batch Processing** – Add multiple files at once via drag-drop or file browser

## How It Works

### Architecture

```
apps/pdf_concatenator/
├── config.yaml              # App configuration (name, description, category)
├── dependencies.yaml        # Required system dependencies (ghostscript)
├── __init__.py             # Package initialization
├── logic.py                # Core PDF merging logic (validation, concatenation)
├── app.py                  # GTK GUI implementation
├── icon.png               # App icon
└── tests/
    └── test_pdf_concatenator.py  # Unit tests for logic module
```

### Workflow Diagram

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  User Drops     │────▶│  Validation  │────▶│  Add to Queue   │
│  PDF Files      │     │  (PDF check) │     │  (Ordered List) │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Save Merged    │◀────│  Merge Via   │◀────│  Reorder Files  │
│  PDF            │     │  Ghostscript │     │  (Arrows/Buttons)│
└─────────────────┘     └──────────────┘     └─────────────────┘
```

## Requirements

### System Dependencies

| Dependency | Purpose | Install Command |
|------------|---------|-----------------|
| Python 3.6+ | Runtime | `sudo apt install python3` |
| PyGObject (GTK3) | GUI Framework | `sudo apt install python3-gi` |
| Ghostscript (`gs`) | PDF Processing | `sudo apt install ghostscript` |
| GTK 3 Libraries | UI Toolkit | `sudo apt install gir1.2-gtk-3.0` |

### Development Dependencies

- pytest (for testing)
- Any standard PDF viewer (for verifying merged output)

## Installation

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 ghostscript
```

**Fedora/RHEL:**
```bash
sudo dnf install python3 python3-gobject gtk3 ghostscript
```

**macOS (Homebrew):**
```bash
brew install python3 gtk+3 ghostscript
```

### 2. Clone or Copy the App

```bash
# Assuming you're in your project root
cd apps/pdf_concatenator/
chmod +x app.py
```

### 3. Run the Application

```bash
python3 app.py
```

Or from the parent directory:
```bash
python3 -m apps.pdf_concatenator.app
```

## Usage Guide

### Adding Files

| Method | Action |
|--------|--------|
| **Drag & Drop** | Drag PDF files from file manager to the drop zone |
| **Browse Button** | Click "Browse PDF Files" to open file picker (multi-select) |
| **Multiple Files** | Drop several files at once – they'll appear in the order dropped |

### Reordering Files

1. **Click** on any tile to select it (turns blue with ● marker)
2. **Use Arrow Keys** – Press ↑ or ↓ to move selected file up/down
3. **Or Click Buttons** – Use the ↑ and ↓ buttons on each tile
4. **Indices Update** – Numbers automatically refresh after reordering

### Saving the Merged Document

1. **Set Output Folder** (optional) – Default is first file's directory
2. **Click "Merge PDFs"** – Opens save dialog
3. **Choose Location & Name** – Defaults to `merged.pdf`
4. **Wait for Completion** – Status bar shows progress
5. **Verify Result** – Open the saved PDF to confirm merge

### Managing Files

| Action | How To |
|--------|--------|
| Remove Single File | Click × button on the tile |
| Remove All Files | Click "Clear All" button |
| Change Output Folder | Click "Browse..." next to Output Folder field |

## Configuration Files

### `config.yaml`

```yaml
name: "PDF Concatenator"
description: "Merge multiple PDF files into one with drag-and-drop ordering"
module: "app"
icon: "./icon.png"
enabled: true
category: "files"
type: "gui"
```

### `dependencies.yaml`

```yaml
dependencies:
  - name: ghostscript
    binary: gs
    description: "PDF processor for merging files"
    optional: false
    install_commands:
      apt: "sudo apt install -y ghostscript"
      dnf: "sudo dnf install -y ghostscript"
      brew: "brew install ghostscript"
    version_flag: "--version"
```

## Testing

Run the included unit tests:

```bash
cd apps/pdf_concatenator/tests/
python3 -m pytest test_pdf_concatenator.py -v
```

Or run directly:
```bash
python3 -m unittest tests.test_pdf_concatenator
```

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| No files appear in right panel | Check terminal for debug messages; verify ghostscript installed |
| Cannot drag & drop | Ensure files are PDFs; check file permissions |
| Reordering doesn't work | Click tile first to select (blue highlight appears) |
| Merge fails with Ghostscript error | Verify source PDFs are valid; check disk space |
| Window appears blank | Restart app; check GTK installation |

### Debug Mode

Run from terminal to see detailed logs:
```bash
python3 app.py 2>&1 | tee app_debug.log
```

Look for lines starting with `[DEBUG]` for troubleshooting.

## Technical Details

### Key Components

| Module | Responsibility |
|--------|---------------|
| `PDFTile` | UI element representing each PDF file with move/remove controls |
| `PDFConcatenatorApp` | Main window managing layout and user interactions |
| `PDFConcatenatorLogic` | Backend validation and Ghostscript invocation |

### Supported Formats

- Input: Standard PDF files (`.pdf` extension)
- Output: PDF/A-compliant merged documents
- Limitations: Cannot process encrypted or corrupted PDFs

### Performance Notes

- Handles 50+ PDFs smoothly
- Large files (>500MB) may take longer to merge
- Memory usage proportional to number of queued files

## Contributing

### Adding Features

1. Modify `logic.py` for backend changes
2. Modify `app.py` for UI changes  
3. Update `test_pdf_concatenator.py` for new functionality
4. Test thoroughly before committing

### Code Structure Guidelines

```python
# Follow this pattern for new methods:
def method_name(self, param1, param2):
    """Docstring explaining purpose."""
    # Validate inputs
    # Perform operation
    # Return result or tuple(success, message)
```

## License

This micro-app follows the licensing terms of your main project repository.

## Version History

- **1.0.0** – Initial release with drag-drop, reorder, and merge functionality

## Support

For issues or feature requests:
1. Check terminal debug output
2. Review `tests/test_pdf_concatenator.py` for expected behavior
3. Consult Ghostscript documentation for PDF-specific errors

---

**Happy PDF Merging!** 📄➡️📑