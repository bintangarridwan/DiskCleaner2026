"""Disk Scanner versi CLI: ringkasan per kategori, 50 file terbesar, hapus ke Recycle Bin.

Jalankan: python disk_scanner.py
Tips: jalankan terminal sebagai Administrator supaya lebih banyak folder bisa dibaca.
"""
import heapq
import os
import time

from rich.console import Console
from rich.progress import Progress
from rich.prompt import Confirm, IntPrompt
from rich.table import Table
from send2trash import send2trash

from core import LOCK, SAFE, WARN, classify, human, iter_files, list_drives, trash_many

console = Console()
TOP_N = 50
ICON = {SAFE: "🟢", WARN: "🟡", LOCK: "🔴"}


def pick_drive():
    drives = list_drives()
    t = Table(title="Pilih Disk")
    for col in ("No", "Drive", "Nama", "Total", "Terpakai", "Kosong"):
        t.add_column(col)
    for i, (d, name, u) in enumerate(drives, 1):
        t.add_row(str(i), d, name, human(u.total), human(u.used), human(u.free))
    console.print(t)
    n = IntPrompt.ask("Nomor disk (0 = keluar)", choices=[str(i) for i in range(len(drives) + 1)], show_choices=False)
    return drives[n - 1][0] if n else None


def scan(root):
    cats, top, n = {}, [], 0
    now, stats = time.time(), {"errors": 0}
    try:
        with console.status(f"Scanning {root} ...  (Ctrl+C untuk berhenti)") as status:
            for path, st in iter_files(root, stats):
                n += 1
                cat, level, note = classify(path, now - st.st_mtime)
                c = cats.setdefault(cat, {"level": level, "note": note, "count": 0, "size": 0, "paths": []})
                c["count"] += 1
                c["size"] += st.st_size
                if level == SAFE:
                    c["paths"].append(path)
                item = (st.st_size, path, st.st_mtime)
                if len(top) < TOP_N:
                    heapq.heappush(top, item)
                elif item > top[0]:
                    heapq.heapreplace(top, item)
                if n % 2000 == 0:
                    status.update(f"Scanning {root} - {n:,} file - {os.path.dirname(path)[:70]}")
    except KeyboardInterrupt:
        console.print("[yellow]Scan dihentikan, menampilkan hasil sementara.[/]")
    console.print(f"Selesai: [bold]{n:,}[/] file, {stats['errors']:,} item dilewati (tidak ada akses).")
    return cats, sorted(top, reverse=True)


def show_summary(cats):
    t = Table(title="Ringkasan per Kategori")
    for col in ("", "Kategori", "Jumlah file", "Total ukuran", "Keterangan"):
        t.add_column(col)
    for name, c in sorted(cats.items(), key=lambda kv: -kv[1]["size"]):
        t.add_row(ICON[c["level"]], name, f"{c['count']:,}", human(c["size"]), c["note"])
    console.print(t)
    console.print(f"{ICON[SAFE]} aman dihapus  {ICON[WARN]} hapus dengan hati-hati  {ICON[LOCK]} dikunci, tidak bisa dihapus")


def show_top(top):
    now = time.time()
    t = Table(title=f"Top {TOP_N} File Terbesar")
    for col in ("No", "", "Ukuran", "Kategori"):
        t.add_column(col)
    t.add_column("Path", overflow="fold")
    for i, (size, path, mtime) in enumerate(top, 1):
        cat, level, _ = classify(path, now - mtime)
        t.add_row(str(i), ICON[level], human(size), cat, path)
    console.print(t)


def delete_one(top):
    if not top:
        return console.print("Tidak ada file di daftar.")
    i = IntPrompt.ask("Nomor file (0 = batal)", choices=[str(i) for i in range(len(top) + 1)], show_choices=False)
    if not i:
        return
    size, path, mtime = top[i - 1]
    cat, level, note = classify(path, time.time() - mtime)
    if level == LOCK:
        return console.print(f"[red]{ICON[LOCK]} Dikunci: {note}. File tidak dihapus.[/]")
    if level == WARN:
        console.print(f"[yellow]Peringatan: {note}. Aplikasi/sistem terkait bisa terdampak.[/]")
    if not Confirm.ask(f"Kirim {path} ({human(size)}) ke Recycle Bin?", default=False):
        return
    try:
        send2trash(path)
        top.pop(i - 1)
        console.print("[green]Dipindah ke Recycle Bin.[/]")
    except OSError as err:
        console.print(f"[red]Gagal: {err}[/]")


def delete_category(cats):
    safe = [(name, c) for name, c in cats.items() if c["level"] == SAFE and c["paths"]]
    if not safe:
        return console.print(f"Tidak ada kategori {ICON[SAFE]} yang bisa dibersihkan.")
    for i, (name, c) in enumerate(safe, 1):
        console.print(f"{i}. {ICON[SAFE]} {name}: {len(c['paths']):,} file, {human(c['size'])}")
    i = IntPrompt.ask("Nomor kategori (0 = batal)", choices=[str(i) for i in range(len(safe) + 1)], show_choices=False)
    if not i:
        return
    name, c = safe[i - 1]
    if not Confirm.ask(f"Kirim {len(c['paths']):,} file '{name}' ke Recycle Bin?", default=False):
        return
    with Progress(console=console) as p:
        task = p.add_task("Menghapus", total=len(c["paths"]))
        failed = trash_many(c["paths"], lambda k: p.advance(task, k))
    ok = len(c["paths"]) - len(failed)
    c["paths"] = []
    console.print(f"[green]{ok:,} file dipindah ke Recycle Bin[/], {len(failed):,} dilewati (sedang dipakai). "
                  "Scan ulang untuk angka terbaru.")


def main():
    while root := pick_drive():
        cats, top = scan(root)
        show_summary(cats)
        show_top(top)
        while True:
            console.print(f"\n[bold]Menu:[/] 1 Hapus file (Top list)  2 Bersihkan kategori {ICON[SAFE]}  "
                          "3 Tampilkan ulang  4 Scan disk lain  0 Keluar")
            choice = IntPrompt.ask("Pilih", choices=["0", "1", "2", "3", "4"], show_choices=False)
            if choice == 0:
                return
            if choice == 4:
                break
            {1: lambda: delete_one(top), 2: lambda: delete_category(cats),
             3: lambda: (show_summary(cats), show_top(top))}[choice]()


if __name__ == "__main__":
    main()
