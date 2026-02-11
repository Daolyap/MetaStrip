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
    import_metadata,
    remove_metadata_fields,
    rename_file,
    set_file_timestamps,
    get_editable_fields,
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


# ---- import_metadata ------------------------------------------------------ #

class TestImportMetadata:
    @pytest.fixture()
    def pdf_file(self, tmp_path):
        from PyPDF2 import PdfWriter
        p = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata({"/Author": "Original"})
        with open(str(p), "wb") as f:
            writer.write(f)
        return str(p)

    def test_import_from_json(self, pdf_file, tmp_path):
        json_path = str(tmp_path / "meta.json")
        with open(json_path, "w") as f:
            json.dump({"Author": "Imported"}, f)
        out = str(tmp_path / "imported.pdf")
        assert import_metadata(json_path, pdf_file, out) is True
        meta = read_metadata(out)
        assert meta.get("Author") == "Imported"

    def test_import_missing_json(self, pdf_file, tmp_path):
        assert import_metadata("/nonexistent.json", pdf_file) is False

    def test_import_missing_target(self, tmp_path):
        json_path = str(tmp_path / "meta.json")
        with open(json_path, "w") as f:
            json.dump({"Author": "X"}, f)
        assert import_metadata(json_path, "/nonexistent.pdf") is False

    def test_import_invalid_json(self, pdf_file, tmp_path):
        bad = str(tmp_path / "bad.json")
        with open(bad, "w") as f:
            f.write("[1,2,3]")
        assert import_metadata(bad, pdf_file) is False


# ---- remove_metadata_fields ---------------------------------------------- #

class TestRemoveMetadataFields:
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

    def test_remove_pdf_field(self, pdf_file, tmp_path):
        out = str(tmp_path / "removed.pdf")
        assert remove_metadata_fields(pdf_file, ["Author"], out) is True
        meta = read_metadata(out)
        assert "Author" not in meta or meta.get("Author") == ""
        assert meta.get("Title") == "TestTitle"

    def test_remove_missing_file(self):
        assert remove_metadata_fields("/nonexistent.pdf", ["Author"]) is False

    def test_remove_default_output(self, pdf_file):
        assert remove_metadata_fields(pdf_file, ["Author"]) is True
        expected = pdf_file.replace(".pdf", "_edited.pdf")
        assert os.path.isfile(expected)

    def test_remove_unknown_type(self, tmp_path):
        p = str(tmp_path / "file.xyz")
        with open(p, "w") as f:
            f.write("data")
        assert remove_metadata_fields(p, ["key"]) is False


# ---- rename_file ---------------------------------------------------------- #

class TestRenameFile:
    def test_rename_success(self, tmp_path):
        p = str(tmp_path / "old.txt")
        with open(p, "w") as f:
            f.write("data")
        result = rename_file(p, "new.txt")
        assert result is not None
        assert os.path.basename(result) == "new.txt"
        assert os.path.isfile(result)
        assert not os.path.isfile(p)

    def test_rename_missing_file(self):
        assert rename_file("/nonexistent.txt", "new.txt") is None

    def test_rename_target_exists(self, tmp_path):
        p1 = str(tmp_path / "a.txt")
        p2 = str(tmp_path / "b.txt")
        with open(p1, "w") as f:
            f.write("1")
        with open(p2, "w") as f:
            f.write("2")
        assert rename_file(p1, "b.txt") is None


# ---- set_file_timestamps ------------------------------------------------- #

class TestSetFileTimestamps:
    def test_set_modified(self, tmp_path):
        p = str(tmp_path / "ts.txt")
        with open(p, "w") as f:
            f.write("data")
        assert set_file_timestamps(p, modified="2020-06-15 12:00:00") is True
        st = os.stat(p)
        import datetime
        mtime = datetime.datetime.fromtimestamp(st.st_mtime)
        assert mtime.year == 2020
        assert mtime.month == 6

    def test_set_accessed(self, tmp_path):
        p = str(tmp_path / "ts2.txt")
        with open(p, "w") as f:
            f.write("data")
        assert set_file_timestamps(p, accessed="2021-03-01 08:00:00") is True

    def test_missing_file(self):
        assert set_file_timestamps("/nonexistent.txt", modified="2020-01-01") is False

    def test_invalid_format(self, tmp_path):
        p = str(tmp_path / "ts3.txt")
        with open(p, "w") as f:
            f.write("data")
        assert set_file_timestamps(p, modified="not-a-date") is False

    def test_no_changes(self, tmp_path):
        p = str(tmp_path / "ts4.txt")
        with open(p, "w") as f:
            f.write("data")
        assert set_file_timestamps(p) is True


# ---- get_editable_fields -------------------------------------------------- #

class TestGetEditableFields:
    def test_image_fields(self):
        fields = get_editable_fields("photo.jpg")
        assert "Artist" in fields
        assert "Copyright" in fields

    def test_audio_fields(self):
        fields = get_editable_fields("song.mp3")
        assert "title" in fields
        assert "artist" in fields

    def test_pdf_fields(self):
        fields = get_editable_fields("doc.pdf")
        assert "Author" in fields
        assert "Title" in fields

    def test_unknown_fields(self):
        assert get_editable_fields("file.xyz") == []
