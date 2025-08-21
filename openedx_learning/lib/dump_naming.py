"""
This module provides utilities for generating safe and consistent filenames for
dumping learning package content.

Examples
print(hash_slugify_filename("My:Component"))     # → my_component_a12f4c.toml
print(hash_slugify_filename("Math/Algebra+V2"))  # → math_algebra+v2_8d31a.toml
print(hash_slugify_filename("User@Library#1"))   # → user@library#1_c9a0f.toml
"""
import hashlib
import re
from typing import Optional

# Windows-invalid filename characters
INVALID_CHARS = r'<>:"/\\|?*'


def safe_slugify(value: str, separator: str = "_") -> str:
    """
    Make a filesystem-safe slug:
    - Lowercase
    - Replace only invalid filename characters with separator
    - Collapse multiple separators
    - Strip leading/trailing separators
    """
    value = value.lower()
    value = re.sub(f"[{re.escape(INVALID_CHARS)}]", separator, value)
    value = re.sub(f"{separator}+", separator, value)  # collapse duplicates
    return value.strip(separator)


def hash_slugify_filename(identifier: str, ext: Optional[str] = "") -> str:
    """
    Hybrid filename = slugified identifier + short hash.
    Keeps most special characters intact except filesystem-invalid ones.
    """
    slug = safe_slugify(identifier)
    short_hash = hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:5]
    return f"{slug}_{short_hash}{ext}"
