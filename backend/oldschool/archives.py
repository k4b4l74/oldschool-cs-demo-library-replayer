"""Read any demo archive: zip, rar, 7z, ace, tar/gz/bz2/xz, nested up to 3 levels.

Origin: ported on 2026-11-11 from the research wiki's ``wiki/tools/demo_catalog.py``
(member walking part), unchanged in behaviour.

* ZIP, TAR, GZ, BZ2 and XZ use the standard library; ACE uses the bundled
  ``acefile`` (``oldschool/_vendor``).
* RAR/7z/CAB/LZH/ARJ go through libarchive's ``bsdtar`` (Windows ships it as
  ``tar.exe``; under WSL the Windows binary is used through interop).
* 7-Zip or UnRAR is the fallback for what libarchive cannot decode
  (RAR 1.5/2.0 compression).

Tool locations can be forced with OLDSCHOOL_BSDTAR and OLDSCHOOL_7Z;
OLDSCHOOL_TMP sets where temporary extractions go.

``iter_members`` yields one dict per leaf member: ``{chain, name, size,
mtime, mtime_basis, read}``. Errors never raise: they are appended to the
``errors`` list, because corrupt archives are normal in old collections.
"""

from __future__ import annotations

import bz2
import gzip
import io
import lzma
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from oldschool.config import NO_WINDOW, resource_dir

ARCHIVE_EXT = {
    ".zip",
    ".rar",
    ".7z",
    ".ace",
    ".tar",
    ".tgz",
    ".tbz",
    ".tbz2",
    ".gz",
    ".bz2",
    ".xz",
    ".cab",
    ".lzh",
    ".arj",
    ".r00",
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
}
BSDTAR_EXT = {".rar", ".7z", ".cab", ".lzh", ".arj", ".r00"}
TEXT_EXT = {".txt", ".nfo", ".diz", ".ini", ".cfg", ".htm", ".html"}
MAX_DEPTH = 3
MAX_DEMO_BYTES = 512 * 1024 * 1024
MAX_TEXT_BYTES = 4096


# ------------------------------------------------------------------ bsdtar


def find_bsdtar() -> str | None:
    env = os.environ.get("OLDSCHOOL_BSDTAR")
    if env:
        return env
    candidates = []
    if os.name == "nt":
        candidates.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe"))
    candidates += [shutil.which("bsdtar") or "", "/mnt/c/Windows/System32/tar.exe"]
    for c in candidates:
        if c and os.path.exists(c):
            try:
                out = subprocess.run([c, "--version"], capture_output=True, timeout=20, **NO_WINDOW).stdout
            except OSError:
                continue
            if b"libarchive" in out:
                return c
    return None


BSDTAR = find_bsdtar()


def _native_path(path: Path) -> str:
    """Path string the bsdtar binary understands (Windows path for tar.exe
    called from WSL)."""
    if BSDTAR and BSDTAR.lower().endswith(".exe") and os.name != "nt":
        s = str(path.resolve())
        m = re.match(r"^/mnt/([a-z])(/.*)?$", s)
        if m:
            return f"{m.group(1).upper()}:" + (m.group(2) or "/").replace("/", "\\")
        return subprocess.run(["wslpath", "-w", s], capture_output=True, text=True, check=True).stdout.strip()
    return str(path)


def _read_tolerant(f, size, name, problems):
    """Read a member chunk by chunk; on a CRC/truncation error keep the bytes
    decoded so far (the demo parser copes with truncated recordings)."""
    chunks, got = [], 0
    try:
        while True:
            c = f.read(1 << 20)
            if not c:
                break
            chunks.append(c)
            got += len(c)
    except (tarfile.ReadError, OSError, EOFError) as exc:
        problems.append(f"{name}: partial read {got}/{size} bytes ({exc})")
    return b"".join(chunks)


def _bsdtar_members(path: Path, problems: list | None = None):
    """Re-stream any libarchive-readable archive as a tar on stdout and yield
    (name, size, mtime, read)."""
    problems = problems if problems is not None else []
    if not BSDTAR:
        raise RuntimeError("bsdtar/tar.exe (libarchive) not found; cannot read " + path.suffix)
    proc = subprocess.Popen(
        [BSDTAR, "-cf", "-", "--format=pax", "@" + _native_path(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **NO_WINDOW,
    )
    err = b""
    finished = False
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                f = tf.extractfile(m)
                yield m.name, m.size, m.mtime, (lambda f=f, m=m: _read_tolerant(f, m.size, m.name, problems))
        finished = True
    except tarfile.ReadError as exc:
        err = str(exc).encode()
        finished = True
    finally:
        if not finished:  # caller stopped early: do not wait on a blocked writer
            proc.kill()
        proc.stdout.close()
        rest_err = proc.stderr.read() if proc.stderr else b""
        proc.wait()
        err += rest_err
    if not finished:
        return
    if proc.returncode or err.strip():
        raise ArchiveWarning(err.decode("utf-8", "replace").strip() or f"bsdtar exit {proc.returncode}")


class ArchiveWarning(Exception):
    """Raised after members were yielded when the reader reported errors."""


def find_extractor() -> list[str] | None:
    """7-Zip or UnRAR, for formats libarchive cannot decode (RAR 1.5/2.0
    compression). Optional; set OLDSCHOOL_7Z to point at 7z/7z.exe/unrar."""
    env = os.environ.get("OLDSCHOOL_7Z")
    cands = [env] if env else []
    if os.name == "nt":  # the copy shipped with the app
        cands.append(str(resource_dir() / "tools" / "7-Zip" / "7z.exe"))
    cands += [shutil.which(n) or "" for n in ("7z", "7zz", "7za", "unrar")]
    for base in ("/mnt/c/Program Files", "/mnt/c/Program Files (x86)", r"C:\Program Files", r"C:\Program Files (x86)"):
        cands += [os.path.join(base, "7-Zip", "7z.exe"), os.path.join(base, "WinRAR", "UnRAR.exe")]
    for c in cands:
        if c and os.path.exists(c):
            return [c]
    return None


EXTRACTOR = find_extractor()


def _external_members(path: Path):
    """Extract with 7-Zip/UnRAR into a temporary directory and yield members."""
    exe = EXTRACTOR[0]
    with tempfile.TemporaryDirectory(prefix="demo_catalog_x_", dir=os.environ.get("OLDSCHOOL_TMP")) as tmp:
        out = Path(tmp)
        native_out = _native_path(out) if exe.lower().endswith(".exe") and os.name != "nt" else str(out)
        src = _native_path(path) if exe.lower().endswith(".exe") and os.name != "nt" else str(path)
        if Path(exe).name.lower().startswith("unrar"):
            sep = "\\" if (os.name == "nt" or exe.lower().endswith(".exe")) else "/"
            cmd = [exe, "x", "-y", "-p-", src, native_out + sep]
        else:
            cmd = [exe, "x", "-y", "-pnone", "-o" + native_out, src]
        res = subprocess.run(cmd, capture_output=True, **NO_WINDOW)
        for f in sorted(out.rglob("*")):
            if f.is_file():
                yield f.relative_to(out).as_posix(), f.stat().st_size, f.stat().st_mtime, (lambda f=f: f.read_bytes())
        if res.returncode:
            raise ArchiveWarning(
                f"{Path(exe).name} exit {res.returncode}: {res.stderr.decode('utf-8', 'replace').strip()[:300]}"
            )


# ---------------------------------------------------------- member walking


def _ext(name: str) -> str:
    low = name.lower()
    for double in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if low.endswith(double):
            return double
    return PurePosixPath(low).suffix


def iter_members(path: Path, data: bytes | None = None, chain: tuple = (), depth: int = 0, errors: list | None = None):
    """Yield dicts {chain, name, size, mtime, read} for every leaf member.
    ``chain`` lists the containing archive members (outermost first)."""
    errors = errors if errors is not None else []
    name = path.name if data is None else chain[-1]
    ext = _ext(name)
    try:
        if ext == ".zip":
            src = io.BytesIO(data) if data is not None else path
            try:
                with zipfile.ZipFile(src) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        mtime = datetime(*info.date_time).timestamp() if info.date_time[0] >= 1980 else None
                        yield from _leaf(
                            path,
                            chain,
                            info.filename,
                            info.file_size,
                            mtime,
                            lambda i=info, z=zf: z.read(i),
                            depth,
                            errors,
                        )
            except (NotImplementedError, zipfile.BadZipFile, EOFError, OSError) as exc:
                if BSDTAR:
                    errors.append(f"{'/'.join(chain) or path.name}: zipfile failed ({exc}); used bsdtar")
                    yield from _via_bsdtar(path, data, chain, depth, errors)
                else:
                    raise
        elif ext in BSDTAR_EXT:
            yield from _via_bsdtar(path, data, chain, depth, errors)
        elif ext == ".ace":
            from oldschool._vendor import acefile

            src = io.BytesIO(data) if data is not None else str(path)
            with acefile.open(src) as af:
                for m in af:
                    if m.is_dir():
                        continue
                    yield from _leaf(
                        path,
                        chain,
                        m.filename,
                        m.size,
                        m.datetime.timestamp() if m.datetime else None,
                        lambda m=m, a=af: a.read(m),
                        depth,
                        errors,
                    )
        elif ext in (".tar", ".tgz", ".tbz", ".tbz2", ".tar.gz", ".tar.bz2", ".tar.xz"):
            src = dict(fileobj=io.BytesIO(data)) if data is not None else dict(name=str(path))
            with tarfile.open(mode="r:*", **src) as tf:
                for m in tf:
                    if m.isfile():
                        yield from _leaf(
                            path,
                            chain,
                            m.name,
                            m.size,
                            m.mtime,
                            lambda m=m, t=tf: t.extractfile(m).read(),
                            depth,
                            errors,
                        )
        elif ext in (".gz", ".bz2", ".xz"):
            opener = {".gz": gzip.open, ".bz2": bz2.open, ".xz": lzma.open}[ext]
            raw = opener(io.BytesIO(data) if data is not None else str(path)).read()
            inner = name[: -len(ext)] or "member"
            if raw[:262][257:262] == b"ustar":
                yield from iter_members(path, raw, chain + (inner + ".tar",), depth + 1, errors)
            else:
                mt = None if data is not None else path.stat().st_mtime
                yield from _leaf(path, chain, inner, len(raw), mt, lambda r=raw: r, depth, errors)
        else:
            mt = path.stat().st_mtime if data is None else None
            yield {
                "chain": chain[:-1] if data is not None else (),
                "name": name,
                "size": len(data) if data is not None else path.stat().st_size,
                "mtime": mt,
                "mtime_basis": "filesystem" if data is None else None,
                "read": (lambda: data) if data is not None else path.read_bytes,
            }
    except ArchiveWarning as exc:
        errors.append(f"{'/'.join(chain) or path.name}: {exc}")
    except Exception as exc:  # corrupt archives are normal in old collections
        errors.append(f"{'/'.join(chain) or path.name}: {type(exc).__name__}: {exc}")


def _via_bsdtar(path, data, chain, depth, errors):
    """Stream members through bsdtar one at a time. If bsdtar fails or
    returns a short member, fall back to 7-Zip/UnRAR for whatever is missing."""
    label = "/".join(chain) or path.name
    with tempfile.TemporaryDirectory(prefix="demo_catalog_", dir=os.environ.get("OLDSCHOOL_TMP")) as tmp:
        src = path
        if data is not None:
            src = Path(tmp) / ("nested" + _ext(chain[-1]))
            src.write_bytes(data)
        done, partial, failure = set(), {}, None
        try:
            for n, size, mtime, read in _bsdtar_members(src, errors):
                raw = read()
                if len(raw) != size:
                    partial[n] = (size, mtime, raw)  # held back: 7-Zip may do better
                    continue
                done.add(n)
                yield from _leaf(path, chain, n, size, mtime, lambda r=raw: r, depth, errors)
        except (ArchiveWarning, RuntimeError, tarfile.ReadError) as exc:
            failure = exc
        if (failure or partial) and EXTRACTOR:
            errors.append(f"{label}: bsdtar failed ({failure or 'short member'}); used {Path(EXTRACTOR[0]).name}")
            failure = None
            try:
                for n, size, mtime, read in _external_members(src):
                    if n in done:
                        continue
                    raw = read()
                    partial.pop(n, None)
                    done.add(n)
                    yield from _leaf(path, chain, n, size, mtime, lambda r=raw: r, depth, errors)
            except ArchiveWarning as exc:
                failure = exc
        for n, (size, mtime, raw) in partial.items():
            yield from _leaf(path, chain, n, size, mtime, lambda r=raw: r, depth, errors)
    if failure:
        hint = (
            ""
            if EXTRACTOR
            else " (install 7-Zip or set OLDSCHOOL_7Z for archives libarchive cannot decode, e.g. RAR 2.0)"
        )
        raise ArchiveWarning(f"{failure}{hint}")


def _leaf(path, chain, name, size, mtime, read, depth, errors):
    if _ext(name) in ARCHIVE_EXT and depth < MAX_DEPTH and size and size < 4 * 1024**3:
        try:
            data = read()
        except Exception as exc:
            errors.append(f"{'/'.join(chain + (name,))}: {type(exc).__name__}: {exc}")
            return
        yield from iter_members(path, data, chain + (name,), depth + 1, errors)
        return
    yield {"chain": chain, "name": name, "size": size, "mtime": mtime, "mtime_basis": "archive_member", "read": read}


def _iso(ts):
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")
