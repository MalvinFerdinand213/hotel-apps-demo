"""Satu perintah untuk memperbarui semuanya setelah dataset bertambah.

Pakai (dari folder train/):   python update_all.py --data data_combine.csv
Langkah: cleaning -> EDA -> evaluasi -> latih model final -> benchmark -> data website -> salin model ke ../lib/
Hasil laporan (tabel + grafik) ada di train/reports/. Lalu commit + push; Vercel otomatis deploy ulang.
Tambah --skip-eval untuk melewati evaluasi (2 menit) saat hanya ingin memperbarui model.
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--data", default=os.path.join(HERE, "data_combine.csv"))
ap.add_argument("--skip-eval", action="store_true")
a = ap.parse_args()
clean = os.path.join(HERE, "data_clean.csv")


def run(*cmd):
    print("\n$", " ".join(cmd))
    subprocess.run(cmd, cwd=HERE, check=True)


run(sys.executable, "audit_and_clean.py", "--data", a.data, "--out", clean)
run(sys.executable, "eda.py", "--data", clean)
if not a.skip_eval:
    run(sys.executable, "evaluate.py", "--data", clean)
run(sys.executable, "train_model.py", "--data", clean)
run(sys.executable, "make_site_data.py", "--data", clean)
shutil.copy(os.path.join(HERE, "aspect_model.json"), os.path.join(HERE, "..", "lib", "aspect_model.json"))
print("\nSelesai. Model baru: lib/aspect_model.json, data website: public/, laporan: train/reports/. Commit + push untuk deploy.")
