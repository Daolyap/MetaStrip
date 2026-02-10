"""Tests for the metadata engine."""

import json
import os
import struct
import tempfile

import pytest

from metastrip.engine import (
    detect_file_type,
    read_metadata,
    strip_metadata,
    edit_metadata,
    export_metadata,
    _human_size,
    _stat_metadata,
)


# ---- Helpers -------------------------------------------------------------- #

def _create_temp_file(suffix: str, content: bytes = b"") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content)
    os.close(fd)
    return path


# ---- detect_file_type ----------------------------------------------------- #

class TestDetectFileType:
    @pytest.mark.parametrize("ext,expected", [
        (".jpg", "image"), (".jpeg", "image"), (".png", "image"),
        (".tiff", "image"), (".bmp", "image"), (".gif", "image"),
        (".webp", "image"),
        (".mp3", "audio"), (".flac", "audio"), (".ogg", "audio"),
        (".wav", "audio"), (".m4a", "audio"),
        (".mp4", "video"), (".mkv", "video"), (".avi", "video"),
        (".mov", "video"),
        (".pdf", "pdf"),
        (".txt", "unknown"), (".docx", "unknown"), ("", "unknown"),
    ])
    def test_extensions(self, ext, expected):
        assert detect_file_type(f"somefile{ext}") == expected

    def test_case_insensitive(self):
        assert detect_file_type("FILE.JPG") == "image"
        assert detect_file_type("song.MP3") == "audio"


# ---- _human_size ---------------------------------------------------------- #

class TestHumanSize:
    def test_bytes(self):
        assert _human_size(500) == "500.0 B"

    def test_kilobytes(self):
        result = _human_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = _human_size(5 * 1024 * 1024)
        assert "MB" in result


# ---- _stat_metadata ------------------------------------------------------- #

class TestStatMetadata:
    def test_basic_keys(self):
        path = _create_temp_file(".txt", b"hello")
        try:
            meta = _stat_metadata(path)
            assert "File Name" in meta
            assert "File Size" in meta
            assert "Created" in meta
            assert "Modified" in meta
        finally:
            os.unlink(path)


# ---- read_metadata -------------------------------------------------------- #

class TestReadMetadata:
    def test_missing_file(self):
        result = read_metadata("/nonexistent/file.txt")
        assert "error" in result

    def test_unknown_type(self):
        path = _create_temp_file(".xyz", b"data")
        try:
            meta = read_metadata(path)
            assert "File Name" in meta
        finally:
            os.unlink(path)


# ---- export_metadata ------------------------------------------------------ #

class TestExportMetadata:
    def test_export_json(self):
        meta = {"Author": "Test", "Title": "Demo"}
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            assert export_metadata(meta, path) is True
            with open(path) as f:
                loaded = json.load(f)
            assert loaded == meta
        finally:
            os.unlink(path)


# ---- strip / edit with images (requires Pillow) --------------------------- #

class TestImageOperations:
    """These tests require Pillow to be installed."""

    @pytest.fixture()
    def png_file(self, tmp_path):
        """Create a minimal valid PNG file."""
        from PIL import Image
        p = tmp_path / "test.png"
        img = Image.new("RGB", (10, 10), color="red")
        img.save(str(p))
        return str(p)

    def test_read_image_metadata(self, png_file):
        meta = read_metadata(png_file)
        assert meta.get("Format") == "PNG"
        assert "Width" in meta

    def test_strip_image_metadata(self, png_file, tmp_path):
        out = str(tmp_path / "stripped.png")
        assert strip_metadata(png_file, out) is True
        assert os.path.isfile(out)

    def test_strip_default_output(self, png_file):
        assert strip_metadata(png_file) is True
        expected = png_file.replace(".png", "_stripped.png")
        assert os.path.isfile(expected)


# ---- PDF operations (requires PyPDF2) ------------------------------------- #

class TestPDFOperations:
    @pytest.fixture()
    def pdf_file(self, tmp_path):
        from PyPDF2 import PdfWriter
        p = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata({"/Author": "TestAuthor", "/Title": "TestTitle"})
        with open(str(p), "wb") as f:
            writer.write(f)
        return str(p)

    def test_read_pdf_metadata(self, pdf_file):
        meta = read_metadata(pdf_file)
        assert meta.get("Author") == "TestAuthor"
        assert meta.get("Pages") == "1"

    def test_strip_pdf_metadata(self, pdf_file, tmp_path):
        out = str(tmp_path / "stripped.pdf")
        assert strip_metadata(pdf_file, out) is True
        meta = read_metadata(out)
        # Author should be empty/stripped
        assert meta.get("Author", "") == ""

    def test_edit_pdf_metadata(self, pdf_file, tmp_path):
        out = str(tmp_path / "edited.pdf")
        assert edit_metadata(pdf_file, {"Author": "NewAuthor"}, out) is True
        meta = read_metadata(out)
        assert meta.get("Author") == "NewAuthor"
