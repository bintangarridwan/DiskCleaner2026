# Disk Scanner

Aplikasi kecil untuk Windows yang membantu mencari file yang aman dibersihkan di disk C, D, atau disk lain.

Aplikasi ini membaca semua file di disk yang dipilih, lalu mengelompokkannya: mana yang aman dihapus (file temp, cache browser, installer lama di Downloads), mana yang perlu dicek dulu, dan mana yang sebaiknya tidak disentuh sama sekali karena dipakai Windows. Setelah itu kamu tinggal centang file yang mau dibuang. File tidak dihapus permanen, tapi dipindah ke Recycle Bin, jadi masih bisa dikembalikan kalau salah pilih.

Ada dua versi:

- **GUI** (`disk_scanner_gui.py`): tampilan jendela dengan tabel yang bisa dibuka-tutup per folder dan kotak centang per file.
- **CLI** (`disk_scanner.py`): versi terminal, isinya ringkasan per kategori dan 50 file terbesar.

## Tech stack

| Komponen | Dipakai untuk |
|---|---|
| Python 3.12 atau lebih baru | Bahasa utamanya. Minimal 3.12 karena aplikasi memakai `os.listdrives()` untuk membaca daftar disk |
| tkinter | Tampilan GUI. Sudah ikut terpasang bersama Python dari python.org |
| [rich](https://github.com/Textualize/rich) | Tabel, menu, dan progress di versi CLI. Versi GUI tidak membutuhkannya |
| [send2trash](https://github.com/arsenetar/send2trash) | Memindahkan file ke Recycle Bin, bukan menghapus permanen |

Selain dua library di atas, semuanya pakai modul bawaan Python. Aplikasi ini **hanya jalan di Windows**, karena memakai API Windows untuk membaca nama volume disk dan mengatur tampilan supaya tetap tajam di layar dengan scaling 125% atau 150%.

## Instalasi

1. Pastikan Python 3.12 atau lebih baru sudah terpasang. Cek dengan:

   ```
   python --version
   ```

   Kalau belum ada, unduh dari [python.org](https://www.python.org/downloads/). Saat instalasi, centang **"tcl/tk and IDLE"** (biasanya sudah tercentang) supaya tkinter ikut terpasang, dan centang juga **"Add python.exe to PATH"**.

2. Clone repo ini, lalu masuk ke foldernya:

   ```
   git clone <url-repo-ini>
   cd <nama-folder>
   ```

3. Pasang dua library yang dibutuhkan:

   ```
   pip install rich send2trash
   ```

## Cara pakai

**Tips:** buka Command Prompt dengan **Run as administrator** sebelum menjalankan aplikasi. Tanpa hak admin, banyak folder sistem tidak bisa dibaca dan akan dilewati. Aplikasi tetap jalan, tapi hasil scan-nya jadi kurang lengkap.

### Versi GUI

```
python disk_scanner_gui.py
```

1. Pilih disk di dropdown **Disk**.
2. Klik **Start**. Selama scan berjalan, tombolnya berubah jadi **Stop**. Klik Stop kalau ingin berhenti di tengah jalan, dan hasil yang sudah terkumpul tetap ditampilkan.
3. Setelah scan selesai.
4. Hasilnya tampil sebagai tabel bertingkat: **Kategori → Folder → File**. Klik segitiga di kiri (atau tekan panah kanan) untuk membuka isinya.
5. Centang file yang ingin dibuang dengan mengklik kotaknya atau menekan **Spasi**. Kalau kategori atau folder dicentang, semua isinya ikut tercentang.
   - **Select All** mencentang semua file yang boleh dihapus.
   - **Unselect All** melepas semua centang.
6. Klik **Delete To Recycle Bin**, lalu konfirmasi.
7. Selama proses hapus berjalan, tombolnya berubah jadi **Stop Delete**. Kalau sadar ada file yang tidak sengaja tercentang, klik tombol ini. File yang belum diproses akan tetap tercentang, jadi tinggal dilepas lalu hapus lagi.

### Versi CLI

```
python disk_scanner.py
```

1. Ketik nomor disk yang mau di-scan. Tekan `Ctrl+C` kalau ingin berhenti di tengah scan.
2. Muncul dua tabel: ringkasan per kategori dan 50 file terbesar.
3. Pilih menu:
   - `1`: hapus satu file dari daftar 50 file terbesar
   - `2`: bersihkan satu kategori Aman sekaligus
   - `3`: tampilkan tabel lagi
   - `4`: scan disk lain
   - `0`: keluar

## Bagaimana aplikasi menentukan status file

Setiap file diberi salah satu dari tiga status berdasarkan lokasi dan ekstensinya.

**Aman**: bisa dihapus tanpa efek berarti, karena isinya dibuat ulang otomatis atau bisa diunduh lagi.

| Kategori | Isinya |
|---|---|
| Temp | `C:\Windows\Temp`, `AppData\Local\Temp`, file `.tmp` dan `.dmp` |
| Cache browser | Cache Chrome, Edge, Brave, Opera, Vivaldi, dan Firefox |
| Cache aplikasi | Folder di AppData yang namanya berakhiran "cache", misalnya milik Discord, VS Code, atau Teams |
| Installer di Downloads | File `.exe` dan `.msi` di folder Downloads |
| Downloads lama | File di Downloads yang tidak diubah lebih dari 180 hari |

**Hati-hati**: boleh dihapus, tapi ada yang bisa terdampak.

| Kategori | Yang perlu diperhatikan |
|---|---|
| Cookie browser | Kamu akan logout dari semua website. Tutup browser dulu, karena file ini terkunci selama browser terbuka |
| Cache Windows Update | Aman kalau tidak ada update yang sedang tertunda |
| Log | Biasanya aman, tapi kadang dibutuhkan untuk mencari penyebab error |
| Data aplikasi | Isi AppData selain cache. Menghapusnya bisa mereset pengaturan atau menghapus data aplikasi |
| File lain | Semua file lain, termasuk dokumen dan foto pribadi. Cek satu per satu sebelum dihapus |

**Terkunci**: tidak bisa dicentang dan hanya ditampilkan sebagai informasi. Isinya folder `Windows`, `Program Files`, `ProgramData`, file boot, `pagefile.sys`, dan `hiberfil.sys`. Program di `Program Files` sebaiknya dihapus lewat **Settings → Apps**, jangan dengan menghapus filenya langsung.

## Hal yang perlu diketahui

- **Status file hanya tebakan berdasarkan aturan path dan ekstensi.** Aturannya cukup hati-hati, tapi tetap bukan jaminan 100%. Sebelum menghapus file Hati-hati, lihat dulu isinya.
- **Hati-hati dengan Select All di disk C.** Tombol ini juga mencentang kategori "File lain", yang isinya termasuk dokumen pribadi. Buka kategori itu dan lepas centang file yang masih kamu butuhkan.
- **Ruang disk baru benar-benar kosong setelah Recycle Bin dikosongkan.** File yang dipindah ke Recycle Bin masih memakan tempat di disk. Setelah yakin tidak ada yang salah hapus, kosongkan Recycle Bin dari desktop.
- **File yang terlalu besar untuk Recycle Bin bisa langsung terhapus permanen.** Ini perilaku bawaan Windows. Batas ukuran Recycle Bin bisa dicek dan diubah lewat klik kanan Recycle Bin → Properties.
- **File yang sedang dipakai akan dilewati.** Misalnya file temp milik aplikasi yang masih terbuka. File lainnya tetap dihapus, dan notifikasi di akhir akan menyebutkan berapa file yang dilewati.
- **Scan disk C bisa makan waktu beberapa menit**, tergantung jumlah file dan kecepatan disk. SSD jauh lebih cepat daripada HDD.
- **Kategori dengan puluhan ribu folder agak lambat saat pertama kali dibuka.** Biasanya ini terjadi pada "File lain" atau "Data aplikasi". Tunggu beberapa detik saja.
- **Registry tidak disentuh sama sekali.** Membersihkan registry hampir tidak ada manfaatnya, sedangkan risikonya besar.

## Mengecek aturan klasifikasi

Kalau kamu mengubah aturan di fungsi `classify()`, jalankan pengecekan ini untuk memastikan tidak ada aturan lama yang rusak:

```
python core.py
```

Kalau semuanya benar, yang muncul hanya `OK`.

## Struktur file

```
core.py               Logika inti: daftar disk, scan, klasifikasi, dan hapus ke Recycle Bin
disk_scanner.py       Versi CLI, memakai core.py
disk_scanner_gui.py   Versi GUI, memakai core.py
```

Aturan klasifikasi ada di bagian atas `core.py` (`RULES`, `BROWSERS`, dan fungsi `classify()`). Kalau ingin menambah kategori baru, ubah di sana, dan perubahannya langsung berlaku di CLI maupun GUI.
