"""
This module exists to abstract away the container archive format. To being with,
we are supporting Zip files and simple directories (useful for testing).
"""
from pathlib import Path

from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.zip import ZipFileSystem
from fsspec import AbstractFileSystem

def read_fs_for_path(path_str: str) -> AbstractFileSystem:
    """
    If the path_str passed in is a directory, we treat that as the root of the
    archive to be restored. Otherwise, we assume you're passing a Zip file.

    For future consideration: Using LibArchiveFileSystem would allow us to
    support tar.gz, zip, 7z, and a bunch of other archiving formats in read-only
    mode. I'm not doing it now because I'm not clear on whether the reliance on
    libarchive makes things problematic, I don't understand the performance
    implications, and I don't want to open the door on "supported archive
    formats" to include everything under the sun. But it's an intriguing option
    to consider.
    """
    path = Path(path_str)
    if path.is_dir():
        # read-only mode is not available for DirFileSystem
        return DirFileSystem(path)
    elif path.is_file() and path.suffix.lower() == ".zip":
        # read-only is the default for ZipFilesystem, but make it explicit
        return ZipFileSystem(path, mode="r")

    raise ValueError(f"Could not load path {path_str}")
