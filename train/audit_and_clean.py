"""Audit + cleaning dataset ulasan hotel. Menulis data_clean.csv dan reports/cleaning_log.csv.

Pakai:  python audit_and_clean.py --data data_combine.csv --out data_clean.csv

Langkah (urut, tiap langkah dicatat jumlah baris sebelum/sesudah):
  1. buang baris tanpa teks/rating/bintang/place_id
  2. buang duplikat review_id
  3. rating harus bilangan bulat 1-5
  4. bersihkan teks (NFKC: huruf gaya 𝙺𝚊𝚖𝚊𝚛 -> Kamar): <br>/tag HTML -> spasi, entitas HTML, karakter tak terlihat, spasi ganda (teks asli disimpan di review_text_raw)
  5. buang teks rusak (#NAME?, #REF!, ...), kosong setelah dibersihkan, atau < 3 huruf
  6. buang teks kembar di hotel yang sama (setelah normalisasi: huruf kecil, tanpa emoji/tanda baca); simpan yang scrape_order terkecil
  Info saja (tidak dibuang): teks kembar lintas hotel, teks > 3000 karakter (dipotong saat dianalisis).
"""
import argparse
import html
import unicodedata
import json
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TAG_RE = re.compile(r"<\s*/?\s*(?:br|p|div|span|b|i|u|li|ul|ol)\b[^>]*>", re.I)
INVIS_RE = re.compile("[​‌‍⁠﻿­]")
CORRUPT_RE = re.compile(r"^\s*(#NAME\?|#REF!|#VALUE!|#N/A|#DIV/0!|nan|null|none)\s*$", re.I)
NONALNUM_RE = re.compile(r"[^0-9a-zA-ZÀ-ɏ]+")


def clean_text(t):
    t = unicodedata.normalize("NFKC", html.unescape(str(t)))  # huruf gaya matematika/fullwidth -> huruf biasa
    t = TAG_RE.sub(" ", t)
    t = INVIS_RE.sub("", t)
    t = t.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", t).strip()


def norm_key(t):
    return NONALNUM_RE.sub("", t.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data_combine.csv"))
    ap.add_argument("--out", default=os.path.join(HERE, "data_clean.csv"))
    ap.add_argument("--reports", default=os.path.join(HERE, "reports"))
    a = ap.parse_args()
    os.makedirs(a.reports, exist_ok=True)

    df = pd.read_csv(a.data, encoding="utf-8-sig")
    log, info = [], {}

    def step(name, new, why):
        log.append({"langkah": name, "baris_sebelum": len(cur[0]), "baris_sesudah": len(new),
                    "dibuang": len(cur[0]) - len(new), "alasan": why})
        cur[0] = new

    cur = [df]
    log.append({"langkah": "0. data awal", "baris_sebelum": len(df), "baris_sesudah": len(df), "dibuang": 0, "alasan": ""})
    d = cur[0]
    step("1. kolom kunci kosong", d.dropna(subset=["review_text", "review_rating", "hotel_stars", "place_id"]),
         "teks/rating/bintang/place_id kosong")
    d = cur[0].copy()
    step("2. duplikat review_id", d.drop_duplicates("review_id"), "review yang sama tercatat dua kali")
    d = cur[0].copy()
    r = pd.to_numeric(d["review_rating"], errors="coerce")
    step("3. rating tidak valid", d[r.between(1, 5) & (r % 1 == 0)], "rating bukan bilangan bulat 1-5")
    d = cur[0].copy()
    d["review_text_raw"] = d["review_text"].astype(str)
    d["review_text"] = d["review_text_raw"].map(clean_text)
    info["teks_berubah_setelah_cleaning"] = int((d["review_text"] != d["review_text_raw"].str.strip()).sum())
    info["teks_mengandung_br_html"] = int(d["review_text_raw"].str.contains(TAG_RE).sum())
    cur[0] = d
    log.append({"langkah": "4. pembersihan teks", "baris_sebelum": len(d), "baris_sesudah": len(d), "dibuang": 0,
                "alasan": f"{info['teks_berubah_setelah_cleaning']} teks dirapikan ({info['teks_mengandung_br_html']} berisi tag <br>/HTML)"})
    letters = d["review_text"].str.count(r"[A-Za-zÀ-ɏ]")
    bad = d["review_text"].str.match(CORRUPT_RE) | (d["review_text"].str.len() == 0) | (letters < 3)
    info["teks_rusak_contoh"] = d.loc[bad, "review_text_raw"].str.slice(0, 40).head(10).tolist()
    step("5. teks rusak/kosong/<3 huruf", d[~bad], "teks '#NAME?', kosong, atau hampir tanpa huruf")
    d = cur[0].copy()
    d["_k"] = d["review_text"].map(norm_key)
    d = d.sort_values("scrape_order") if "scrape_order" in d.columns else d
    # lintas hotel (info saja)
    cross = d.groupby("_k")["place_id"].nunique()
    info["teks_kembar_lintas_hotel"] = int((cross > 1).sum())
    info["contoh_kembar_lintas_hotel"] = d[d["_k"].isin(cross[cross > 1].index)]["review_text"].str.slice(0, 50).value_counts().head(5).to_dict()
    step("6. teks kembar di hotel yang sama", d.drop_duplicates(["place_id", "_k"]),
         "teks sama persis (setelah normalisasi) di hotel yang sama")
    d = cur[0].drop(columns="_k").sort_values("scrape_order").reset_index(drop=True)
    info["teks_lebih_3000_karakter"] = int((d["review_text"].str.len() > 3000).sum())
    d["review_rating"] = d["review_rating"].astype(int)
    d.to_csv(a.out, index=False, encoding="utf-8")
    pd.DataFrame(log).to_csv(os.path.join(a.reports, "cleaning_log.csv"), index=False, encoding="utf-8-sig")
    info.update({"baris_awal": len(df), "baris_akhir": len(d), "hotel": int(d["place_id"].nunique())})
    with open(os.path.join(a.reports, "cleaning_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(pd.DataFrame(log).to_string(index=False))
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
