"""Evaluasi model: hold-out per hotel + 5-fold GroupKFold, baseline, per-subgrup, analisis error.
Output: reports/eval_*.csv, reports/eval_summary.json, reports/fig_1x_*.png

Yang diukur: seberapa baik skor dari TEKS memprediksi rating keseluruhan review (satu-satunya label yang ada).
Dataset tidak punya label per aspek, jadi akurasi per aspek TIDAK bisa diukur dengan data ini.

Pakai: python evaluate.py --data data_clean.csv
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold

import aspect_model as am
import train_model as tm

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 42
PRED = ["rata2_global", "kamus_saja", "ml_saja", "pipeline"]
LABELS = {"rata2_global": "Rata-rata global", "kamus_saja": "Kamus sentimen saja",
          "ml_saja": "TF-IDF+Ridge (teks utuh)", "pipeline": "Pipeline (rata-rata skor aspek)"}
CLS = ["negatif (1-2)", "netral (3)", "positif (4-5)"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "axes.axisbelow": True})
C = ["#8A8A8A", "#E08A3C", "#5B9E6B", "#2F6F8F"]


def score_frame(df, model, train_mean):
    """Prediksi rating untuk tiap review dari 4 pendekatan."""
    rows = []
    for text in df["review_text"]:
        toks = am.TOKEN_RE.findall(am.normalize(text))
        ml = am.ml_predict(" ".join(toks), model)
        lex = am.lex_score(toks)
        an = am.analyze(text, model)
        got = [r["score"] for r in an.values() if r["score"] is not None]
        rows.append({"rata2_global": train_mean, "kamus_saja": lex if lex is not None else 3.0,
                     "ml_saja": ml, "pipeline": float(np.mean(got)) if got else np.nan,
                     "n_aspek": len(got), "has_lex": lex is not None,
                     **{f"a_{a}": r["score"] for a, r in an.items()}})
    out = pd.DataFrame(rows, index=df.index)
    out["pipeline_isi"] = out["pipeline"].fillna(out["ml_saja"])  # review tanpa aspek -> pakai ML teks utuh
    return out


def fit_model(df):
    texts, y, w = tm.build_samples(df, tm.MODE)
    return tm.fit(texts, y, w, tm.ALPHA)[0], float(df["review_rating"].mean())


def cv_predict(df, n_splits=5):
    parts = []
    for tr, te in GroupKFold(n_splits).split(df, groups=df["place_id"]):
        m, mean = fit_model(df.iloc[tr])
        parts.append(score_frame(df.iloc[te], m, mean))
    return pd.concat(parts).loc[df.index]


def to_cls(rating):
    r = np.asarray(rating)
    return np.where(r <= 2, 0, np.where(r == 3, 1, 2))


def tune_thr(score, rating):
    """Cari 2 ambang (neg|net, net|pos) pada skor yang memaksimalkan macro-F1 (hanya dari data latih)."""
    s = np.asarray(score)
    cand = np.unique(np.round(np.quantile(s, np.linspace(.02, .98, 49)), 3))
    y = to_cls(rating)
    best = (-1, cand[0], cand[-1])
    for i, t1 in enumerate(cand):
        for t2 in cand[i + 1:]:
            p = np.where(s < t1, 0, np.where(s < t2, 1, 2))
            f = f1_score(y, p, average="macro")
            if f > best[0]:
                best = (f, t1, t2)
    return best[1], best[2]


def apply_thr(score, thr):
    s = np.asarray(score)
    return np.where(s < thr[0], 0, np.where(s < thr[1], 1, 2))


def metrics(rating, pred, cls_pred=None):
    r, p = np.asarray(rating, float), np.asarray(pred, float)
    ok = ~np.isnan(p)
    r, p = r[ok], p[ok]
    out = {"n": int(ok.sum()), "MAE": float(np.abs(p - r).mean()), "RMSE": float(np.sqrt(((p - r) ** 2).mean()))}
    out["Spearman"] = float(spearmanr(p, r)[0]) if np.std(p) > 0 else 0.0
    low = (r <= 3).astype(int)
    out["AUC_rating<=3"] = float(roc_auc_score(low, -p)) if 0 < low.sum() < len(low) else np.nan
    if cls_pred is not None:
        c = np.asarray(cls_pred)[ok]
        out["macroF1_3kelas"] = float(f1_score(to_cls(r), c, average="macro"))
        out["akurasi_3kelas"] = float((to_cls(r) == c).mean())
    return out


def holdout_split(df, frac=.2):
    rng = np.random.RandomState(SEED)
    test = set()
    for s, g in df.groupby("hotel_stars"):
        ids = np.array(sorted(g["place_id"].unique()))
        rng.shuffle(ids)
        test |= set(ids[: max(1, int(round(len(ids) * frac)))])
    m = df["place_id"].isin(test)
    return df[~m], df[m]


def boot_ci(df, pred, col, fn, n=300):
    """Bootstrap per hotel (klaster) untuk interval kepercayaan 95%."""
    rng = np.random.RandomState(SEED)
    g = {k: v for k, v in df.assign(_p=pred[col].values).groupby("place_id")}
    ids = np.array(list(g))
    vals = []
    for _ in range(n):
        b = pd.concat([g[i] for i in rng.choice(ids, len(ids))])
        vals.append(fn(b["review_rating"].values, b["_p"].values))
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data_clean.csv"))
    ap.add_argument("--reports", default=os.path.join(HERE, "reports"))
    a = ap.parse_args()
    rep = a.reports
    os.makedirs(rep, exist_ok=True)
    df = tm.load_data(a.data)
    summary = {"n_review": len(df), "n_hotel": int(df["place_id"].nunique())}

    # ---------- A. CV 5 lipatan (semua data) ----------
    print("CV 5-fold per hotel ...")
    cv = cv_predict(df)
    y = df["review_rating"].values
    thr_cv = {p: tune_thr(cv[p], y) for p in PRED[1:3] + ["pipeline_isi"]}
    rows = []
    for p in PRED:
        col = "pipeline_isi" if p == "pipeline" else p
        cp = apply_thr(cv[col], thr_cv[col]) if col in thr_cv else np.full(len(df), 2)
        m = metrics(y, cv[col], cp)
        rows.append({"metode": LABELS[p], "evaluasi": "CV-5 per hotel", **m})
    # ---------- B. Hold-out 80/20 per hotel ----------
    tr, te = holdout_split(df)
    print(f"Hold-out: latih {len(tr)} review/{tr.place_id.nunique()} hotel, uji {len(te)} review/{te.place_id.nunique()} hotel")
    summary["holdout"] = {"latih_review": len(tr), "latih_hotel": int(tr.place_id.nunique()),
                          "uji_review": len(te), "uji_hotel": int(te.place_id.nunique())}
    cv_tr = cv_predict(tr.reset_index(drop=True))  # ambang dicari hanya dari data latih (OOF)
    thr_h = {c: tune_thr(cv_tr[c], tr["review_rating"].values) for c in ("kamus_saja", "ml_saja", "pipeline_isi")}
    m_full, mean_tr = fit_model(tr)
    ho = score_frame(te, m_full, mean_tr)
    yt = te["review_rating"].values
    for p in PRED:
        col = "pipeline_isi" if p == "pipeline" else p
        cp = apply_thr(ho[col], thr_h[col]) if col in thr_h else np.full(len(te), 2)
        rows.append({"metode": LABELS[p], "evaluasi": "Hold-out 20% hotel", **metrics(yt, ho[col], cp)})
    res = pd.DataFrame(rows).round(4)
    res.to_csv(os.path.join(rep, "eval_utama.csv"), index=False, encoding="utf-8-sig")
    print(res.to_string(index=False))
    summary["ambang_3kelas_cv"] = {k: [float(x) for x in v] for k, v in thr_cv.items()}

    # CI bootstrap (CV pooled, pipeline & ml)
    ci = {}
    for col in ("ml_saja", "pipeline_isi"):
        ci[col] = {"MAE": boot_ci(df, cv, col, lambda r, p: np.abs(r - p).mean()),
                   "Spearman": boot_ci(df, cv, col, lambda r, p: spearmanr(r, p)[0])}
    summary["ci95_bootstrap_per_hotel"] = ci

    # cakupan pipeline
    summary["cakupan_review_pipeline_cv"] = float(cv["pipeline"].notna().mean())
    pd.DataFrame({"jumlah_aspek_terdeteksi": cv["n_aspek"].value_counts().sort_index()}).assign(
        persen=lambda x: (x.jumlah_aspek_terdeteksi / len(cv) * 100).round(1)).to_csv(
        os.path.join(rep, "eval_cakupan_aspek.csv"), encoding="utf-8-sig")

    # ---------- C. per-subgrup (CV) ----------
    sub = []
    for name, col in (("bintang hotel", "hotel_stars"), ("bahasa", "detected_language"), ("wilayah", "region")):
        for val, idx in df.groupby(col).groups.items():
            for p in ("ml_saja", "pipeline_isi"):
                m = metrics(y[df.index.get_indexer(idx)], cv.loc[idx, p].values)
                sub.append({"kelompok": name, "nilai": val, "metode": LABELS["pipeline" if p == "pipeline_isi" else p], **m})
    sub = pd.DataFrame(sub).round(4)
    sub.to_csv(os.path.join(rep, "eval_per_subgrup.csv"), index=False, encoding="utf-8-sig")

    # ---------- D. per aspek: cakupan & hubungan dengan rating ----------
    asp = []
    for aname in am.ASPECTS:
        s = cv[f"a_{aname}"]
        ok = s.notna()
        asp.append({"aspek": aname, "review_terdeteksi": int(ok.sum()), "cakupan_%": round(ok.mean() * 100, 1),
                    "skor_rata2": round(s[ok].mean(), 3), "skor_sd": round(s[ok].std(), 3),
                    "spearman_dgn_rating": round(spearmanr(s[ok], y[ok.values])[0], 3)})
    pd.DataFrame(asp).to_csv(os.path.join(rep, "eval_per_aspek.csv"), index=False, encoding="utf-8-sig")

    # ---------- E. analisis error ----------
    d = df.assign(pred=cv["pipeline_isi"].values, ml=cv["ml_saja"].values)
    d["err"] = d["pred"] - d["review_rating"]
    d["tipe"] = np.where(d["err"] > 0, "terlalu positif", "terlalu negatif")
    d["panjang_kata"] = d["review_text"].str.split().str.len()
    err = d.reindex(d["err"].abs().sort_values(ascending=False).index).head(40)
    err[["hotel_stars", "review_rating", "pred", "tipe", "detected_language", "review_text"]].round(2).to_csv(
        os.path.join(rep, "eval_error_terbesar.csv"), index=False, encoding="utf-8-sig")
    bylen = d.assign(b=pd.cut(d["panjang_kata"], [0, 5, 10, 20, 50, 100000], labels=["1-5", "6-10", "11-20", "21-50", ">50"]))
    pd.DataFrame([{"panjang_kata": k, "n": len(g), "MAE": round(g["err"].abs().mean(), 3),
                   "Spearman": round(spearmanr(g["pred"], g["review_rating"])[0], 3)}
                  for k, g in bylen.groupby("b", observed=True)]).to_csv(
        os.path.join(rep, "eval_error_per_panjang.csv"), index=False, encoding="utf-8-sig")
    summary["error"] = {
        "rating<=2_diprediksi>=4_%": float((d[d.review_rating <= 2]["pred"] >= 4).mean() * 100),
        "rating=5_diprediksi<3.5_%": float((d[d.review_rating == 5]["pred"] < 3.5).mean() * 100),
    }

    # ---------- F. uji kewajaran (model penuh) ----------
    ok = tot = 0
    for text, exp in tm.SANITY:
        r = am.score_text(text, m_full)
        for aname, sg in exp.items():
            tot += 1
            s = r[aname]
            ok += s is not None and ((sg == "+" and s > 3.2) or (sg == "-" and s < 2.8))
    summary["uji_kewajaran_tanda_benar"] = f"{ok}/{tot}"

    # ---------- figur ----------
    fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.6))
    cvr = res[res.evaluasi == "CV-5 per hotel"]
    for k, (met, ttl) in enumerate((("MAE", "MAE (lebih kecil lebih baik)"), ("Spearman", "Spearman (lebih besar lebih baik)"),
                                    ("AUC_rating<=3", "AUC rating ≤3 vs ≥4"))):
        ax[k].bar(range(4), cvr[met], color=C)
        ax[k].set(title=ttl, xticks=range(4), xticklabels=["Rata2\nglobal", "Kamus", "ML", "Pipeline"])
        for i, v in enumerate(cvr[met]):
            ax[k].text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(rep, "fig_10_baseline.png"), dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    g = d.groupby("review_rating")["pred"].agg(["mean", "std"])
    ax[0].bar(g.index, g["mean"], yerr=g["std"], color=C[3], capsize=3)
    ax[0].plot([.5, 5.5], [.5, 5.5], "--", color="#999", label="ideal")
    ax[0].set(title="Skor model vs rating sebenarnya (CV)", xlabel="Rating review", ylabel="Skor model rata-rata (±SD)", ylim=(1, 5.3))
    ax[0].legend(frameon=False)
    cm = confusion_matrix(to_cls(y), apply_thr(cv["pipeline_isi"], thr_cv["pipeline_isi"]), labels=[0, 1, 2])
    cmn = cm / cm.sum(1, keepdims=True)
    ax[1].imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax[1].text(j, i, f"{cmn[i, j]*100:.0f}%\n(n={cm[i, j]})", ha="center", va="center",
                       color="white" if cmn[i, j] > .5 else "#222", fontsize=9)
    ax[1].set(title="Confusion matrix 3 kelas (baris = sebenarnya)", xticks=range(3), yticks=range(3),
              xticklabels=["neg", "net", "pos"], yticklabels=["neg", "net", "pos"], xlabel="Prediksi", ylabel="Sebenarnya")
    ax[1].grid(False)
    fig.tight_layout()
    fig.savefig(os.path.join(rep, "fig_11_kalibrasi_confusion.png"), dpi=160)
    plt.close(fig)
    summary["confusion_3kelas_cv"] = cm.tolist()

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    s1 = sub[(sub.kelompok == "bintang hotel") & (sub.metode == LABELS["pipeline"])]
    ax[0].bar(s1["nilai"].astype(str), s1["Spearman"], color=C[3])
    ax[0].set(title="Spearman pipeline per bintang hotel", xlabel="Bintang hotel", ylim=(0, 1))
    s2 = sub[(sub.kelompok == "bahasa") & (sub.metode == LABELS["pipeline"])]
    ax[1].bar(s2["nilai"], s2["Spearman"], color=C[1])
    ax[1].set(title="Spearman pipeline per bahasa", xlabel="Bahasa", ylim=(0, 1))
    for x in ax:
        for p in x.patches:
            x.text(p.get_x() + p.get_width() / 2, p.get_height(), f"{p.get_height():.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(rep, "fig_12_subgrup.png"), dpi=160)
    plt.close(fig)

    for k in ("n_review",):
        pass
    with open(os.path.join(rep, "eval_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(sub.to_string(index=False))
    print(pd.DataFrame(asp).to_string(index=False))
    print(pd.read_csv(os.path.join(rep, "eval_error_per_panjang.csv")).to_string(index=False))


if __name__ == "__main__":
    main()
