"""Menyusun laporan Word (EDA + evaluasi) dari tabel/grafik di reports/. Pakai: python make_report.py"""
import json, os
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "reports")
rd = lambda n: pd.read_csv(os.path.join(R, n))
S = json.load(open(os.path.join(R, "eval_summary.json"), encoding="utf-8"))
CI = json.load(open(os.path.join(R, "cleaning_info.json"), encoding="utf-8"))
doc = Document()
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Cm(2.5); sec.top_margin = sec.bottom_margin = Cm(2.5)
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
for h, sz in (("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 12)):
    s = doc.styles[h]; s.font.name = "Times New Roman"; s.font.size = Pt(sz); s.font.bold = True
    s.font.color.rgb = None
    s.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
cn = {"t": 0, "f": 0}


def P(text, bold=False, italic=False, align=None):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    p.paragraph_format.space_after = Pt(6); p.paragraph_format.line_spacing = 1.3
    if align: p.alignment = align
    return p


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color); tcPr.append(sh)


def T(title, df, widths=None, fs=9):
    cn["t"] += 1
    P(f"Tabel {cn['t']}. {title}", bold=True).paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(df.columns)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(str(c)); r.bold = True; r.font.size = Pt(fs)
        shade(cell, "D9E2EC")
    for row in df.itertuples(index=False):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            if hasattr(v, 'item'): v = v.item()
            if isinstance(v, float):
                v = "–" if pd.isna(v) else (f"{v:.3f}" if abs(v) < 100 else f"{v:.0f}")
            cells[i].text = ""; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(fs)
            if i > 0 and not isinstance(v, str): cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def F(name, caption, w=15.5):
    cn["f"] += 1
    doc.add_picture(os.path.join(R, name), width=Cm(w)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = P(f"Gambar {cn['f']}. {caption}", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)


# ---------- data ----------
log = rd("cleaning_log.csv"); rg = rd("tbl_ringkas_per_bintang.csv"); ev = rd("eval_utama.csv")
sub = rd("eval_per_subgrup.csv"); asp = rd("eval_per_aspek.csv"); cov = rd("eval_cakupan_aspek.csv")
ln = rd("eval_error_per_panjang.csv"); er = rd("eval_error_terbesar.csv"); ment = rd("tbl_mention_aspek.csv")
bench = pd.read_csv(os.path.join(HERE, "benchmark.csv"))
cv = ev[ev.evaluasi == "CV-5 per hotel"].set_index("metode"); ho = ev[ev.evaluasi != "CV-5 per hotel"].set_index("metode")
PL, ML, KM, GL = "Pipeline (rata-rata skor aspek)", "TF-IDF+Ridge (teks utuh)", "Kamus sentimen saja", "Rata-rata global"
ci = S["ci95_bootstrap_per_hotel"]
nrev, nhot = S["n_review"], S["n_hotel"]

doc.add_heading("Laporan Pembersihan Data, Analisis Eksplorasi (EDA), dan Evaluasi Model", 0)
P("Analisis ulasan Google Maps hotel Jakarta dan Bali per kelas bintang hotel", italic=True)

doc.add_heading("1. Ringkasan", 1)
P(f"Dataset akhir berisi {nrev:,} ulasan dari {nhot} hotel (bintang 1–5, masing-masing sekitar 2.000 ulasan; Jakarta dan Bali). "
  f"Pembersihan data membuang {CI['baris_awal']-CI['baris_akhir']} baris dari {CI['baris_awal']:,} dan merapikan {CI['teks_berubah_setelah_cleaning']:,} teks "
  f"(terutama tag HTML <br> pada {CI['teks_mengandung_br_html']:,} teks). Model yang dievaluasi adalah pendekatan weak supervision berbasis teks "
  "(TF-IDF + regresi Ridge, dipadukan dengan kamus sentimen) yang menghasilkan skor 1–5 untuk enam aspek.")
P(f"Hasil utama (validasi silang 5-lipatan, dibagi per hotel sehingga hotel uji tidak pernah dilihat saat pelatihan): model teks utuh mencapai "
  f"Spearman {cv.loc[ML,'Spearman']:.2f}, MAE {cv.loc[ML,'MAE']:.2f}, dan AUC {cv.loc[ML,'AUC_rating<=3']:.2f} dalam memisahkan ulasan rating ≤3 dari ≥4, "
  f"jauh di atas baseline rata-rata global (MAE {cv.loc[GL,'MAE']:.2f}). Skor gabungan aspek (pipeline) mempertahankan urutan yang baik "
  f"(Spearman {cv.loc[PL,'Spearman']:.2f}, AUC {cv.loc[PL,'AUC_rating<=3']:.2f}) tetapi skalanya tidak dikalibrasi terhadap rating, sehingga MAE-nya tidak boleh dibaca sebagai galat prediksi rating.")
P("Batasan terpenting: dataset hanya memiliki rating keseluruhan per ulasan, bukan label per aspek. Karena itu seluruh metrik mengukur kesesuaian skor "
  "dengan rating keseluruhan, bukan ketepatan skor tiap aspek. Ketepatan per aspek hanya dapat diukur dengan anotasi manual atau kuesioner.", bold=True)

doc.add_heading("2. Pembersihan data", 1)
P("Pembersihan dijalankan oleh skrip audit_and_clean.py. Setiap langkah dicatat (Tabel 1) sehingga dapat diulang dan diaudit. Teks asli disimpan pada kolom review_text_raw.")
lg = log.copy(); lg.columns = ["Langkah", "Sebelum", "Sesudah", "Dibuang", "Alasan"]
T("Log pembersihan data", lg)
P(f"Temuan lain: kolom review_url kosong 100% (tidak dipakai). Terdapat {CI['teks_kembar_lintas_hotel']} teks pendek yang sama persis di hotel berbeda "
  f"(misalnya “{list(CI['contoh_kembar_lintas_hotel'])[0]}”); ini dipertahankan karena merupakan ulasan singkat yang wajar. "
  f"Sebanyak {CI['teks_lebih_3000_karakter']} teks melebihi 3.000 karakter dan dipotong saat dianalisis di website. "
  "Teks bergaya huruf matematika (misalnya “𝙺𝚊𝚖𝚊𝚛”) dinormalisasi dengan NFKC menjadi huruf biasa agar tidak terbuang.")

doc.add_heading("3. Analisis eksplorasi data (EDA)", 1)
doc.add_heading("3.1 Gambaran umum", 2)
r2 = rg.copy(); r2.columns = ["Bintang", "Ulasan", "Hotel", "Rata-rata rating", "SD rating", "Median kata", "Rata-rata foto", "Ulasan/hotel"]
T("Ringkasan data per bintang hotel", r2)
P("Jumlah ulasan hampir seimbang antar bintang (±2.000), tetapi jumlah hotel menurun pada bintang tinggi (223 hotel bintang 1 vs 131 hotel bintang 5). "
  "Artinya hotel bintang tinggi memiliki lebih banyak ulasan per hotel (15,5 vs 9,3), sehingga rata-rata bintang 5 lebih dipengaruhi beberapa hotel.")
F("fig_01_jumlah_data.png", "Jumlah ulasan dan hotel per bintang dan wilayah.")
doc.add_heading("3.2 Distribusi rating", 2)
F("fig_02_distribusi_rating.png", "Distribusi rating ulasan per bintang hotel.", 13)
F("fig_03_rata_rating.png", "Rata-rata rating ulasan per bintang hotel (±95% CI).", 10)
P("Rating sangat condong ke bintang 5 di semua kelas hotel (59–82% ulasan, terendah di bintang 2). Rata-rata rating tidak naik monoton: hotel bintang 2 memiliki rata-rata terendah (4,07) "
  "dan paling banyak ulasan rating 1 (sekitar 13%), sedangkan hotel bintang 1 (4,44) lebih tinggi dari bintang 2 dan 3. Kelas bintang hotel dan rating ulasan adalah dua hal berbeda, "
  "dan ekspektasi tamu pada hotel murah relatif rendah. Ketimpangan kelas rating ini juga yang membuat kelas netral (rating 3) paling sulit diprediksi.")
doc.add_heading("3.3 Bahasa, panjang teks, dan foto", 2)
F("fig_04_bahasa_panjang.png", "Bahasa dan panjang ulasan per bintang hotel.")
F("fig_05_review_hotel_foto.png", "Distribusi ulasan per hotel dan foto per ulasan.")
P("Ulasan berbahasa Indonesia mendominasi (65%), diikuti Inggris (30%) dan campuran (5%); porsi bahasa Inggris tertinggi di bintang 1 (45%) dan terendah di bintang 5 (18%). "
  "Median panjang ulasan naik dari 33 kata (bintang 1) menjadi 44 kata (bintang 4–5). Rata-rata jumlah foto per ulasan juga naik dari 3,4 menjadi 5,0. "
  "Foto belum dianalisis pada tahap ini.")
doc.add_heading("3.4 Aspek yang dibahas", 2)
F("fig_06_mention_aspek.png", "Persentase ulasan yang menyebut tiap aspek (berdasarkan kata kunci).", 14)
P("Kamar dan fasilitas paling sering dibahas (57–68%), diikuti pelayanan. Pembahasan harga turun tajam pada hotel bintang tinggi (32% di bintang 1 menjadi 14% di bintang 5), "
  "sedangkan makanan dan minuman naik (35% menjadi 52%). Kebersihan paling jarang dibahas di bintang 5 (27%), kemungkinan karena dianggap standar. "
  "Konsekuensinya jumlah observasi per aspek berbeda antar bintang (Tabel 3), dan benchmark aspek berjumlah sedikit (misalnya harga bintang 5) harus dibaca lebih hati-hati.")
bn = bench.copy(); bn.columns = ["Bintang", "Aspek", "Rata-rata", "SD", "n"]
T("Benchmark skor aspek per bintang hotel (dari skor out-of-fold; dipakai website)", bn, fs=8)

doc.add_heading("4. Metode yang dievaluasi", 1)
P("Karena tidak ada label per aspek, model dilatih dengan weak supervision: setiap ulasan utuh dan setiap jendela kata di sekitar kata kunci aspek diberi label rating ulasan. "
  "Fitur TF-IDF (unigram dan bigram, sublinear tf, min_df=2) dilatih dengan regresi Ridge (alpha=1; jendela berbobot 0,5). Skor aspek adalah rata-rata skor jendela, "
  "gabungan prediksi model dan kamus sentimen; aspek yang tidak disebut diberi nilai kosong. Inferensi dilakukan dengan Python murni dari berkas JSON sehingga dapat berjalan di Vercel.")
P("Pada skripsi, metode utama adalah zero-shot Qwen3-VL; model ini hanya dipakai untuk demo. Hasil Qwen3-VL belum dimasukkan dalam laporan ini.", italic=True)

doc.add_heading("5. Evaluasi model", 1)
doc.add_heading("5.1 Rancangan evaluasi", 2)
ho_s = S["holdout"]
P(f"Dua skema dipakai. (a) Validasi silang 5-lipatan dengan GroupKFold berdasarkan place_id, sehingga ulasan dari satu hotel tidak pernah berada di data latih dan data uji sekaligus. "
  f"(b) Hold-out: {ho_s['uji_hotel']} hotel ({ho_s['uji_review']:,} ulasan, 20% hotel per bintang) disisihkan sebagai data uji, model dilatih pada {ho_s['latih_hotel']} hotel ({ho_s['latih_review']:,} ulasan). "
  "Pembagian per hotel mencegah kebocoran dari gaya penulisan atau nama hotel yang sama.")
P("Tugas yang diukur: memprediksi rating keseluruhan (1–5) dari teks. Metrik: MAE dan RMSE (galat), korelasi Spearman (kesesuaian urutan), AUC untuk memisahkan rating ≤3 dari ≥4, "
  "serta macro-F1 dan akurasi untuk tiga kelas (negatif 1–2, netral 3, positif 4–5). Ambang tiga kelas dicari hanya pada data latih. "
  "Pembanding: rata-rata global, kamus sentimen saja, model TF-IDF+Ridge pada teks utuh, dan pipeline aspek.")
doc.add_heading("5.2 Hasil utama", 2)
m = ev.copy()
m = m[["evaluasi", "metode", "n", "MAE", "RMSE", "Spearman", "AUC_rating<=3", "macroF1_3kelas", "akurasi_3kelas"]]
m.columns = ["Skema", "Metode", "n", "MAE", "RMSE", "Spearman", "AUC", "Macro-F1", "Akurasi"]
T("Perbandingan metode (rating 1–5)", m, fs=8)
F("fig_10_baseline.png", "Perbandingan metode pada validasi silang per hotel.")
P(f"Model teks utuh terbaik pada semua metrik. Pada CV, Spearman {cv.loc[ML,'Spearman']:.3f} (CI 95% bootstrap per hotel {ci['ml_saja']['Spearman'][0]:.3f}–{ci['ml_saja']['Spearman'][1]:.3f}) "
  f"dan MAE {cv.loc[ML,'MAE']:.3f} ({ci['ml_saja']['MAE'][0]:.3f}–{ci['ml_saja']['MAE'][1]:.3f}). Hasil hold-out konsisten (Spearman {ho.loc[ML,'Spearman']:.3f}, MAE {ho.loc[ML,'MAE']:.3f}), "
  "sehingga tidak terlihat overfit terhadap hotel. Kamus sentimen saja lebih lemah, dan penggabungan keduanya pada tingkat jendela aspek memberi skor yang lebih mudah dijelaskan per aspek dengan harga penurunan akurasi terhadap rating total.")
P(f"Pipeline aspek: Spearman {cv.loc[PL,'Spearman']:.3f} (CI {ci['pipeline_isi']['Spearman'][0]:.3f}–{ci['pipeline_isi']['Spearman'][1]:.3f}), AUC {cv.loc[PL,'AUC_rating<=3']:.3f}. "
  f"MAE-nya ({cv.loc[PL,'MAE']:.2f}) hampir sama dengan baseline karena skor aspek ditarik ke sekitar 3,5–4 (lihat Gambar 8) dan tidak dikalibrasi ke skala rating. "
  "Jadi skor aspek layak dipakai untuk membandingkan (peringkat dan selisih terhadap benchmark), bukan sebagai nilai rating absolut. "
  f"Cakupan: {S['cakupan_review_pipeline_cv']*100:.1f}% ulasan memiliki minimal satu aspek terdeteksi; ulasan tanpa aspek dihitung memakai prediksi model teks utuh pada tabel di atas.")
F("fig_11_kalibrasi_confusion.png", "Kalibrasi skor terhadap rating (kiri) dan confusion matrix tiga kelas pada pipeline (kanan).")
cm = S["confusion_3kelas_cv"]
P(f"Kelas positif dikenali dengan baik ({cm[2][2]/sum(cm[2])*100:.0f}% benar), kelas negatif cukup ({cm[0][0]/sum(cm[0])*100:.0f}%), tetapi kelas netral sulit ({cm[1][1]/sum(cm[1])*100:.0f}%): "
  f"{cm[1][2]/sum(cm[1])*100:.0f}% ulasan rating 3 diprediksi positif. Ini wajar karena kelas netral sedikit (n={sum(cm[1])}) dan teks ulasan rating 3 sering bernada campuran.")
doc.add_heading("5.3 Hasil per kelompok", 2)
sb = sub[sub.metode == PL][["kelompok", "nilai", "n", "Spearman", "AUC_rating<=3"]].copy(); sb.columns = ["Kelompok", "Nilai", "n", "Spearman", "AUC"]
sm = sub[sub.metode == ML][["Spearman", "MAE"]].reset_index(drop=True); sb = sb.reset_index(drop=True); sb["Spearman ML"] = sm["Spearman"]; sb["MAE ML"] = sm["MAE"]
sb.columns = ["Kelompok", "Nilai", "n", "Spearman pipeline", "AUC pipeline", "Spearman ML", "MAE ML"]
T("Kinerja per bintang hotel, bahasa, dan wilayah (CV)", sb)
F("fig_12_subgrup.png", "Spearman pipeline per bintang hotel dan bahasa.")
en = sub[(sub.kelompok == "bahasa") & (sub.metode == PL)].set_index("nilai")
P(f"Kinerja lebih rendah pada ulasan berbahasa Inggris (Spearman pipeline {en.loc['en','Spearman']:.2f} vs {en.loc['id','Spearman']:.2f} untuk Indonesia), karena kamus dan kata kunci aspek terutama berbahasa Indonesia. "
  "Kinerja juga lebih rendah pada hotel bintang 4–5 dan Bali. Bali separuh berbahasa Inggris dan 78% ratingnya 5 (Jakarta 63%), sehingga variasi rating kecil dan ulasan negatif langka.")
doc.add_heading("5.4 Cakupan dan hubungan per aspek", 2)
a2 = asp.copy(); a2.columns = ["Aspek", "Ulasan terdeteksi", "Cakupan (%)", "Skor rata-rata", "SD skor", "Spearman dgn rating"]
T("Cakupan dan statistik skor per aspek (CV)", a2)
P("Korelasi skor aspek dengan rating total berkisar 0,20 (lokasi) hingga 0,58 (kebersihan). Korelasi rendah pada lokasi dan makanan bukan bukti skor salah: ulasan sering memuji lokasi walau rating total rendah karena alasan lain. "
  "Tabel ini bukan ukuran akurasi per aspek.")
doc.add_heading("5.5 Analisis kesalahan", 2)
l2 = ln.copy(); l2.columns = ["Panjang (kata)", "n", "MAE", "Spearman"]
T("Kinerja pipeline menurut panjang ulasan", l2)
e = S["error"]
P(f"Ulasan pendek jauh lebih sulit (Spearman 0,29 untuk ≤10 kata vs 0,60 untuk >50 kata). Kesalahan ekstrem jarang: {e['rating<=2_diprediksi>=4_%']:.1f}% ulasan rating ≤2 diprediksi ≥4 dan {e['rating=5_diprediksi<3.5_%']:.1f}% ulasan rating 5 diprediksi <3,5. "
  "Pemeriksaan 40 kesalahan terbesar (eval_error_terbesar.csv) menunjukkan tiga pola:")
for t_ in ("Ketidaksesuaian rating dan teks (label noise): teks memuji tetapi rating 1 (misalnya “Tempat menginap yang murah & nyaman di jakarta”, rating 1). Ini kesalahan label, bukan kesalahan model.",
           "Keluhan spesifik di tengah teks positif atau sebaliknya (sarkasme, “tapi hotelnya creepy parah”, kritik yang ditulis setelah pujian panjang), yang tidak ditangkap model berbasis kata.",
           "Ulasan tentang hal di luar pengalaman menginap (hotel sudah tutup, tidak jadi menginap, hanya merujuk foto) tanpa kata sentimen yang jelas. Dari 40 kesalahan terbesar, 37 berupa skor terlalu positif."):
    doc.add_paragraph(t_, style="List Bullet")
doc.add_heading("5.6 Uji kewajaran", 2)
P(f"Sebanyak 32 kalimat buatan sendiri (43 pasangan aspek–arah sentimen) menghasilkan tanda sentimen benar {S['uji_kewajaran_tanda_benar']}. Ini hanya uji kewajaran, bukan akurasi: kalimatnya ditulis oleh pembuat model.")

doc.add_heading("6. Keterbatasan dan saran", 1)
for t_ in ("Label per aspek tidak ada, sehingga ketepatan skor aspek belum terukur. Saran: anotasi manual sampel acak (misalnya 200 ulasan × 6 aspek, oleh dua penilai) atau kuesioner; hitung kesepakatan skor model dengan penilai manusia dan Cohen’s kappa antarpenilai.",
           "Skor aspek tidak dikalibrasi terhadap skala rating; interpretasi hanya relatif (perbandingan dengan benchmark bintang).",
           "Kamus dan kata kunci aspek terutama berbahasa Indonesia sehingga ulasan Inggris lebih lemah.",
           "Rating ulasan condong 5 dan memuat label noise; kelas netral sulit.",
           "Foto belum dianalisis dan hasil Qwen3-VL (metode utama skripsi) belum tersedia; keduanya perlu dilaporkan terpisah dan dibandingkan dengan kinerja model ini sebagai baseline.",
           "Hotel bintang 4–5 punya hotel lebih sedikit dengan ulasan per hotel lebih banyak; benchmark aspek berjumlah n kecil (misalnya harga bintang 5, n=275) kurang stabil."):
    doc.add_paragraph(t_, style="List Bullet")
doc.add_heading("Lampiran. Berkas pendukung", 1)
P("Semua tabel dan grafik di laporan ini dihasilkan otomatis ke folder train/reports/ oleh update_all.py (cleaning_log.csv, tbl_*.csv, eval_*.csv, fig_*.png, eval_summary.json). Laporan ini dapat dibuat ulang dengan python make_report.py.")
out = os.path.join(R, "laporan_eda_evaluasi.docx")
doc.save(out); print(out)
