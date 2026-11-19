"""EDA dataset bersih -> reports/fig_*.png dan reports/tbl_*.csv.
Pakai: python eda.py --data data_clean.csv"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import aspect_model as am

HERE = os.path.dirname(os.path.abspath(__file__))
C = ["#2F6F8F", "#E08A3C", "#5B9E6B", "#B5586A", "#7A6FB0", "#8A8A8A"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "axes.axisbelow": True, "figure.dpi": 100})


def save(fig, rep, name):
    fig.tight_layout()
    fig.savefig(os.path.join(rep, name), dpi=160)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data_clean.csv"))
    ap.add_argument("--reports", default=os.path.join(HERE, "reports"))
    a = ap.parse_args()
    rep = a.reports
    os.makedirs(rep, exist_ok=True)
    d = pd.read_csv(a.data)
    d["words"] = d["review_text"].str.split().str.len()
    stars = sorted(d["hotel_stars"].unique())

    # tabel ringkas
    t = d.groupby("hotel_stars").agg(review=("review_id", "size"), hotel=("place_id", "nunique"),
                                      rating_rata2=("review_rating", "mean"), rating_sd=("review_rating", "std"),
                                      kata_median=("words", "median"), foto_rata2=("downloaded_image_count", "mean")).round(3)
    t["review_per_hotel"] = (t["review"] / t["hotel"]).round(1)
    t.to_csv(os.path.join(rep, "tbl_ringkas_per_bintang.csv"), encoding="utf-8-sig")
    pd.crosstab(d["hotel_stars"], d["region"]).to_csv(os.path.join(rep, "tbl_bintang_wilayah.csv"), encoding="utf-8-sig")
    pd.crosstab(d["hotel_stars"], d["review_rating"]).to_csv(os.path.join(rep, "tbl_bintang_rating.csv"), encoding="utf-8-sig")
    pd.crosstab(d["hotel_stars"], d["detected_language"], normalize="index").round(3).to_csv(
        os.path.join(rep, "tbl_bintang_bahasa.csv"), encoding="utf-8-sig")
    d.isna().sum().rename("kosong").to_frame().assign(persen=lambda x: (x.kosong / len(d) * 100).round(1)).to_csv(
        os.path.join(rep, "tbl_missing.csv"), encoding="utf-8-sig")

    # 1 review & hotel per bintang x wilayah
    ct = pd.crosstab(d["hotel_stars"], d["region"])
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ct.plot.bar(ax=ax[0], color=C[:2], rot=0)
    ax[0].set(title="Jumlah review per bintang hotel", xlabel="Bintang hotel", ylabel="Review")
    h = d.groupby(["hotel_stars", "region"])["place_id"].nunique().unstack()
    h.plot.bar(ax=ax[1], color=C[:2], rot=0)
    ax[1].set(title="Jumlah hotel per bintang", xlabel="Bintang hotel", ylabel="Hotel")
    save(fig, rep, "fig_01_jumlah_data.png")

    # 2 distribusi rating per bintang (proporsi)
    p = pd.crosstab(d["hotel_stars"], d["review_rating"], normalize="index")
    fig, ax = plt.subplots(figsize=(7, 3.8))
    left = np.zeros(len(p))
    cols = ["#B5586A", "#E08A3C", "#E8C547", "#8FBF8F", "#2F6F8F"]
    for r, c in zip(p.columns, cols):
        ax.barh(p.index.astype(str), p[r], left=left, color=c, label=f"{r}★")
        left += p[r].values
    ax.set(title="Distribusi rating review per bintang hotel", xlabel="Proporsi", ylabel="Bintang hotel")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(.5, -.18), frameon=False)
    ax.invert_yaxis()
    save(fig, rep, "fig_02_distribusi_rating.png")

    # 3 rata-rata rating + CI
    g = d.groupby("hotel_stars")["review_rating"]
    m, ci = g.mean(), 1.96 * g.std() / np.sqrt(g.size())
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    ax.errorbar(m.index, m.values, yerr=ci.values, fmt="o-", color=C[0], capsize=4)
    ax.set(title="Rata-rata rating review (±95% CI)", xlabel="Bintang hotel", ylabel="Rating review", xticks=stars)
    save(fig, rep, "fig_03_rata_rating.png")

    # 4 bahasa & panjang teks
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.6))
    pd.crosstab(d["hotel_stars"], d["detected_language"], normalize="index").plot.bar(
        stacked=True, ax=ax[0], color=C[:3], rot=0)
    ax[0].set(title="Bahasa review per bintang", xlabel="Bintang hotel", ylabel="Proporsi")
    ax[0].legend(title=None, ncol=3, loc="upper center", bbox_to_anchor=(.5, -.2), frameon=False)
    ax[1].boxplot([d[d.hotel_stars == s]["words"].clip(upper=200) for s in stars], tick_labels=stars, showfliers=False)
    ax[1].set(title="Panjang review (kata, dipotong 200)", xlabel="Bintang hotel", ylabel="Kata")
    save(fig, rep, "fig_04_bahasa_panjang.png")

    # 5 review per hotel + foto
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.6))
    rph = d.groupby("place_id").size()
    ax[0].hist(rph, bins=range(1, int(rph.max()) + 2), color=C[0])
    ax[0].set(title="Review per hotel", xlabel="Jumlah review", ylabel="Hotel")
    ph = d["downloaded_image_count"].clip(upper=6).value_counts().sort_index()
    ax[1].bar(ph.index.astype(str), ph.values, color=C[1])
    ax[1].set(title="Foto per review (6 = 6+)", xlabel="Jumlah foto", ylabel="Review")
    save(fig, rep, "fig_05_review_hotel_foto.png")

    # 6 mention rate per aspek x bintang
    rows = []
    for s, txt in zip(d["hotel_stars"], d["review_text"]):
        w = am.extract_windows(txt)
        rows.append({"hotel_stars": s, **{a: bool(w[a]) for a in am.ASPECTS}})
    mr = pd.DataFrame(rows).groupby("hotel_stars").mean().round(3)
    mr.to_csv(os.path.join(rep, "tbl_mention_aspek.csv"), encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    im = ax.imshow(mr.values, cmap="Blues", vmin=0, vmax=max(.6, mr.values.max()), aspect="auto")
    ax.set_xticks(range(len(mr.columns)), [c.replace(" dan ", "\ndan ") for c in mr.columns])
    ax.set_yticks(range(len(mr)), mr.index)
    for i in range(mr.shape[0]):
        for j in range(mr.shape[1]):
            ax.text(j, i, f"{mr.values[i, j]*100:.0f}%", ha="center", va="center",
                    color="white" if mr.values[i, j] > .35 else "#222")
    ax.set(title="Persentase review yang menyebut tiap aspek", ylabel="Bintang hotel")
    ax.grid(False)
    save(fig, rep, "fig_06_mention_aspek.png")
    print(t.to_string())
    print(mr.to_string())


if __name__ == "__main__":
    main()
