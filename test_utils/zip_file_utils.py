"""Utility functions for working with in-memory zip files from folders."""

import io
import zipfile
from pathlib import Path


def folder_to_inmemory_zip(folder_path: str) -> zipfile.ZipFile:
    """
    Read the contents of a folder and returns an in-memory ZipFile object.

    Args:
        folder_path (str): Path to the folder to zip.

    Returns:
        zipfile.ZipFile: An in-memory ZipFile containing the folder's contents.
    """
    buffer = io.BytesIO()
    folder = Path(folder_path)
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for file_path in folder.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(folder)
                zipf.write(file_path, arcname=str(arcname))
    buffer.seek(0)
    return zipfile.ZipFile(buffer, "r")


def folder_to_zip_path(
    folder_path: str,
    dest_dir: str,
    name: str = "archive.zip",
    prefix: str = "",
    extra_names: tuple = (),
) -> str:
    """
    Write the contents of a folder out as a real zip file on disk.

    Unlike ``folder_to_inmemory_zip``, this returns a *path*, which is what the
    restore pipeline takes (it opens the archive itself, so that it can support
    both zip files and plain directories).

    Args:
        folder_path (str): Path to the folder to zip.
        dest_dir (str): Directory to write the zip file into.
        name (str): File name to give the zip file.
        prefix (str): Prepended to every archive member, e.g. ``"MyLib/"``. Use
            this to build the kind of archive you get from ``zip -r x.zip MyLib``,
            where everything sits inside a single wrapper folder.
        extra_names (tuple): Extra (empty) members to add, for simulating the
            debris real archiving tools leave behind, e.g. ``"__MACOSX/._MyLib"``.

    Returns:
        str: The path of the zip file that was written.
    """
    folder = Path(folder_path)
    zip_path = Path(dest_dir) / name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for file_path in sorted(folder.rglob("*")):
            if file_path.is_file():
                arcname = prefix + str(file_path.relative_to(folder))
                zipf.write(file_path, arcname=arcname)
        for extra_name in extra_names:
            zipf.writestr(extra_name, b"")
    return str(zip_path)
