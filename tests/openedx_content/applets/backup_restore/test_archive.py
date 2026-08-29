"""
Tests for resolving an archive location into a filesystem we can read.

These tests are strictly for the archive module, and therefore don't need Django
to run.
"""
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.zip import ZipFileSystem

from openedx_content.applets.backup_restore import archive
from openedx_content.applets.backup_restore.errors import ArchiveNotReadableError


class ReadFsForPathTest(TestCase):
    """Tests for resolving a path into a readable filesystem."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def _make_zip(self, name: str) -> Path:
        zip_path = self.tmp_path / name
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("package.toml", "[meta]\nformat_version = 1\n")
        return zip_path

    def test_directory(self):
        contents_dir = self.tmp_path / "unzipped"
        contents_dir.mkdir()
        (contents_dir / "package.toml").write_text("[meta]\nformat_version = 1\n")

        fs = archive.read_fs_for_path(str(contents_dir))

        assert isinstance(fs, DirFileSystem)
        assert fs.exists("package.toml")

    def test_zip_file(self):
        fs = archive.read_fs_for_path(str(self._make_zip("backup.zip")))

        assert isinstance(fs, ZipFileSystem)
        assert fs.exists("package.toml")

    def test_zip_file_uppercase_suffix(self):
        """Suffix matching is case-insensitive."""
        fs = archive.read_fs_for_path(str(self._make_zip("BACKUP.ZIP")))

        assert isinstance(fs, ZipFileSystem)

    def test_nonexistent_path(self):
        missing = str(self.tmp_path / "not_here.zip")

        with self.assertRaises(ArchiveNotReadableError) as ctx:
            archive.read_fs_for_path(missing)
        assert ctx.exception.path == missing

    def test_file_that_is_not_a_zip(self):
        not_a_zip = self.tmp_path / "package.toml"
        not_a_zip.write_text("[meta]\nformat_version = 1\n")

        with self.assertRaises(ArchiveNotReadableError) as ctx:
            archive.read_fs_for_path(str(not_a_zip))
        assert ctx.exception.path == str(not_a_zip)
