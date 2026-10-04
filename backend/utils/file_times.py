"""
Keep file dates (modified, accessed and, on Windows, created) when files are derived
from or rewritten over a photo, so archives sorted by file date keep their order.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# FILETIME counts 100 ns intervals since 1601-01-01; Unix time starts at 1970-01-01
_FILETIME_UNIX_EPOCH = 116444736000000000
_FILE_WRITE_ATTRIBUTES = 0x0100
_FILE_SHARE_ALL = 0x07
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000


def _set_windows_creation_time(path: Path, birthtime_ns: int):
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.SetFileTime.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    ticks = birthtime_ns // 100 + _FILETIME_UNIX_EPOCH
    created = wintypes.FILETIME(ticks & 0xFFFFFFFF, ticks >> 32)

    handle = kernel32.CreateFileW(
        str(path), _FILE_WRITE_ATTRIBUTES, _FILE_SHARE_ALL, None,
        _OPEN_EXISTING, _FILE_FLAG_BACKUP_SEMANTICS, None
    )
    if handle in (None, wintypes.HANDLE(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel32.SetFileTime(handle, ctypes.byref(created), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def apply_file_times(path: Path, times: os.stat_result):
    """Set `path`'s dates to those recorded in `times` (a stat taken earlier). Never fails."""
    try:
        os.utime(path, ns=(times.st_atime_ns, times.st_mtime_ns))
        birthtime_ns = getattr(times, "st_birthtime_ns", None)
        if os.name == "nt" and birthtime_ns:
            _set_windows_creation_time(Path(path), birthtime_ns)
    except Exception as e:
        logger.warning(f"Could not keep file dates on {path}: {e}")


def copy_file_times(source: Path, target: Path):
    """Give `target` the same file dates as `source`"""
    apply_file_times(target, Path(source).stat())
