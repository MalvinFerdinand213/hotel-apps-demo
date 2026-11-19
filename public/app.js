(() => {
  "use strict";
  const { ASPECTS, TIERS } = Core;
  const $ = (id) => document.getElementById(id);
  const ICONS = {
    "Lokasi": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "Kebersihan": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
    "Pelayanan": '<path d="M3 20a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1h18a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1Z"/><path d="M20 16a8 8 0 1 0-16 0"/><path d="M12 4v4"/><path d="M10 4h4"/>',
    "Kamar dan fasilitas": '<path d="M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8"/><path d="M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4"/><path d="M12 4v6"/><path d="M2 18h20"/>',
    "Harga": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    "Makanan dan minuman": '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  };
  const icon = (a, s = 16) =>
    `<span class="ico" aria-hidden="true"><svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${ICONS[a]}</svg></span>`;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const f1 = (x) => x.toFixed(1), f2 = (x) => x.toFixed(2);
  const sgn = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(2);
  const norm = (s) => String(s || "").replace(/\s+/g, " ").trim().toLowerCase();
  const store = {
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* abaikan */ } },
  };
  const MAX_SUMMARIES = 5;

  let BENCH = {}, META = {};
  const S = { tier: 1, resultTier: null, scores: null, evidence: null, sig: null, gemSig: null, photos: [] };

  /* ------------------------------------------------------------ data */
  async function loadJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(url + " " + r.status);
    return r.json();
  }

  /* ------------------------------------------------------------ UI builders */
  function buildTierSeg() {
    const avail = Core.availableTiers(BENCH);
    $("tierSeg").innerHTML = TIERS.map((t) =>
      `<span><input type="radio" name="tier" id="tier-${t}" value="${t}"${t === S.tier ? " checked" : ""}>` +
      `<label for="tier-${t}">${t}★${avail.includes(t) ? "" : '<i class="dot" title="belum ada pembanding"></i>'}</label></span>`).join("");
    $("tierNote").textContent = avail.length === 5 || !avail.length
      ? "Review akan dibandingkan dengan rata-rata hotel yang bintangnya sama."
      : `Pembanding ada untuk hotel ${avail.map((t) => t + "★").join(", ")}. Bintang lain tetap dinilai tetapi belum bisa dibandingkan (titik kuning).`;
    $("heroTiers").textContent = avail.length ? `${avail.map((t) => t + "★").join(", ")}` : "bintang yang sama";
    $("tierSeg").addEventListener("change", (e) => {
      S.tier = Number(e.target.value);
      updateStale();
    });
  }

  function buildRateList() {
    $("rateList").innerHTML = ASPECTS.map((a, i) => {
      const opts = ["–", 1, 2, 3, 4, 5].map((v, j) =>
        `<input type="radio" name="rate-${i}" id="r-${i}-${j}" value="${v}"${j === 0 ? " checked" : ""}>` +
        `<label for="r-${i}-${j}" aria-label="${a}: ${v === "–" ? "tidak dinilai" : v}">${v}</label>`).join("");
      return `<div class="rate-row"><div class="aspect">${icon(a)}<span>${a}</span></div>` +
        `<div class="seg" role="radiogroup" aria-label="Rating ${a}">${opts}</div></div>`;
    }).join("");
    $("rateList").addEventListener("change", () => { if (S.scores) render(); });
  }

  function userRatings() {
    const out = {};
    ASPECTS.forEach((a, i) => {
      const el = document.querySelector(`input[name="rate-${i}"]:checked`);
      out[a] = !el || el.value === "–" ? null : Number(el.value);
    });
    return out;
  }
  const weight = () => Number($("weight").value) / 100;
  const sigNow = () => `${$("text").value.trim()}|${S.tier}`;

  function updateStale() {
    $("stale").hidden = !(S.sig && S.sig !== sigNow());
  }

  /* ------------------------------------------------------------ analisis */
  async function run() {
    const text = $("text").value.trim();
    const err = $("runError");
    err.hidden = true;
    if (!text) { err.textContent = "Isi teks review dulu."; err.hidden = false; $("text").focus(); return; }
    const btn = $("runBtn"), lbl = $("runLabel");
    btn.disabled = true; lbl.innerHTML = '<span class="spin"></span> Menganalisis…';
    try {
      const r = await fetch("/api/score", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      let data = {};
      try { data = await r.json(); } catch (e) { /* bukan JSON */ }
      if (!r.ok || !data.scores) throw new Error(data.error || `Server membalas ${r.status}.`);
      S.scores = data.scores; S.evidence = data.evidence; S.spans = data.spans || {}; S.text = text; S.resultTier = S.tier; S.sig = sigNow();
      render();
      updateStale();
      if (window.matchMedia("(max-width: 980px)").matches) $("results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      err.textContent = "Analisis gagal: " + e.message;
      err.hidden = false;
    } finally {
      btn.disabled = false; lbl.textContent = "Analisis";
    }
  }

  /* ------------------------------------------------------------ render hasil */
  function statusBadge(st) {
    if (st === "Di atas rata-rata") return '<span class="badge badge-good">▲ Di atas</span>';
    if (st === "Di bawah rata-rata") return '<span class="badge badge-bad">▼ Di bawah</span>';
    if (st === "Sekitar rata-rata") return '<span class="badge badge-mid">≈ Sekitar</span>';
    return '<span class="dim">–</span>';
  }
  const pct = (v) => Math.min(100, Math.max(0, ((v - 1) / 4) * 100));

  const ACOL = { "Lokasi": "#3b82f6", "Kebersihan": "#14b8a6", "Pelayanan": "#f59e0b", "Kamar dan fasilitas": "#8b5cf6", "Harga": "#ef4444", "Makanan dan minuman": "#22c55e" };
  const label = (v) => (v >= 4 ? ["Bagus", "good"] : v >= 3 ? ["Cukup", "mid"] : v >= 2 ? ["Kurang", "bad"] : ["Buruk", "bad"]);

  /* kesimpulan dalam bahasa awam */
  function renderVerdict(table, ov, tier) {
    const rated = table.filter((r) => r.fused !== null);
    const el = $("verdict");
    if (!rated.length) { el.innerHTML = '<h3 id="verdictHead">Belum ada aspek yang bisa dinilai</h3><p>Review belum menyebut lokasi, kebersihan, pelayanan, kamar, harga, atau makanan. Coba tulis lebih detail atau isi rating aspek.</p>'; return; }
    const best = rated.slice().sort((a, b) => b.fused - a.fused)[0], worst = rated.slice().sort((a, b) => a.fused - b.fused)[0];
    let head;
    if (ov) {
      const g = ov.fused - ov.tier;
      head = Math.abs(g) < 0.25 ? `Review ini <em>setara</em> dengan review hotel bintang ${tier} pada umumnya.`
        : g > 0 ? `Review ini <em>lebih positif</em> dari review hotel bintang ${tier} pada umumnya.`
        : `Review ini <em>lebih negatif</em> dari review hotel bintang ${tier} pada umumnya.`;
    } else head = "Ini penilaian review untuk tiap aspek.";
    const sub = rated.length > 1 && best.aspek !== worst.aspek
      ? `Paling baik: <strong>${esc(best.aspek)}</strong>. Paling perlu diperbaiki: <strong>${esc(worst.aspek)}</strong>.` : "";
    const tiles = table.map((r) => {
      if (r.fused === null) return `<div class="vt none"><div class="vt-a">${r.aspek}</div><div class="vt-l">Tidak disebut</div></div>`;
      const [lb, cls] = label(r.fused);
      const rel = r.status === "Di atas rata-rata" ? `Lebih baik dari hotel ${tier}★ biasanya`
        : r.status === "Di bawah rata-rata" ? `Lebih buruk dari hotel ${tier}★ biasanya`
        : r.status === "Sekitar rata-rata" ? `Setara hotel ${tier}★ biasanya` : "";
      return `<div class="vt ${cls}"><div class="vt-a">${r.aspek}</div><div class="vt-l">${lb}</div><div class="vt-r">${rel}</div></div>`;
    }).join("");
    el.innerHTML = `<p class="eyebrow dark">Kesimpulan</p><h3 id="verdictHead">${head}</h3>${sub ? `<p class="vsub">${sub}</p>` : ""}<div class="vgrid">${tiles}</div>`;
  }

  /* teks review dengan potongan kalimat berwarna per aspek */
  function renderMarks(fused) {
    const text = S.text || "", spans = S.spans || {};
    const list = [];
    ASPECTS.forEach((a) => { if (fused[a].fused !== null) (spans[a] || []).forEach(([s, e]) => list.push({ a, s, e })); });
    $("markCard").hidden = !list.length;
    if (!list.length) return;
    const cuts = [...new Set([0, text.length, ...list.flatMap((x) => [x.s, x.e])])].sort((x, y) => x - y);
    let html = "";
    for (let i = 0; i < cuts.length - 1; i++) {
      const s = cuts[i], e = cuts[i + 1], seg = esc(text.slice(s, e));
      const as = [...new Set(list.filter((x) => x.s <= s && x.e >= e).map((x) => x.a))];
      html += as.length ? `<mark style="--c:${ACOL[as[0]]}" title="${esc(as.join(", "))}">${seg}</mark>` : seg;
    }
    $("markText").innerHTML = html;
    const used = ASPECTS.filter((a) => list.some((x) => x.a === a));
    $("markLegend").innerHTML = used.map((a) => `<span style="--c:${ACOL[a]}"><i></i>${a}</span>`).join("");
  }

  function render() {
    const tier = S.resultTier;
    const fused = Core.fuse(S.scores, userRatings(), weight());
    const table = Core.compare(fused, BENCH, tier);
    const ov = Core.overall(table);
    const near = Core.nearestTier(fused, BENCH).tier;
    const diff = Core.disagreements(fused);
    const rated = table.filter((r) => r.fused !== null);
    const hasBench = table.some((r) => r.tier_mean !== null);

    $("empty").hidden = true; $("results").hidden = false;

    /* KPI */
    let k1v, k1s;
    if (ov) {
      const g = ov.fused - ov.tier;
      k1v = f2(ov.fused);
      k1s = (Math.abs(g) <= 0.15 ? `<span class="badge badge-mid">≈ ${sgn(g)}</span>`
        : g > 0 ? `<span class="badge badge-good">▲ ${sgn(g)}</span>` : `<span class="badge badge-bad">▼ ${sgn(g)}</span>`) + '<span class="dim">dari rata-rata</span>';
    } else if (rated.length) {
      k1v = f2(rated.reduce((s, r) => s + r.fused, 0) / rated.length);
      k1s = '<span class="badge badge-mid">belum ada pembanding</span>';
    } else { k1v = "–"; k1s = '<span class="badge badge-mid">belum ada skor</span>'; }
    $("kpis").innerHTML =
      `<div class="kpi"><div class="k">Nilai review ini</div><div class="v">${k1v}<small>/5</small></div><div class="s">${k1s}</div></div>` +
      `<div class="kpi"><div class="k">Rata-rata hotel ${tier}★</div><div class="v">${ov ? f2(ov.tier) + "<small>/5</small>" : "–"}</div><div class="s">${hasBench ? '<span class="dim">dari data pembanding</span>' : '<span class="dim">belum ada data</span>'}</div></div>` +
      `<div class="kpi"><div class="k">Aspek yang disebut</div><div class="v">${rated.length}<small>/${ASPECTS.length}</small></div><div class="s"><span class="dim">${rated.length < ASPECTS.length ? "sisanya tidak disebut" : "semua aspek"}</span></div></div>` +
      `<div class="kpi"><div class="k">Paling mirip hotel</div><div class="v">${near ? near + "★" : "–"}</div><div class="s"><span class="dim">${near && near !== tier ? `bukan ${tier}★` : near ? "sesuai pilihanmu" : ""}</span></div></div>`;

    renderVerdict(table, ov, tier);
    renderMarks(fused);

    /* legend + chart */
    $("legend").innerHTML = hasBench
      ? `<span><i class="lg-bar"></i>Skor review</span><span><i class="lg-tick"></i>Rata-rata hotel ${tier}★</span><span><i class="lg-band"></i>Kisaran umum hotel ${tier}★</span>`
      : `<span><i class="lg-bar"></i>Skor review</span>`;
    $("chart").innerHTML = table.map((r) => {
      if (r.fused === null)
        return `<div class="crow none"><div class="aspect">${icon(r.aspek)}<span>${r.aspek}</span></div><div class="track"></div><div class="val">tidak disebut</div></div>`;
      let band = "", tick = "";
      if (r.tier_mean !== null) {
        if (r.tier_std) {
          const lo = pct(r.tier_mean - 0.5 * r.tier_std), hi = pct(r.tier_mean + 0.5 * r.tier_std);
          band = `<div class="band" style="left:${lo}%;width:${Math.max(0, hi - lo)}%"></div>`;
        }
        tick = `<div class="tick" style="left:${pct(r.tier_mean)}%"></div>`;
      }
      return `<div class="crow"><div class="aspect">${icon(r.aspek)}<span>${r.aspek}</span></div>` +
        `<div class="track">${band}<div class="bar" style="width:${pct(r.fused)}%"></div>${tick}</div>` +
        `<div class="val">${f2(r.fused)}${r.tier_mean !== null ? `<small>vs ${f2(r.tier_mean)}</small>` : ""}</div></div>`;
    }).join("");

    /* tabel */
    const n = (v, d) => (v === null ? '<span class="dim">–</span>' : d(v));
    $("tbl").innerHTML =
      `<thead><tr><th>Aspek</th><th>Model</th><th>Rating</th><th>Gabungan</th><th>Rata-rata ${tier}★</th><th>Selisih</th><th>Status</th></tr></thead><tbody>` +
      table.map((r) => `<tr><td>${r.aspek}</td><td>${n(r.model, f1)}</td><td>${n(r.user, (v) => v.toFixed(0))}</td>` +
        `<td><strong>${n(r.fused, f2)}</strong></td><td>${n(r.tier_mean, f2)}</td><td>${n(r.gap, sgn)}</td><td>${statusBadge(r.status)}</td></tr>`).join("") +
      "</tbody>";

    /* bukti teks */
    const evs = ASPECTS.filter((a) => S.evidence && S.evidence[a] && S.evidence[a].length);
    $("evidenceBox").hidden = !evs.length;
    $("evidence").innerHTML = evs.map((a) =>
      `<div><div class="ev-a">${esc(a)} <span class="dim">· nilai ${f1(S.scores[a])}</span></div><div class="ev-q">${S.evidence[a].map((e) => `“${esc(e)}”`).join(" · ")}</div></div>`).join("");

    /* ringkasan */
    const sum = Core.ruleSummary(table, ov, near, tier, diff);
    $("autoSummary").innerHTML = sum ? md(sum) : '<span class="dim">Belum ada aspek yang bisa dibandingkan. Pilih bintang yang punya data pembanding.</span>';
    $("diffChips").innerHTML = diff.map((a) => `<span class="chip">Beda jauh · ${esc(a)}: model ${f1(fused[a].model)} vs rating ${fused[a].user}</span>`).join("");

    /* Gemini: kosongkan hasil lama kalau angka berubah */
    const gs = JSON.stringify(table.map((r) => r.fused === null ? null : +r.fused.toFixed(2)));
    if (S.gemSig && S.gemSig !== gs) { $("gemOut").hidden = true; $("gemDetail").hidden = true; }
    S.gemTable = table; S.gemOv = ov; S.gemNear = near; S.gemSigNow = gs;
    $("gemBtn").disabled = !ov || S.gemEnabled === false;
    $("gemBtn").title = ov ? "" : "Perlu pembanding untuk bintang ini";
  }

  /* ------------------------------------------------------------ Gemini */
  async function gemini() {
    const used = Number(store.get("gemCount") || 0);
    const out = $("gemOut"), btn = $("gemBtn");
    out.className = "gem-out"; $("gemDetail").hidden = true;
    if (used >= MAX_SUMMARIES) { out.textContent = "Batas kesimpulan per sesi tercapai. Muat ulang halaman untuk mengulang."; out.hidden = false; return; }
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Gemini menulis…';
    const payload = {
      tier: S.resultTier, w_user: weight(), nearest: S.gemNear,
      overall: S.gemOv ? { fused: S.gemOv.fused, tier: S.gemOv.tier } : null,
      rows: S.gemTable.map((r) => ({ aspek: r.aspek, model: r.model, user: r.user, fused: r.fused, tier_mean: r.tier_mean, gap: r.gap, status: r.status })),
      excerpt: $("text").value.slice(0, 3000),
    };
    try {
      const r = await fetch("/api/summary", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      let d = {};
      try { d = await r.json(); } catch (e) { d = { error: `Server membalas ${r.status} tanpa JSON (biasanya waktu habis di Vercel). Coba klik lagi.` }; }
      if (d.summary) {
        out.textContent = d.summary; store.set("gemCount", String(used + 1)); S.gemSig = S.gemSigNow;
      } else {
        out.classList.add("err");
        out.textContent = d.error || "Kesimpulan Gemini belum bisa dibuat. Ringkasan di atas tetap berlaku.";
        if (d.attempts && d.attempts.length) { $("gemAttempts").innerHTML = d.attempts.map(esc).join("<br>"); $("gemDetail").hidden = false; }
      }
    } catch (e) {
      out.classList.add("err"); out.textContent = "Tidak bisa menghubungi server: " + e.message;
    }
    out.hidden = false; btn.disabled = false; btn.textContent = "Tulis ulang kesimpulan";
  }

  /* ------------------------------------------------------------ foto */
  function renderThumbs() {
    $("thumbs").innerHTML = S.photos.map((p, i) =>
      `<div class="thumb"><img src="${p.url}" alt="Foto review ${i + 1}"><button type="button" data-i="${i}" aria-label="Hapus foto ${i + 1}">×</button></div>`).join("");
    $("photoNote").hidden = !S.photos.length;
  }

  /* ------------------------------------------------------------ reset */
  function reset() {
    $("text").value = ""; $("counter").textContent = "0 / 3000";
    S.scores = null; S.sig = null; S.gemSig = null;
    ASPECTS.forEach((a, i) => { document.getElementById(`r-${i}-0`).checked = true; });
    $("weight").value = 50; $("weightOut").textContent = "50%";
    $("results").hidden = true; $("empty").hidden = false; $("stale").hidden = true; $("runError").hidden = true;
    $("gemOut").hidden = true; $("gemDetail").hidden = true; $("gemBtn").textContent = "Tulis kesimpulan";
    S.photos.forEach((p) => URL.revokeObjectURL(p.url)); S.photos = []; renderThumbs();
  }

  /* ------------------------------------------------------------ init */
  async function init() {
    const [b] = await Promise.allSettled([loadJSON("benchmark.json")]);
    if (b.status === "fulfilled") { BENCH = b.value.tiers || {}; META = b.value.meta || {}; }
    const avail = Core.availableTiers(BENCH);
    S.tier = avail[0] || 1;
    buildTierSeg(); buildRateList();

    /* teks metode */
    const rps = META.reviews_per_star || {}, hps = META.hotels_per_star || {};
    $("metaTrain").textContent = META.n_reviews
      ? `Dilatih dari ${META.n_reviews.toLocaleString("id-ID")} review unik di ${META.n_hotels} hotel (${Object.keys(rps).map((t) => `${t}★: ${rps[t].toLocaleString("id-ID")}`).join(", ")}).`
      : "Informasi data tidak tersedia.";
    const missing = TIERS.filter((t) => !avail.includes(t));
    $("metaBench").textContent = avail.length
      ? `Rata-rata, simpangan baku (σ), dan jumlah skor aspek per bintang, dihitung dari skor model pada review yang tidak dipakai melatihnya (validasi silang per hotel). Tersedia untuk bintang ${avail.join(", ")}.` +
        (missing.length ? ` Bintang ${missing.join(", ")} belum tersedia karena hotel di datanya terlalu sedikit (${missing.map((t) => `${t}★: ${hps[t] || 0} hotel`).join(", ")}).` : "")
      : "Belum ada data pembanding.";

    /* gemini aktif? */
    fetch("/api/summary").then((r) => r.json()).then((d) => {
      if (d && d.enabled === false) { S.gemEnabled = false; $("gemBtn").disabled = true; $("gemOut").hidden = false; $("gemOut").textContent = "Fitur ini belum diaktifkan (GEMINI_API_KEY belum diatur)."; }
    }).catch(() => {});

    /* event */
    $("text").addEventListener("input", () => {
      const v = $("text").value; $("counter").textContent = `${v.length} / 3000`;
      updateStale();
    });
    $("weight").addEventListener("input", () => { $("weightOut").textContent = $("weight").value + "%"; if (S.scores) render(); });
    $("runBtn").addEventListener("click", run);
    $("resetBtn").addEventListener("click", reset);
    $("gemBtn").addEventListener("click", gemini);
    $("text").addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run(); });
    document.querySelectorAll(".ex").forEach((b) => b.addEventListener("click", () => {
      $("text").value = EXAMPLES[b.dataset.ex]; $("text").dispatchEvent(new Event("input", { bubbles: true })); $("text").focus();
    }));
    $("photos").addEventListener("change", (e) => {
      for (const f of Array.from(e.target.files)) {
        if (S.photos.length >= 6 || f.size > 8 * 1024 * 1024) continue;
        S.photos.push({ url: URL.createObjectURL(f) });
      }
      e.target.value = ""; renderThumbs();
    });
    $("thumbs").addEventListener("click", (e) => {
      const i = e.target.dataset && e.target.dataset.i;
      if (i === undefined) return;
      URL.revokeObjectURL(S.photos[i].url); S.photos.splice(Number(i), 1); renderThumbs();
    });
    $("themeBtn").addEventListener("click", () => {
      const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* abaikan */ }
    });
  }
  /* ------------------------------------------------------------ polesan tampilan */
  const fmt1 = (v) => v.toFixed(2).replace(".", ",");
  function buildBenchmark() {
    const tiers = Core.availableTiers(BENCH);
    if (!tiers.length) { $("benchmark").hidden = true; return; }
    $("bnReviews").textContent = (META.n_reviews || 0).toLocaleString("id-ID");
    const mean = (a) => tiers.reduce((s, t) => s + BENCH[t][a].mean, 0) / tiers.length;
    const dev = Math.max(...ASPECTS.flatMap((a) => tiers.map((t) => Math.abs(BENCH[t][a].mean - mean(a))))) || 1;
    let h = `<div class="hr hh"><span></span>${tiers.map((t) => `<span>${t}★</span>`).join("")}</div>`;
    ASPECTS.forEach((a, ai) => {
      h += `<div class="hr"><span class="hl">${a}</span>${tiers.map((t) => {
        const c = BENCH[t][a], d = (c.mean - mean(a)) / dev, al = Math.min(1, Math.abs(d)) * 0.85;
        const strong = al > 0.45 ? " data-s" : "";
        return `<button type="button" class="hc ${d >= 0 ? "hi" : "lo"}" data-a="${ai}" data-t="${t}" style="--al:${al.toFixed(2)}"${strong} aria-label="${a}, bintang ${t}: ${fmt1(c.mean)}">${fmt1(c.mean)}</button>`;
      }).join("")}</div>`;
    });
    $("heat").innerHTML = h;
    $("heat").addEventListener("click", (e) => {
      const b = e.target.closest(".hc"); if (!b) return;
      document.querySelectorAll(".hc.on").forEach((x) => x.classList.remove("on")); b.classList.add("on");
      const a = ASPECTS[b.dataset.a], t = b.dataset.t, c = BENCH[t][a], d = c.mean - mean(a);
      $("heatDetail").innerHTML = `<strong>${a}, hotel bintang ${t}:</strong> rata-rata skor <strong>${fmt1(c.mean)}</strong> dari ${c.n.toLocaleString("id-ID")} review. ` +
        (Math.abs(d) < 0.05 ? "Hampir sama dengan rata-rata semua bintang." : `${d > 0 ? "Lebih tinggi" : "Lebih rendah"} ${fmt1(Math.abs(d))} dari rata-rata semua bintang untuk aspek ini.`);
    });
    /* temuan otomatis */
    const items = ASPECTS.map((a) => {
      const ys = tiers.map((t) => BENCH[t][a].mean), n = ys.length, xs = tiers.map(Number);
      const mx = xs.reduce((s, v) => s + v, 0) / n, my = ys.reduce((s, v) => s + v, 0) / n;
      const r = xs.reduce((s, v, i) => s + (v - mx) * (ys[i] - my), 0) / Math.sqrt(xs.reduce((s, v) => s + (v - mx) ** 2, 0) * ys.reduce((s, v) => s + (v - my) ** 2, 0) || 1);
      const hi = ys.indexOf(Math.max(...ys)), lo = ys.indexOf(Math.min(...ys));
      return { a, r, range: Math.max(...ys) - Math.min(...ys), hi: tiers[hi], lo: tiers[lo], first: ys[0], last: ys[n - 1] };
    }).sort((x, y) => y.range - x.range).slice(0, 3);
    $("insights").innerHTML = items.map((x) => {
      const txt = x.r > 0.7 ? `Makin tinggi bintang hotelnya, makin <strong>tinggi</strong> skor ${x.a.toLowerCase()} (${fmt1(x.first)} di ${tiers[0]}★ menjadi ${fmt1(x.last)} di ${tiers[tiers.length - 1]}★).`
        : x.r < -0.7 ? `Makin tinggi bintang hotelnya, makin <strong>rendah</strong> skor ${x.a.toLowerCase()} (${fmt1(x.first)} di ${tiers[0]}★ menjadi ${fmt1(x.last)} di ${tiers[tiers.length - 1]}★).`
        : `Skor ${x.a.toLowerCase()} paling tinggi di hotel ${x.hi}★ dan paling rendah di hotel ${x.lo}★.`;
      return `<div class="ins reveal"><span class="ins-a">${x.a}</span><p>${txt}</p></div>`;
    }).join("");
    document.querySelectorAll("#insights .reveal").forEach((el) => el.classList.add("in"));
  }
  async function buildResults() {
    try {
      const h = await loadJSON("hasil.json"), pc = (v) => Math.round(v * 100);
      $("bigstats").innerHTML = [
        [`${pc(h.auc_pipeline)}%`, "Dari 10 pasang review (satu negatif, satu positif), model mengurutkan dengan benar sekitar " + Math.round(h.auc_pipeline * 10) + " pasang."],
        [h.n_review.toLocaleString("id-ID"), `review dari ${h.n_hotel} hotel dipakai untuk belajar dan menguji.`],
        [`${pc(h.cakupan)}%`, "review menyebut minimal satu aspek, jadi bisa dinilai."],
        ["Hotel baru", "Penguji hanya memakai hotel yang belum pernah dilihat model saat belajar."],
      ].map(([v, t]) => `<div class="bs reveal"><div class="bs-v">${v}</div><p>${t}</p></div>`).join("");
    } catch (e) { $("bigstats").hidden = true; }
    document.querySelectorAll("#bigstats .reveal").forEach((el) => el.classList.add("in"));
  }

  const EXAMPLES = {
    pos: "Luar biasa, sangat puas! Lokasi strategis dan mudah dicari. Kamar sangat bersih, wangi, luas, dan fasilitasnya lengkap. Pelayanan prima, staf ramah dan sigap. Makanan dan sarapannya enak sekali. Harga sepadan dengan kualitasnya, pasti menginap lagi.",
    net: "Hotel biasa saja. Kamar lumayan bersih tapi AC kurang dingin dan wifi sering putus. Staf ramah tapi pelayanannya agak lambat. Lokasi lumayan dekat dari stasiun. Sarapan standar, pilihannya terbatas. Harganya sesuai, tidak murah tidak mahal.",
    neg: "Sangat kecewa. Kamar kotor dan berbau, kamar mandi ada rambut dan jamur. Staf tidak peduli saat saya komplain, malah dicuekin. Sarapannya basi dan tidak enak. Harga mahal tapi kualitas jelek sekali, tidak akan menginap lagi.",
  };
  function polish() {
    const nav = $("nav");
    const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
    onScroll(); window.addEventListener("scroll", onScroll, { passive: true });

    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const els = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window && !reduce) {
      const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 });
      els.forEach((el) => io.observe(el));
    } else els.forEach((el) => el.classList.add("in"));
  }
  function setStats() {
    const set = (id, v) => { const el = $(id); if (el && v) el.dataset.count = String(v); };
    set("statReviews", META.n_reviews); set("statHotels", META.n_hotels);
    const fr = $("footReviews"), fh = $("footHotels");
    if (fr && META.n_reviews) fr.textContent = META.n_reviews.toLocaleString("id-ID");
    if (fh && META.n_hotels) fh.textContent = META.n_hotels.toLocaleString("id-ID");
    set("statTiers", Core.availableTiers(BENCH).length || 5);
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelectorAll("[data-count]").forEach((el) => {
      const to = Number(el.dataset.count), fmt = (v) => Math.round(v).toLocaleString("id-ID");
      if (reduce) { el.textContent = fmt(to); return; }
      const t0 = performance.now(), dur = 1200;
      const tick = (t) => { const p = Math.min(1, (t - t0) / dur); el.textContent = fmt(to * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    });
  }
  polish();
  init().then(() => { buildBenchmark(); setStats(); }, setStats);
  buildResults();
})();
