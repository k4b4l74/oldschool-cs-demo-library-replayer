"""Bring the game window in front of the browser once it appears.

Windows only lets the program the user is working in (the browser) choose
which window comes to the front. The app's server runs in the background, so
a game it starts can open *behind* the browser: the CS 1.0-1.5 clients then
grab the mouse while the page stays visible (seen 2026-11-12). After
starting hl.exe, the app waits for its window and brings it to the front.

Native Windows (the installed app) uses the Windows API through ctypes. Under
WSL (development) the same steps run in a PowerShell helper.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import time
from pathlib import PureWindowsPath

log = logging.getLogger("oldschool.play")

WAIT_SECONDS = 40.0  # old engines can take a while to open their window
STABLE_SECONDS = 3.0  # done once the game has stayed in front this long
POLL = 0.25


def bring_to_front(image: str = "hl.exe", wait: float = WAIT_SECONDS, stable: float = STABLE_SECONDS) -> bool:
    """Wait for a window of `image` and keep it in front until it stays there.

    Returns True when the window was in front for `stable` seconds."""
    from oldschool.player.platform import IS_WINDOWS, IS_WSL

    try:
        if IS_WINDOWS:
            return _native(image, wait, stable)
        if IS_WSL:
            return _powershell(image, wait, stable)
    except Exception:  # never let this break Play
        log.exception("could not bring %s to the front", image)
    return False


# --- native Windows -------------------------------------------------------


def _native(image: str, wait: float, stable: float) -> bool:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]

    names: dict[int, str] = {}

    def process_name(pid: int) -> str:
        if pid not in names:
            name = ""
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(buf))
                if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    name = PureWindowsPath(buf.value).name.lower()
                kernel32.CloseHandle(handle)
            names[pid] = name
        return names[pid]

    def game_window() -> int | None:
        found: list[tuple[int, int]] = []

        def visit(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if process_name(pid.value) == image.lower():
                    r = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                    found.append(((r.right - r.left) * (r.bottom - r.top), hwnd))
            return True

        user32.EnumWindows(enum_proc(visit), 0)
        return max(found)[1] if found else None  # the biggest one: the game, not a splash

    def force(hwnd: int) -> None:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        front = user32.GetForegroundWindow()
        mine = kernel32.GetCurrentThreadId()
        theirs = user32.GetWindowThreadProcessId(front, None) if front else 0
        attached = bool(theirs and theirs != mine and user32.AttachThreadInput(mine, theirs, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(mine, theirs, False)
        if user32.GetForegroundWindow() != hwnd:  # a key press lifts the foreground lock
            user32.keybd_event(0x12, 0, 0, 0)  # Alt down
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)  # Alt up

    return _loop(game_window, lambda: user32.GetForegroundWindow(), force, wait, stable)


def _loop(find, front, force, wait: float, stable: float, clock=time.monotonic, sleep=time.sleep) -> bool:
    """Shared steps: find the window, push it to the front, stop once it stays."""
    deadline = clock() + wait
    since = None
    while clock() < deadline:
        hwnd = find()
        if hwnd:
            if front() == hwnd:
                since = since if since is not None else clock()
                if clock() - since >= stable:
                    return True
            else:
                since = None
                force(hwnd)
        sleep(POLL)
    return False


# --- WSL (development) ----------------------------------------------------

_PS = r"""
$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class OldschoolFront {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
  public static void Force(IntPtr h) {
    if (IsIconic(h)) ShowWindow(h, 9);
    IntPtr front = GetForegroundWindow();
    uint mine = GetCurrentThreadId();
    uint theirs = front == IntPtr.Zero ? 0 : GetWindowThreadProcessId(front, IntPtr.Zero);
    bool attached = theirs != 0 && theirs != mine && AttachThreadInput(mine, theirs, true);
    BringWindowToTop(h); SetForegroundWindow(h);
    if (attached) AttachThreadInput(mine, theirs, false);
    if (GetForegroundWindow() != h) { keybd_event(0x12, 0, 0, UIntPtr.Zero); SetForegroundWindow(h); keybd_event(0x12, 0, 2, UIntPtr.Zero); }
  }
}
'@
$name = [IO.Path]::GetFileNameWithoutExtension($env:OLDSCHOOL_FRONT_IMAGE)
$deadline = (Get-Date).AddSeconds([double]$env:OLDSCHOOL_FRONT_WAIT)
$stable = [double]$env:OLDSCHOOL_FRONT_STABLE
$since = $null
while ((Get-Date) -lt $deadline) {
  $h = Get-Process -Name $name -ErrorAction SilentlyContinue |
       Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } |
       Select-Object -First 1 -ExpandProperty MainWindowHandle
  if ($h) {
    if ([OldschoolFront]::GetForegroundWindow() -eq $h) {
      if ($since -eq $null) { $since = Get-Date }
      if (((Get-Date) - $since).TotalSeconds -ge $stable) { 'front'; exit 0 }
    } else { $since = $null; [OldschoolFront]::Force($h) }
  }
  Start-Sleep -Milliseconds 250
}
'timeout'
"""


def _powershell(image: str, wait: float, stable: float) -> bool:
    env = dict(os.environ)
    env.update(
        OLDSCHOOL_FRONT_IMAGE=image,
        OLDSCHOOL_FRONT_WAIT=str(wait),
        OLDSCHOOL_FRONT_STABLE=str(stable),
        WSLENV=":".join(
            filter(
                None,
                [os.environ.get("WSLENV"), "OLDSCHOOL_FRONT_IMAGE", "OLDSCHOOL_FRONT_WAIT", "OLDSCHOOL_FRONT_STABLE"],
            )
        ),
    )
    encoded = base64.b64encode(_PS.encode("utf-16-le")).decode()  # stdin scripts break on here-strings
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=wait + 30,
        env=env,
    )
    if out.returncode:
        log.warning("bring to front failed: %s", out.stderr.strip()[-500:])
    return out.stdout.strip().endswith("front")
