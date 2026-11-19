/* Logika inti (tanpa DOM): penggabungan skor, perbandingan benchmark, ringkasan.
   Padanan hotel_core.py. Skala semua skor: 1-5. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Core = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const ASPECTS = ["Lokasi", "Kebersihan", "Pelayanan", "Kamar dan fasilitas", "Harga", "Makanan dan minuman"];
  const TIERS = [1, 2, 3, 4, 5];
  const DISAGREE_THRESHOLD = 1.5;

  const clip = (x) => Math.min(5, Math.max(1, x));
  const has = (v) => v !== null && v !== undefined && !Number.isNaN(v);

  /* gabungan = (1 - w) * model + w * rating pengguna; kalau salah satu tidak ada, dipakai yang ada */
  function fuse(model, user, w) {
    const out = {};
    for (const a of ASPECTS) {
      const m = model[a], u = user[a];
      let f = null, src = "-";
      if (has(m) && has(u)) { f = (1 - w) * m + w * u; src = "gabungan"; }
      else if (has(m)) { f = m; src = "model saja"; }
      else if (has(u)) { f = u; src = "rating saja"; }
      out[a] = { model: has(m) ? m : null, user: has(u) ? u : null, fused: f === null ? null : clip(f), sumber: src };
    }
    return out;
  }

  /* bench: {tier: {aspek: {mean, std, n}}} */
  function compare(fused, bench, tier, band = 0.3, zBand = 0.5) {
    const b = (bench && bench[String(tier)]) || {};
    return ASPECTS.map((a) => {
      const r = fused[a], f = r.fused;
      const row = { aspek: a, model: r.model, user: r.user, fused: f, tier_mean: null, tier_std: null, gap: null, status: "-" };
      if (f !== null && b[a]) {
        const mean = b[a].mean, std = b[a].std;
        const gap = f - mean;
        const neutral = has(std) && std > 0 ? Math.abs(gap / std) <= zBand : Math.abs(gap) <= band;
        row.tier_mean = mean; row.tier_std = has(std) ? std : null; row.gap = gap;
        row.status = neutral ? "Sekitar rata-rata" : gap > 0 ? "Di atas rata-rata" : "Di bawah rata-rata";
      }
      return row;
    });
  }

  function overall(table) {
    const t = table.filter((r) => r.fused !== null && r.tier_mean !== null);
    if (!t.length) return null;
    const mean = (k) => t.reduce((s, r) => s + r[k], 0) / t.length;
    return { fused: mean("fused"), tier: mean("tier_mean"), n: t.length };
  }

  function nearestTier(fused, bench) {
    const dists = {};
    for (const t of TIERS) {
      const b = (bench && bench[String(t)]) || {};
      const diffs = ASPECTS.filter((a) => fused[a].fused !== null && b[a]).map((a) => Math.abs(fused[a].fused - b[a].mean));
      if (diffs.length) dists[t] = diffs.reduce((s, x) => s + x, 0) / diffs.length;
    }
    const keys = Object.keys(dists);
    if (!keys.length) return { tier: null, dists };
    let best = keys[0];
    for (const k of keys) if (dists[k] < dists[best]) best = k;
    return { tier: Number(best), dists };
  }

  function disagreements(fused, threshold = DISAGREE_THRESHOLD) {
    return ASPECTS.filter((a) => fused[a].model !== null && fused[a].user !== null &&
      Math.abs(fused[a].model - fused[a].user) >= threshold);
  }

  const f2 = (x) => x.toFixed(2);
  const sg = (x) => (x >= 0 ? "+" : "-") + Math.abs(x).toFixed(2);

  /* ringkasan berbasis aturan; tanda ** untuk huruf tebal */
  function ruleSummary(table, ov, near, tier, diff) {
    const t = table.filter((r) => r.fused !== null && r.tier_mean !== null);
    if (!t.length || !ov) return "";
    const gap = ov.fused - ov.tier;
    const pos = Math.abs(gap) <= 0.15 ? "sekitar rata-rata" : gap > 0 ? "di atas rata-rata" : "di bawah rata-rata";
    const parts = [`Skor keseluruhan **${f2(ov.fused)}/5**, ${pos} hotel ${tier}★ (${sg(gap)}).`];
    if (t.length >= 2) {
      let best = t[0], worst = t[0];
      for (const r of t) { if (r.gap > best.gap) best = r; if (r.gap < worst.gap) worst = r; }
      const bits = [];
      if (best.gap > 0) bits.push(`Aspek terkuat: **${best.aspek}** (${sg(best.gap)})`);
      else bits.push(`Tidak ada aspek di atas rata-rata, yang paling dekat: **${best.aspek}** (${sg(best.gap)})`);
      if (worst.gap < 0) bits.push(`terlemah: **${worst.aspek}** (${sg(worst.gap)})`);
      parts.push(bits.join(", ") + ".");
    }
    if (near !== null && near !== undefined) parts.push(`Profilnya paling mirip hotel ${near}★.`);
    if (diff.length) parts.push("Skor model dan rating kamu berbeda jauh pada " + diff.join(", ") + ".");
    return parts.join(" ");
  }

  const availableTiers = (bench) => Object.keys(bench || {}).map(Number).sort((a, b) => a - b);

  return { ASPECTS, TIERS, fuse, compare, overall, nearestTier, disagreements, ruleSummary, availableTiers };
});
