"""Disk Scanner GUI: scan disk, centang file per kategori/folder/file, kirim ke Recycle Bin.

Jalankan: python disk_scanner_gui.py   (sebagai Administrator supaya lebih banyak folder terbaca)
Klik kotak/nama atau tekan Spasi untuk mencentang. Panah kanan/kiri untuk buka/tutup folder.
"""
import ctypes
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from core import LOCK, SAFE, WARN, classify, human, iter_files, list_drives, trash_many

# Palet warna; teks utama dan teks muted lolos kontras 4.5:1 di latar putih
BG, CARD, TEXT, MUTED, BORDER = "#F8FAFC", "#FFFFFF", "#0F172A", "#64748B", "#E4E7EB"
PRIMARY, SUCCESS, SELECT = "#1E3A5F", "#16A34A", "#DBEAFE"
LEVEL = {SAFE: ("Aman", "#059669"), WARN: ("Hati-hati", "#D97706"), LOCK: ("Terkunci", "#94A3B8")}
FONT, BOLD = ("Segoe UI", 10), ("Segoe UI Semibold", 10)


def make_icon(kind, state, zoom):
    """Ikon 38x16: checkbox (state 0/1/2, None = tanpa checkbox) + folder/file/titik level."""
    img = tk.PhotoImage(width=38, height=16)

    def rect(x0, y0, x1, y1, color):
        img.put(color, to=(x0, y0, x1, y1))

    if state is not None:
        filled = state > 0
        rect(1, 1, 15, 15, PRIMARY if filled else "#94A3B8")
        rect(2, 2, 14, 14, PRIMARY if filled else CARD)
        if state == 1:
            rect(4, 7, 12, 9, CARD)
        elif state == 2:
            for x, y in ((4, 7), (5, 8), (6, 9), (7, 8), (8, 7), (9, 6), (10, 5), (11, 4)):
                rect(x, y, x + 1, y + 2, CARD)
    if kind == "folder":
        rect(21, 3, 27, 5, "#E8A317")
        rect(21, 5, 36, 14, "#FFC83D")
        rect(21, 5, 36, 6, "#E8A317")
    elif kind == "file":
        rect(23, 1, 34, 15, "#94A3B8")
        rect(24, 2, 33, 14, CARD)
        for y in (5, 8, 11):
            rect(26, y, 31, y + 1, "#CBD5E1")
    else:  # titik warna level kategori
        color = LEVEL[kind][1]
        for y in range(16):
            for x in range(20, 38):
                if (x - 28) ** 2 + (y - 8) ** 2 <= 20:
                    rect(x, y, x + 1, y + 1, color)
    return img.zoom(zoom) if zoom > 1 else img


class App:
    def __init__(self, root):
        self.root = root
        scale = root.winfo_fpixels("1i") / 96
        px = lambda n: int(n * scale)  # noqa: E731
        root.title("Disk Scanner")
        root.geometry(f"{px(1150)}x{px(700)}")
        root.minsize(px(1000), px(450))
        root.configure(bg=BG)
        self.data, self.nodes, self.checked = {}, {}, {}  # nodes: iid -> (cat, dir, name, size)
        self.stop = threading.Event()
        zoom = max(1, round(scale))
        self.icons = {(k, s): make_icon(k, s, zoom) for k in ("folder", "file", SAFE, WARN) for s in (0, 1, 2)}
        self.icons[(LOCK, None)] = make_icon(LOCK, None, zoom)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=FONT, background=BG, foreground=TEXT, bordercolor=BORDER, focuscolor=PRIMARY)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 15))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Bold.TLabel", font=BOLD)
        style.configure("TButton", padding=(px(14), px(6)), background=CARD)
        style.map("TButton", background=[("disabled", BG), ("active", "#F1F5F9")], foreground=[("disabled", MUTED)])
        style.configure("TCombobox", padding=(px(8), px(5)), arrowsize=px(14), arrowcolor=MUTED)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)], background=[("active", "#F1F5F9"), ("readonly", CARD)],
                  selectbackground=[("readonly", CARD)], selectforeground=[("readonly", TEXT)],
                  bordercolor=[("focus", PRIMARY)], foreground=[("disabled", MUTED)])
        root.option_add("*TCombobox*Listbox.font", FONT)
        root.option_add("*TCombobox*Listbox.selectBackground", SELECT)
        root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        style.configure("Treeview", background=CARD, fieldbackground=CARD, rowheight=px(28), borderwidth=0)
        style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
        style.configure("Treeview.Heading", font=BOLD, background="#F1F5F9", relief="flat", padding=(px(6), px(5)))
        style.map("Treeview.Heading", background=[("active", "#E2E8F0")])
        style.configure("Horizontal.TProgressbar", background=SUCCESS, lightcolor=SUCCESS, darkcolor=SUCCESS,
                        troughcolor="#E2E8F0", bordercolor="#E2E8F0")

        head = ttk.Frame(root, padding=(px(16), px(14), px(16), px(4)))
        head.pack(fill="x")
        ttk.Label(head, text="Disk Scanner", style="Title.TLabel").pack(anchor="w")

        bar = ttk.Frame(root, padding=(px(16), px(8)))
        bar.pack(fill="x")
        ttk.Label(bar, text="Disk").pack(side="left")
        self.drives = [(d, f"{name} ({d[:2]})  ·  {human(u.free)} kosong dari {human(u.total)}")
                       for d, name, u in list_drives()]
        self.drive = ttk.Combobox(bar, state="readonly", width=38, font=FONT, values=[label for _, label in self.drives])
        self.drive.current(0)
        self.drive.pack(side="left", padx=px(8))
        self.scan_btn = ttk.Button(bar, text="Start", command=self.toggle_scan)
        self.scan_btn.pack(side="left")
        self.del_btn = ttk.Button(bar, text="Delete To Recycle Bin", width=21, command=self.toggle_delete)
        self.del_btn.pack(side="right")
        self.none_btn = ttk.Button(bar, text="Unselect All", command=lambda: self.set_all(False))
        self.none_btn.pack(side="right", padx=px(8))
        self.all_btn = ttk.Button(bar, text="Select All", command=lambda: self.set_all(True))
        self.all_btn.pack(side="right")

        frame = tk.Frame(root, bg=BORDER, padx=1, pady=1)  # garis tepi tipis di sekitar tabel
        frame.pack(fill="both", expand=True, padx=px(16))
        cols = ("size", "count", "status", "note")
        self.tree = ttk.Treeview(frame, columns=cols)
        for col, title, width, anchor in (("#0", "Nama", 520, "w"), ("size", "Ukuran", 90, "e"),
                                          ("count", "File", 80, "e"), ("status", "Status", 90, "w"),
                                          ("note", "Keterangan", 330, "w")):
            self.tree.heading(col, text=title, anchor=anchor)
            self.tree.column(col, width=px(width), anchor=anchor, stretch=col in ("#0", "note"))
        self.tree.tag_configure("cat", font=BOLD)
        self.tree.tag_configure("lock", foreground=MUTED)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", lambda e: (self.toggle(self.tree.focus()), "break")[1])
        self.tree.bind("<<TreeviewOpen>>", self.on_open)

        foot = ttk.Frame(root, padding=(px(16), px(10)))
        foot.pack(fill="x")
        self.bar = ttk.Progressbar(foot, mode="determinate")
        self.bar.pack(fill="x", pady=(0, px(8)))
        self.status = tk.StringVar(value="Total dicentang: 0 file")
        self.selection = tk.StringVar(value=human(0))
        # label kanan di-pack duluan supaya tidak terpotong oleh teks status yang panjang
        ttk.Label(foot, textvariable=self.selection, style="Bold.TLabel").pack(side="right")
        ttk.Label(foot, textvariable=self.status, style="Muted.TLabel").pack(side="left")
        self.busy(False)

    def busy(self, on, scanning=False, deleting=False):
        self.is_busy = on
        for w in (self.all_btn, self.none_btn):
            w.configure(state="disabled" if on else "normal")
        self.scan_btn.configure(text="Stop" if scanning else "Start",
                                state="normal" if scanning or not on else "disabled")
        self.del_btn.configure(text="Stop Delete" if deleting else "Delete To Recycle Bin",
                               state="normal" if deleting or not on else "disabled")
        self.drive.configure(state="disabled" if on else "readonly")
        self.bar.stop()
        if scanning:
            self.bar.configure(mode="indeterminate")
            self.bar.start(15)
        else:
            self.bar.configure(mode="determinate", value=0)

    # ---------- scan ----------
    def toggle_scan(self):
        if self.scan_btn["text"] == "Stop":
            self.stop.set()
        else:
            self.start_scan()

    def start_scan(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        self.checked.clear()
        self.update_selection()
        self.stop.clear()
        self.job = {"n": 0, "path": "", "done": False}
        self.busy(True, scanning=True)
        root_path = self.drives[self.drive.current()][0]
        threading.Thread(target=self.scan_worker, args=(root_path, self.job), daemon=True).start()
        self.poll_scan()

    def scan_worker(self, root_path, job):
        data, now, stats = {}, time.time(), {"errors": 0}
        for path, st in iter_files(root_path, stats):
            if self.stop.is_set():
                break
            cat, level, note = classify(path, now - st.st_mtime)
            c = data.setdefault(cat, {"level": level, "note": note, "count": 0, "size": 0, "folders": {}})
            c["count"] += 1
            c["size"] += st.st_size
            if level != LOCK:
                # ponytail: semua file Aman/Hati-hati disimpan di memori (~200 B/file), cukup untuk jutaan file
                d, name = os.path.split(path)
                c["folders"].setdefault(d, []).append((name, st.st_size, st.st_mtime))
            job["n"] += 1
            if job["n"] % 500 == 0:
                job["path"] = path
        job.update(data=data, errors=stats["errors"], done=True)

    def poll_scan(self):
        j = self.job
        if not j["done"]:
            self.status.set(f"Scanning... {j['n']:,} file   {j['path'][:90]}")
            self.root.after(200, self.poll_scan)
            return
        self.data = j["data"]
        self.busy(False)
        self.update_selection()
        self.fill_tree()
        title = "Scan dihentikan" if self.stop.is_set() else "Scan selesai"
        total = sum(c["size"] for c in self.data.values())
        messagebox.showinfo(title, f"{j['n']:,} file ter-scan\nTotal ukuran: {human(total)}\n"
                                   f"{j['errors']:,} item dilewati (tidak ada akses)")

    # ---------- tree ----------
    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        # yang bisa dicentang di atas, Terkunci di bawah; masing-masing A-Z
        for cat, c in sorted(self.data.items(), key=lambda kv: (kv[1]["level"] == LOCK, kv[0].lower())):
            values = (human(c["size"]), f"{c['count']:,}", LEVEL[c["level"]][0], c["note"])
            if c["level"] == LOCK:  # tampil sebagai info saja, tidak bisa dicentang
                self.tree.insert("", "end", text=f" {cat}", image=self.icons[(LOCK, None)],
                                 values=values, tags=("cat", "lock"))
                continue
            iid = self.tree.insert("", "end", values=values, tags=("cat",))
            self.nodes[iid] = (cat, None, None, None)
            self.tree.insert(iid, "end")  # placeholder supaya bisa di-expand; isi dimuat saat dibuka
            self.refresh(iid)

    def on_open(self, _):
        iid = self.tree.focus()
        kids = self.tree.get_children(iid)
        if len(kids) == 1 and kids[0] not in self.nodes:
            self.tree.delete(kids[0])
            self.populate(iid)

    def populate(self, iid):
        cat, d, _, _ = self.nodes[iid]
        status = LEVEL[self.data[cat]["level"]][0]
        folders = self.data[cat]["folders"]
        if d is None:
            # ponytail: semua folder kategori dimasukkan sekaligus, terasa lambat jika >20 ribu folder
            for dd in sorted(folders, key=str.lower):
                size, n = sum(f[1] for f in folders[dd]), len(folders[dd])
                kid = self.tree.insert(iid, "end", values=(human(size), f"{n:,}", status, ""))
                self.nodes[kid] = (cat, dd, None, None)
                self.tree.insert(kid, "end")
                self.refresh(kid)
        else:
            for name, size, mtime in sorted(folders[d], key=lambda f: f[0].lower()):
                note = "Diubah " + time.strftime("%Y-%m-%d", time.localtime(mtime))
                kid = self.tree.insert(iid, "end", values=(human(size), "", status, note))
                self.nodes[kid] = (cat, d, name, size)
                self.refresh(kid)

    def files_of(self, node):
        cat, d, name, size = node
        if name is not None:
            yield os.path.join(d, name), size
            return
        folders = self.data[cat]["folders"]
        for dd in [d] if d is not None else folders:
            for n, s, _ in folders[dd]:
                yield os.path.join(dd, n), s

    def refresh(self, iid):
        cat, d, name, _ = node = self.nodes[iid]
        total = hit = 0
        for p, _ in self.files_of(node):
            total += 1
            hit += p in self.checked
        state = 0 if not hit else 2 if hit == total else 1
        kind = "file" if name else "folder" if d else self.data[cat]["level"]
        label = name or d or cat
        if kind == "folder" and len(label) > 55:  # bagian akhir path paling penting
            label = "…" + label[-54:]
        self.tree.item(iid, text=f" {label}", image=self.icons[(kind, state)])

    # ---------- centang ----------
    def on_click(self, e):
        if self.tree.identify_region(e.x, e.y) == "tree" and "indicator" not in self.tree.identify_element(e.x, e.y):
            self.toggle(self.tree.identify_row(e.y))

    def toggle(self, iid):
        if iid not in self.nodes or self.is_busy:  # centang dikunci selama scan/hapus
            return
        node = self.nodes[iid]
        files = list(self.files_of(node))
        if all(p in self.checked for p, _ in files):
            for p, _ in files:
                self.checked.pop(p, None)
        else:
            for p, s in files:
                self.checked[p] = (s, node[0])
        stack = [iid]
        while stack:  # anak yang sudah dimuat
            i = stack.pop()
            if i in self.nodes:
                self.refresh(i)
                stack.extend(self.tree.get_children(i))
        parent = self.tree.parent(iid)
        while parent:  # induk
            self.refresh(parent)
            parent = self.tree.parent(parent)
        self.update_selection()

    def set_all(self, on):
        self.checked.clear()
        if on:  # semua kategori yang bisa dicentang (Aman + Hati-hati)
            for iid in self.tree.get_children():
                if iid in self.nodes:
                    for p, s in self.files_of(self.nodes[iid]):
                        self.checked[p] = (s, self.nodes[iid][0])
        for iid in self.nodes:
            self.refresh(iid)
        self.update_selection()

    def update_selection(self):
        self.status.set(f"Total dicentang: {len(self.checked):,} file")
        self.selection.set(human(sum(s for s, _ in self.checked.values())))

    # ---------- hapus ----------
    def toggle_delete(self):
        if self.del_btn["text"] == "Stop Delete":
            self.stop.set()
        else:
            self.delete_checked()

    def delete_checked(self):
        if not self.checked:
            messagebox.showinfo("Disk Scanner", "Belum ada file yang dicentang.")
            return
        size = sum(s for s, _ in self.checked.values())
        msg = f"Kirim {len(self.checked):,} file ({human(size)}) ke Recycle Bin?"
        warn = sorted({cat for _, cat in self.checked.values() if self.data[cat]["level"] == WARN})
        if warn:
            msg += ("\n\nPERINGATAN: termasuk file 'Hati-hati' dari: " + ", ".join(warn) +
                    ".\nAplikasi/sistem terkait bisa terdampak (pengaturan ter-reset, data aplikasi hilang).")
        if not messagebox.askyesno("Konfirmasi", msg, icon="warning", default="no"):
            return
        paths = list(self.checked)
        self.job = {"n": 0, "total": len(paths), "paths": paths, "done": False}
        self.stop.clear()
        self.busy(True, deleting=True)
        self.bar.configure(maximum=len(paths))
        # ~100 langkah supaya progress bergerak; maks 50 file per batch supaya Stop cepat berlaku
        chunk = max(1, min(50, len(paths) // 100))

        def work():
            self.job["failed"] = set(trash_many(paths, lambda k: self.job.update(n=self.job["n"] + k),
                                                chunk, self.stop.is_set))
            self.job["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self.poll_delete()

    def poll_delete(self):
        j = self.job
        if not j["done"]:
            self.bar.configure(value=j["n"])
            self.status.set(f"Menghapus... {j['n']:,} / {j['total']:,} file")
            self.root.after(200, self.poll_delete)
            return
        processed = j["paths"][:j["n"]]  # file yang belum diproses tetap dicentang
        gone, freed = {}, 0
        for p in processed:
            size, cat = self.checked.pop(p)
            if p in j["failed"]:
                continue
            d, name = os.path.split(p)
            gone.setdefault((cat, d), set()).add(name)
            self.data[cat]["count"] -= 1
            self.data[cat]["size"] -= size
            freed += size
        for (cat, d), names in gone.items():
            folders = self.data[cat]["folders"]
            folders[d] = [f for f in folders[d] if f[0] not in names]
            if not folders[d]:
                del folders[d]
        self.data = {k: c for k, c in self.data.items() if c["count"] > 0}
        ok, left = len(processed) - len(j["failed"]), j["total"] - len(processed)
        self.busy(False)
        self.fill_tree()
        self.update_selection()
        msg = f"{ok:,} file berhasil dipindah ke Recycle Bin\nRuang dibebaskan: {human(freed)}"
        if j["failed"]:
            msg += f"\n\n{len(j['failed']):,} file dilewati karena sedang dipakai/terkunci."
        if left:
            msg += f"\n\nDihentikan: {left:,} file belum diproses dan masih dicentang."
        title = "Hapus dihentikan" if left else "Hapus selesai"
        (messagebox.showwarning if j["failed"] or left else messagebox.showinfo)(title, msg)


if __name__ == "__main__":
    try:  # teks tajam di layar dengan scaling 125%/150%
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()
