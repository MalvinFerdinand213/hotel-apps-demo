"""Buat public/benchmark.json dari benchmark.csv + dataset.

Pakai (dari folder train/):  python make_site_data.py --data data_combine.csv
"""
import argparse
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "..", "public")
ap = argparse.ArgumentParser()
ap.add_argument("--data", default=os.path.join(HERE, "data_combine.csv"))
ap.add_argument("--per-star", type=int, default=150, help="jumlah contoh review per bintang hotel")
a = ap.parse_args()

# --- benchmark ---
b = pd.read_csv(os.path.join(HERE, "benchmark.csv"))
tiers = {}
for r in b.itertuples():
    tiers.setdefault(str(int(r.bintang)), {})[r.aspek] = {"mean": float(r.rata_rata), "std": float(r.std), "n": int(r.n)}

# --- dataset: bersihkan sama seperti train_model.py ---
df = pd.read_csv(a.data, encoding="utf-8-sig").dropna(subset=["review_id", "review_text", "review_rating", "hotel_stars", "place_id"])
df = df.drop_duplicates("review_id")
df["review_rating"] = pd.to_numeric(df["review_rating"], errors="coerce")
df = df[df["review_rating"].between(1, 5) & (df["review_rating"] % 1 == 0)]
hotels = df.groupby("hotel_stars")["place_id"].nunique()
meta = {
    "n_reviews": int(len(df)),
    "n_hotels": int(df["place_id"].nunique()),
    "reviews_per_star": {str(int(k)): int(v) for k, v in df["hotel_stars"].value_counts().sort_index().items()},
    "regions": {str(k): int(v) for k, v in df["region"].value_counts().items()} if "region" in df else {},
    "hotels_per_star": {str(int(k)): int(v) for k, v in hotels.items()},
}
json.dump({"tiers": tiers, "meta": meta}, open(os.path.join(PUB, "benchmark.json"), "w"), ensure_ascii=False, indent=1)

print("benchmark tiers:", sorted(tiers))

# --- ringkasan hasil evaluasi + gambar untuk halaman "Hasil penelitian" (kalau laporan sudah dibuat) ---
import shutil
REP = os.path.join(HERE, "reports")
ev_path, sm_path = os.path.join(REP, "eval_utama.csv"), os.path.join(REP, "eval_summary.json")
if os.path.exists(ev_path) and os.path.exists(sm_path):
    ev = pd.read_csv(ev_path)
    cvr = ev[ev["evaluasi"].str.startswith("CV")].set_index("metode")
    sm = json.load(open(sm_path, encoding="utf-8"))
    pl, ml = "Pipeline (rata-rata skor aspek)", "TF-IDF+Ridge (teks utuh)"
    hasil = {
        "n_review": sm["n_review"], "n_hotel": sm["n_hotel"],
        "auc_pipeline": round(float(cvr.loc[pl, "AUC_rating<=3"]), 3), "spearman_pipeline": round(float(cvr.loc[pl, "Spearman"]), 3),
        "auc_ml": round(float(cvr.loc[ml, "AUC_rating<=3"]), 3), "spearman_ml": round(float(cvr.loc[ml, "Spearman"]), 3),
        "mae_ml": round(float(cvr.loc[ml, "MAE"]), 3), "cakupan": round(sm["cakupan_review_pipeline_cv"], 3),
    }
    json.dump(hasil, open(os.path.join(PUB, "hasil.json"), "w"), ensure_ascii=False, indent=1)
    img = os.path.join(PUB, "img")
    os.makedirs(img, exist_ok=True)
    for f in ("fig_01_jumlah_data", "fig_02_distribusi_rating", "fig_06_mention_aspek", "fig_10_baseline", "fig_11_kalibrasi_confusion", "fig_12_subgrup"):
        shutil.copy(os.path.join(REP, f + ".png"), os.path.join(img, f + ".png"))
    print("hasil.json + gambar disalin:", hasil)
