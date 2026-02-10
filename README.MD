# MetaStrip

A modern, cross-platform GUI application to **view**, **strip**, and **edit** file metadata.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **View metadata** – See all embedded metadata in images, audio, video, and PDF files.
- **Strip metadata** – Remove all metadata for privacy with one click.
- **Edit metadata** – Modify individual metadata fields and save.
- **Export to JSON** – Export metadata to a JSON file for analysis.
- **Modern dark/light theme** – Powered by customtkinter with system, dark, and light themes.
- **Cross-platform** – Runs on Windows, macOS, and Linux.

## Supported File Types

| Category | Extensions |
|----------|------------|
| Images | `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.bmp`, `.gif`, `.webp` |
| Audio | `.mp3`, `.flac`, `.ogg`, `.wav`, `.m4a`, `.aac`, `.wma`, `.opus` |
| Video | `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm` |
| PDF | `.pdf` |

## Installation

### From source

```bash
# Clone the repository
git clone https://github.com/Daolyap/MetaStrip.git
cd MetaStrip

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m metastrip
```

### Pre-built binaries

Download the latest build from the [Actions](../../actions) tab (artifacts for Windows, macOS, and Linux).

## Usage

1. Click **Open File** to select a file.
2. View all metadata fields in the scrollable table.
3. **Edit** any field directly in the table and click **Save Edits**.
4. Click **Strip Metadata** to create a clean copy with all metadata removed.
5. Click **Export JSON** to save the metadata to a JSON file.
6. Use the **Theme** selector to switch between System, Dark, and Light themes.

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt pytest

# Run tests
pytest tests/ -v
```

## Building Executables

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name MetaStrip metastrip/__main__.py
```

## License

MIT License
