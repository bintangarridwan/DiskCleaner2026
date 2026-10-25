"""Logika inti Disk Scanner: daftar disk, scan, klasifikasi file, dan hapus ke Recycle Bin.

Dipakai oleh disk_scanner.py (CLI) dan disk_scanner_gui.py (GUI). Tidak bergantung pada tampilan apa pun.
Self-check aturan klasifikasi: python core.py
"""
import ctypes
import os
import shutil

from send2trash import send2trash

SAFE, WARN, LOCK = "safe", "warn", "lock"
OLD_DAYS = 180
SKIP_DIRS = {"$recycle.bin", "system volume information"}
SYSTEM_FILES = {"pagefile.sys", "hiberfil.sys", "swapfile.sys", "bootmgr", "dumpstack.log.tmp"}
ROOT_LOCK = ("\\recovery\\", "\\boot\\", "\\efi\\")
BROWSERS = ("\\google\\chrome\\", "\\microsoft\\edge\\", "\\bravesoftware\\", "\\opera software\\",
            "\\vivaldi\\", "\\mozilla\\firefox\\")
COOKIE_FILES = {"cookies", "cookies-journal", "cookies.sqlite", "cookies.sqlite-wal", "cookies.sqlite-shm"}

# Prefix dari root drive (mis. C:\Windows\...), dicek berurutan, aturan pertama yang cocok menang.
RULES = [
    ("\\windows\\temp\\", "Temp", SAFE, "File sementara Windows"),
    ("\\windows\\softwaredistribution\\download\\", "Cache Windows Update", WARN, "Aman jika tidak ada update yang tertunda"),
    ("\\windows\\", "Sistem Windows", LOCK, "Dibutuhkan Windows"),
    ("\\program files", "Program terinstal", LOCK, "Uninstall lewat Settings > Apps"),
    ("\\programdata\\", "Data program", LOCK, "Data bersama aplikasi terinstal"),
]


def classify(path, age_sec):
    """Return (kategori, level, keterangan). Heuristik path/ekstensi, bukan jaminan 100%."""
    p = path.lower()
    name = os.path.basename(p)
    ext = os.path.splitext(name)[1]
    if name in SYSTEM_FILES or p[2:].startswith(ROOT_LOCK):
        return "File boot/sistem", LOCK, "Dipakai Windows untuk boot/memori"
    for key, cat, level, note in RULES:
        if p[2:].startswith(key):
            return cat, level, note
    if "\\appdata\\local\\temp\\" in p or ext in (".tmp", ".dmp"):
        return "Temp", SAFE, "File sementara/crash dump"
    if "\\appdata\\" in p:
        browser = any(b in p for b in BROWSERS)
        if browser and name in COOKIE_FILES:
            return "Cookie browser", WARN, "Akan logout dari semua website"
        # folder berakhiran "cache" (Cache, Code Cache, GPUCache, ShaderCache, INetCache, cache2, ...)
        if any(seg.endswith(("cache", "cache2")) for seg in p.split("\\")[:-1]):
            if browser:
                return "Cache browser", SAFE, "Dibuat ulang otomatis oleh browser"
            return "Cache aplikasi", SAFE, "Dibuat ulang otomatis oleh aplikasi"
    if "\\downloads\\" in p:
        if ext in (".exe", ".msi"):
            return "Installer di Downloads", SAFE, "Bisa diunduh ulang"
        if age_sec > OLD_DAYS * 86400:
            return "Downloads lama", SAFE, f"Tidak diubah >{OLD_DAYS} hari"
    if ext == ".log":
        return "Log", WARN, "Biasanya aman, kadang dibutuhkan untuk troubleshooting"
    if "\\appdata\\" in p:
        return "Data aplikasi", WARN, "Bisa mereset pengaturan/data aplikasi"
    return "File lain", WARN, "File pribadi/lainnya, cek manual"


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def list_drives():
    """Return [(drive, nama volume, usage)] untuk disk yang bisa dibaca."""
    out = []
    for d in os.listdrives():
        try:
            usage = shutil.disk_usage(d)
        except OSError:  # CD kosong, drive jaringan putus, dll.
            continue
        name = ctypes.create_unicode_buffer(261)
        if not ctypes.windll.kernel32.GetVolumeInformationW(d, name, 261, None, None, None, None, 0):
            name.value = ""
        out.append((d, name.value or "Local Disk", usage))
    return out


def iter_files(root, stats):
    """Yield (path, stat) semua file di bawah root. Junction/symlink dan folder tanpa akses dilewati."""
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if not e.is_junction() and e.name.lower() not in SKIP_DIRS:
                                stack.append(e.path)
                            continue
                        if not e.is_file(follow_symlinks=False):
                            continue
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        stats["errors"] += 1
                        continue
                    yield e.path, st
        except OSError:  # Access Denied, dll.: lewati folder
            stats["errors"] += 1


def trash_many(paths, advance=lambda n: None, chunk=200, stop=lambda: False):
    """Kirim paths ke Recycle Bin per batch; file terkunci dilewati. Berhenti di antara batch jika stop().
    Return daftar file yang gagal."""
    failed = []
    for i in range(0, len(paths), chunk):
        if stop():
            break
        part = paths[i:i + chunk]
        try:
            send2trash(part)
        except OSError:  # ada file terkunci/hilang: ulangi satu per satu yang masih ada
            for f in part:
                if os.path.exists(f):
                    try:
                        send2trash(f)
                    except OSError:
                        pass
        # cek langsung ke disk: Windows kadang melewati file terkunci tanpa melapor error
        failed += [f for f in part if os.path.exists(f)]
        advance(len(part))
    return failed


def _selftest():
    old, new = 400 * 86400, 0
    assert classify(r"C:\Windows\System32\kernel32.dll", new)[1] == LOCK
    assert classify(r"C:\Windows\Temp\x.txt", new)[1] == SAFE
    assert classify(r"C:\pagefile.sys", new)[1] == LOCK
    assert classify(r"C:\Program Files (x86)\App\a.exe", new)[1] == LOCK
    assert classify(r"C:\Users\a\AppData\Local\Temp\x.dat", new)[1] == SAFE
    assert classify(r"C:\Users\a\AppData\Local\Google\Chrome\User Data\Default\Cache\Cache_Data\f_1", new)[0] == "Cache browser"
    assert classify(r"C:\Users\a\AppData\Local\Microsoft\Edge\User Data\Default\GPUCache\data_0", new)[0] == "Cache browser"
    assert classify(r"C:\Users\a\AppData\Local\Mozilla\Firefox\Profiles\x.default\cache2\entries\AB", new)[0] == "Cache browser"
    assert classify(r"C:\Users\a\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies", new)[:2] == ("Cookie browser", WARN)
    assert classify(r"C:\Users\a\AppData\Roaming\Mozilla\Firefox\Profiles\x.default\cookies.sqlite", new)[0] == "Cookie browser"
    assert classify(r"C:\Users\a\AppData\Roaming\discord\Cache\Cache_Data\f_1", new)[0] == "Cache aplikasi"
    assert classify(r"C:\Users\a\AppData\Local\Microsoft\Windows\INetCache\IE\x.dat", new)[0] == "Cache aplikasi"
    assert classify(r"C:\Users\a\AppData\Local\Google\Chrome\User Data\Default\History", new)[0] == "Data aplikasi"
    assert classify(r"C:\Users\a\AppData\Roaming\App\settings.json", new)[1] == WARN
    assert classify(r"C:\Users\a\Downloads\setup.exe", new)[0] == "Installer di Downloads"
    assert classify(r"C:\Users\a\Downloads\doc.pdf", old)[0] == "Downloads lama"
    assert classify(r"C:\Users\a\Downloads\doc.pdf", new)[1] == WARN
    assert classify(r"D:\Data\foto.jpg", new)[1] == WARN
    assert classify(r"D:\Project\app\windows\runner\main.cpp", new)[1] == WARN
    print("OK")


if __name__ == "__main__":
    _selftest()
