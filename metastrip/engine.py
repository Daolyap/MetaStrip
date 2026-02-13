"""Metadata engine for reading, editing, and stripping metadata from files."""

import os
import json
import shutil
import struct
import datetime

# Optional dependencies – imported lazily so the module can still be
# tested in environments where heavy libraries aren't installed.
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

try:
    from PIL import Image as PILImage
    from PIL.ExifTags import TAGS as EXIF_TAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from PyPDF2 import PdfReader, PdfWriter
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# ---- File-type detection -------------------------------------------------- #

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".wma", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}
PDF_EXTENSIONS = {".pdf"}

ALL_SUPPORTED = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | PDF_EXTENSIONS


def detect_file_type(filepath: str) -> str:
    """Return a category string for the given file path."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    return "unknown"


# ---- Generic stat metadata ------------------------------------------------ #

def _stat_metadata(filepath: str) -> dict:
    """Return basic OS-level file metadata."""
    st = os.stat(filepath)
    return {
        "File Name": os.path.basename(filepath),
        "File Size": _human_size(st.st_size),
        "Created": datetime.datetime.fromtimestamp(st.st_ctime).isoformat(sep=" ", timespec="seconds"),
        "Modified": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds"),
    }


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


# ---- Image metadata ------------------------------------------------------- #

def _read_image_metadata(filepath: str) -> dict:
    if not HAS_PIL:
        return {"error": "Pillow is not installed"}
    meta = _stat_metadata(filepath)
    try:
        img = PILImage.open(filepath)
        meta["Format"] = img.format or "Unknown"
        meta["Mode"] = img.mode
        meta["Width"], meta["Height"] = img.size

        exif_data = img.getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = EXIF_TAGS.get(tag_id, str(tag_id))
                # Convert bytes to hex string for display
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = value.hex()
                meta[tag_name] = str(value)
    except Exception as exc:
        meta["error"] = str(exc)
    return meta


def _strip_image_metadata(filepath: str, output_path: str) -> bool:
    if not HAS_PIL:
        return False
    try:
        img = PILImage.open(filepath)
        # Re-save without EXIF
        clean = PILImage.new(img.mode, img.size)
        get_data = getattr(img, "get_flattened_data", None) or img.getdata
        clean.putdata(list(get_data()))
        fmt = img.format or "PNG"
        clean.save(output_path, format=fmt)
        return True
    except Exception:
        return False


def _edit_image_metadata(filepath: str, output_path: str, updates: dict) -> bool:
    """Edit EXIF tags on an image. Keys should be EXIF tag names."""
    if not HAS_PIL:
        return False
    try:
        img = PILImage.open(filepath)
        exif_data = img.getexif()
        # Build reverse map: tag_name -> tag_id
        reverse_tags = {v: k for k, v in EXIF_TAGS.items()}
        for key, value in updates.items():
            tag_id = reverse_tags.get(key)
            if tag_id is not None:
                exif_data[tag_id] = value
        fmt = img.format or "PNG"
        img.save(output_path, format=fmt, exif=exif_data.tobytes())
        return True
    except Exception:
        return False


# ---- Audio / Video metadata ----------------------------------------------- #

def _read_audio_metadata(filepath: str) -> dict:
    if not HAS_MUTAGEN:
        return {"error": "Mutagen is not installed"}
    meta = _stat_metadata(filepath)
    try:
        audio = MutagenFile(filepath, easy=True)
        if audio is None:
            meta["error"] = "Unsupported audio format"
            return meta
        if audio.info:
            meta["Length (s)"] = f"{audio.info.length:.1f}"
            if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                meta["Bitrate"] = f"{audio.info.bitrate // 1000} kbps"
            if hasattr(audio.info, "sample_rate") and audio.info.sample_rate:
                meta["Sample Rate"] = f"{audio.info.sample_rate} Hz"
            if hasattr(audio.info, "channels") and audio.info.channels:
                meta["Channels"] = str(audio.info.channels)
        if audio.tags:
            for key, value in audio.tags.items():
                if isinstance(value, list):
                    value = "; ".join(str(v) for v in value)
                meta[key] = str(value)
    except Exception as exc:
        meta["error"] = str(exc)
    return meta


def _strip_audio_metadata(filepath: str, output_path: str) -> bool:
    if not HAS_MUTAGEN:
        return False
    try:
        shutil.copy2(filepath, output_path)
        audio = MutagenFile(output_path, easy=True)
        if audio is not None and audio.tags is not None:
            audio.delete()
            audio.save()
        return True
    except Exception:
        return False


def _edit_audio_metadata(filepath: str, output_path: str, updates: dict) -> bool:
    if not HAS_MUTAGEN:
        return False
    try:
        shutil.copy2(filepath, output_path)
        audio = MutagenFile(output_path, easy=True)
        if audio is None:
            return False
        if audio.tags is None:
            audio.add_tags()
        for key, value in updates.items():
            try:
                audio.tags[key] = value
            except Exception:
                pass
        audio.save()
        return True
    except Exception:
        return False


# ---- PDF metadata --------------------------------------------------------- #

def _read_pdf_metadata(filepath: str) -> dict:
    if not HAS_PYPDF2:
        return {"error": "PyPDF2 is not installed"}
    meta = _stat_metadata(filepath)
    try:
        reader = PdfReader(filepath)
        info = reader.metadata
        if info:
            for key in info:
                val = info[key]
                if val is not None:
                    # key is like '/Author'
                    clean_key = key.lstrip("/") if isinstance(key, str) else str(key)
                    meta[clean_key] = str(val)
        meta["Pages"] = str(len(reader.pages))
    except Exception as exc:
        meta["error"] = str(exc)
    return meta


def _strip_pdf_metadata(filepath: str, output_path: str) -> bool:
    if not HAS_PYPDF2:
        return False
    try:
        reader = PdfReader(filepath)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata({"/Producer": "", "/Creator": "", "/Author": "", "/Title": "", "/Subject": ""})
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        return False


def _edit_pdf_metadata(filepath: str, output_path: str, updates: dict) -> bool:
    if not HAS_PYPDF2:
        return False
    try:
        reader = PdfReader(filepath)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        # Preserve existing metadata and merge updates
        existing = {}
        if reader.metadata:
            for key in reader.metadata:
                val = reader.metadata[key]
                if val is not None:
                    existing[key] = str(val)
        for key, value in updates.items():
            pdf_key = key if key.startswith("/") else f"/{key}"
            existing[pdf_key] = value
        writer.add_metadata(existing)
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        return False


# ---- Public API ----------------------------------------------------------- #

def read_metadata(filepath: str) -> dict:
    """Read metadata from a file and return as a dict."""
    if not os.path.isfile(filepath):
        return {"error": f"File not found: {filepath}"}
    ftype = detect_file_type(filepath)
    if ftype == "image":
        return _read_image_metadata(filepath)
    if ftype in ("audio", "video"):
        return _read_audio_metadata(filepath)
    if ftype == "pdf":
        return _read_pdf_metadata(filepath)
    # Fallback: return basic stat metadata
    return _stat_metadata(filepath)


def strip_metadata(filepath: str, output_path: str | None = None) -> bool:
    """Strip metadata from a file. Returns True on success."""
    if not os.path.isfile(filepath):
        return False
    if output_path is None:
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}_stripped{ext}"
    ftype = detect_file_type(filepath)
    if ftype == "image":
        return _strip_image_metadata(filepath, output_path)
    if ftype in ("audio", "video"):
        return _strip_audio_metadata(filepath, output_path)
    if ftype == "pdf":
        return _strip_pdf_metadata(filepath, output_path)
    return False


def edit_metadata(filepath: str, updates: dict, output_path: str | None = None) -> bool:
    """Edit metadata fields on a file. Returns True on success."""
    if not os.path.isfile(filepath):
        return False
    if output_path is None:
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}_edited{ext}"
    ftype = detect_file_type(filepath)
    if ftype == "image":
        return _edit_image_metadata(filepath, output_path, updates)
    if ftype in ("audio", "video"):
        return _edit_audio_metadata(filepath, output_path, updates)
    if ftype == "pdf":
        return _edit_pdf_metadata(filepath, output_path, updates)
    return False


def export_metadata(metadata: dict, output_path: str) -> bool:
    """Export metadata dict to a JSON file."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception:
        return False


def import_metadata(json_path: str, filepath: str, output_path: str | None = None) -> bool:
    """Import metadata from a JSON file and apply it to the target file.

    Returns True on success.
    """
    if not os.path.isfile(json_path) or not os.path.isfile(filepath):
        return False
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            updates = json.load(f)
        if not isinstance(updates, dict):
            return False
    except Exception:
        return False
    return edit_metadata(filepath, updates, output_path)


def remove_metadata_fields(filepath: str, fields: list[str],
                           output_path: str | None = None) -> bool:
    """Remove specific metadata fields from a file. Returns True on success."""
    if not os.path.isfile(filepath):
        return False
    if output_path is None:
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}_edited{ext}"
    ftype = detect_file_type(filepath)
    if ftype == "image":
        return _remove_image_fields(filepath, output_path, fields)
    if ftype in ("audio", "video"):
        return _remove_audio_fields(filepath, output_path, fields)
    if ftype == "pdf":
        return _remove_pdf_fields(filepath, output_path, fields)
    return False


def rename_file(filepath: str, new_name: str) -> str | None:
    """Rename a file (name only, same directory). Returns new path or None."""
    if not os.path.isfile(filepath):
        return None
    directory = os.path.dirname(filepath)
    new_path = os.path.join(directory, new_name)
    if os.path.exists(new_path):
        return None
    try:
        os.rename(filepath, new_path)
        return new_path
    except Exception:
        return None


def set_file_timestamps(filepath: str, modified: str | None = None,
                        accessed: str | None = None) -> bool:
    """Set the modification and/or access time on a file.

    *modified* and *accessed* should be ISO-8601 datetime strings
    (e.g. ``"2024-01-15 10:30:00"``).  If either is *None* the
    corresponding timestamp is left unchanged.

    Returns True on success.
    """
    if not os.path.isfile(filepath):
        return False
    try:
        st = os.stat(filepath)
        atime = st.st_atime
        mtime = st.st_mtime
        if modified is not None:
            mtime = datetime.datetime.fromisoformat(modified).timestamp()
        if accessed is not None:
            atime = datetime.datetime.fromisoformat(accessed).timestamp()
        os.utime(filepath, (atime, mtime))
        return True
    except Exception:
        return False


def get_editable_fields(filepath: str) -> list[str]:
    """Return a list of common editable field names for the file type."""
    ftype = detect_file_type(filepath)
    if ftype == "image":
        return [
            "ImageDescription", "Make", "Model", "Software",
            "Artist", "Copyright", "DateTimeOriginal",
            "DateTimeDigitized", "UserComment",
        ]
    if ftype in ("audio", "video"):
        return [
            "title", "artist", "album", "albumartist", "genre",
            "date", "tracknumber", "discnumber", "composer",
            "lyricist", "conductor", "organization", "copyright",
            "description", "comment",
        ]
    if ftype == "pdf":
        return [
            "Title", "Author", "Subject", "Creator", "Producer",
            "Keywords",
        ]
    return []


# ---- Field removal helpers ------------------------------------------------ #

def _remove_image_fields(filepath: str, output_path: str,
                         fields: list[str]) -> bool:
    if not HAS_PIL:
        return False
    try:
        img = PILImage.open(filepath)
        exif_data = img.getexif()
        reverse_tags = {v: k for k, v in EXIF_TAGS.items()}
        for field in fields:
            tag_id = reverse_tags.get(field)
            if tag_id is not None and tag_id in exif_data:
                del exif_data[tag_id]
        fmt = img.format or "PNG"
        img.save(output_path, format=fmt, exif=exif_data.tobytes())
        return True
    except Exception:
        return False


def _remove_audio_fields(filepath: str, output_path: str,
                         fields: list[str]) -> bool:
    if not HAS_MUTAGEN:
        return False
    try:
        shutil.copy2(filepath, output_path)
        audio = MutagenFile(output_path, easy=True)
        if audio is None:
            return False
        if audio.tags is not None:
            for field in fields:
                if field in audio.tags:
                    del audio.tags[field]
            audio.save()
        return True
    except Exception:
        return False


def _remove_pdf_fields(filepath: str, output_path: str,
                       fields: list[str]) -> bool:
    if not HAS_PYPDF2:
        return False
    try:
        reader = PdfReader(filepath)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        existing = {}
        if reader.metadata:
            for key in reader.metadata:
                val = reader.metadata[key]
                if val is not None:
                    clean_key = key.lstrip("/") if isinstance(key, str) else str(key)
                    if clean_key not in fields:
                        existing[key] = str(val)
        writer.add_metadata(existing)
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception:
        return False
