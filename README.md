# Aspek Hotel — analisis aspek review hotel (siap deploy ke Vercel)

Website: input review + rating per aspek -> skor tiap aspek dibanding rata-rata hotel di bintang yang sama,
plus kesimpulan dari Gemini. Tanpa framework dan tanpa build: HTML/CSS/JS statis + 2 fungsi Python.

```
public/          website statis (index.html, styles.css, app.js, core.js, benchmark.json)
api/score.py     POST /api/score    -> skor aspek dari model (murni Python, tanpa dependensi)
api/summary.py   POST /api/summary  -> kesimpulan Gemini (REST, key dari Environment Variable)
lib/             aspect_model.py + aspect_model.json (hasil pelatihan)
train/           pelatihan model (tidak ikut di-deploy)
dev_server.py    server lokal untuk mencoba tanpa Vercel
vercel.json
```

## Deploy ke Vercel (tanpa terminal)
1. Buat repo GitHub baru, upload SEMUA isi folder ini (kecuali `train/data_combine.csv` yang besar; sudah di .gitignore).
2. vercel.com -> **Add New… -> Project** -> pilih repo tadi -> **Import**.
3. Pengaturan: Framework Preset = **Other**. Kosongkan Build Command, biarkan Output Directory (sudah diatur di `vercel.json`).
4. Buka **Environment Variables**, tambah:
   - `GEMINI_API_KEY` = key dari https://aistudio.google.com/apikey  (jangan ditulis di kode)
   - (opsional) `GEMINI_MODELS` = `gemini-3.8-flash,gemini-3.7-flash`
5. Klik **Deploy**. Setelah selesai, buka link `.vercel.app`.
Mengubah env var -> **Redeploy** agar berlaku.

## Coba di laptop
```
python dev_server.py        # lalu buka http://localhost:8000
# (opsional, Windows PowerShell)  $env:GEMINI_API_KEY="..." ; python dev_server.py
```

## Dataset bertambah
```
cd train
pip install -r requirements.txt
python update_all.py --data data_combine.csv
```
Lalu commit + push; Vercel deploy ulang otomatis. Bintang yang hotelnya < 10 tidak dimasukkan ke benchmark.

## Catatan
- Skor aspek adalah perkiraan: dataset hanya punya rating keseluruhan per review, bukan label per aspek.
- Foto belum dianalisis model (hanya tampil di browser, tidak dikirim ke server).
- Endpoint Gemini publik: siapa pun yang tahu link-nya bisa memakai kuota key-mu. Pantau kuota di AI Studio,
  atau batasi akses (mis. Vercel Password Protection / Deployment Protection).
