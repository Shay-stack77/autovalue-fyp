/* ============================================================================
   AutoValue frontend — talks to the Flask API on the same origin (served at /).
   Renders the full valuation report: estimate + range, deal gauge, value
   breakdown, depreciation chart and comparable cars. Buildless vanilla JS.
   ========================================================================= */
const API = "";
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const $ = (id) => document.getElementById(id);
const els = {
  brand: $("brand"), model: $("model"), transmission: $("transmission"),
  fuelType: $("fuelType"), form: $("predict-form"), submit: $("submit-btn"),
  presets: $("presets"), headline: $("headline"), results: $("results"),
  dealCard: $("deal-card"), dealBody: $("deal-body"), whyBody: $("why-body"),
  deprBody: $("depr-body"), compBody: $("comp-body"),
  statusDot: $("status-dot"), statusText: $("status-text"),
  themeBtn: $("theme-btn"), printBtn: $("print-btn"),
  resultActions: $("result-actions"), saveBtn: $("save-btn"), addCompareBtn: $("addcompare-btn"),
  viewValue: $("view-value"), viewGarage: $("view-garage"), viewCompare: $("view-compare"),
  garageBody: $("garage-body"), compareBody: $("compare-body"),
  garageCount: $("garage-count"), compareCount: $("compare-count"), clearGarage: $("clear-garage"),
};

let modelsByBrand = {};
let currentValuation = null;     // { inputs, report } of the car on screen

const gbp = (n, dp = 0) => new Intl.NumberFormat("en-GB", {
  style: "currency", currency: "GBP", maximumFractionDigits: dp,
}).format(n);
const gbp0 = (n) => gbp(n, 0);
const num = (n) => new Intl.NumberFormat("en-GB").format(n);

/* ---------- theme ------------------------------------------------------- */
function applyTheme(dark) {
  document.documentElement.classList.toggle("dark", dark);
  try { localStorage.setItem("av-theme", dark ? "dark" : "light"); } catch {}
}
(function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("av-theme"); } catch {}
  const dark = saved ? saved === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(dark);
})();
els.themeBtn.addEventListener("click", () =>
  applyTheme(!document.documentElement.classList.contains("dark")));
els.printBtn.addEventListener("click", () => window.print());

/* ---------- vocab / dropdowns ------------------------------------------- */
function fillSelect(el, options, placeholder) {
  el.innerHTML = "";
  if (placeholder) {
    const o = document.createElement("option");
    o.value = ""; o.textContent = placeholder; o.disabled = true; o.selected = true;
    el.appendChild(o);
  }
  for (const v of options) {
    const o = document.createElement("option");
    o.value = v; o.textContent = v; el.appendChild(o);
  }
}

function setStatus(ok) {
  els.statusDot.className = "w-2 h-2 rounded-full " + (ok ? "bg-emerald-500" : "bg-rose-500");
  els.statusText.textContent = ok ? "model ready" : "model offline";
}

const PRESETS = [
  { label: "2019 BMW 3 Series", brand: "BMW", model: "3 Series", year: 2019, mileage: 28000, transmission: "Automatic", fuelType: "Diesel", engineSize: 2.0, askingPrice: 24000 },
  { label: "2017 Ford Fiesta", brand: "Ford", model: "Fiesta", year: 2017, mileage: 35000, transmission: "Manual", fuelType: "Petrol", engineSize: 1.0 },
  { label: "2020 VW Golf", brand: "Volkswagen", model: "Golf", year: 2020, mileage: 22000, transmission: "Manual", fuelType: "Petrol", engineSize: 1.5 },
  { label: "2018 Mercedes A Class", brand: "Mercedes", model: "A Class", year: 2018, mileage: 40000, transmission: "Automatic", fuelType: "Diesel", engineSize: 1.5 },
];

function renderPresets() {
  els.presets.innerHTML = "";
  PRESETS.forEach((p) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.textContent = p.label;
    b.addEventListener("click", () => { applyPreset(p); els.form.requestSubmit(); });
    els.presets.appendChild(b);
  });
}

function applyPreset(p) {
  els.brand.value = p.brand;
  els.brand.dispatchEvent(new Event("change"));
  els.model.value = p.model;
  els.transmission.value = p.transmission;
  els.fuelType.value = p.fuelType;
  $("year").value = p.year; $("mileage").value = p.mileage;
  $("engineSize").value = p.engineSize;
  $("askingPrice").value = p.askingPrice ?? "";
}

async function loadVocab() {
  const [health, vocab] = await Promise.all([
    fetch(`${API}/health`).then((r) => r.json()).catch(() => ({})),
    fetch(`${API}/vocab`).then((r) => r.json()).catch(() => ({})),
  ]);
  setStatus(!!health.model_loaded);
  modelsByBrand = vocab.models_by_brand || {};
  fillSelect(els.brand, vocab.brands || [], "Select brand");
  fillSelect(els.transmission, vocab.transmissions || [], "Select transmission");
  fillSelect(els.fuelType, vocab.fuelTypes || [], "Select fuel type");
  fillSelect(els.model, [], "Choose a brand first");
  renderPresets();
}

els.brand.addEventListener("change", () => {
  const list = modelsByBrand[els.brand.value] || [];
  fillSelect(els.model, list, list.length ? "Select model" : "No models available");
});

/* ---------- count-up ---------------------------------------------------- */
function countUp(node, to) {
  if (REDUCED) { node.textContent = gbp0(to); return; }
  const dur = 700, t0 = performance.now();
  function step(t) {
    const k = Math.min(1, (t - t0) / dur);
    const eased = 1 - Math.pow(1 - k, 3);
    node.textContent = gbp0(Math.round(to * eased));
    if (k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ---------- renderers --------------------------------------------------- */
function renderHeadline(b) {
  const hasRange = b.range_low != null && b.range_high != null;
  let rangeHtml = "";
  if (hasRange) {
    const pct = Math.max(3, Math.min(97, ((b.estimate - b.range_low) / (b.range_high - b.range_low)) * 100));
    rangeHtml = `
      <div class="w-full mt-5">
        <div class="range-track"><span class="range-marker" style="left:${pct}%"></span></div>
        <div class="flex justify-between text-xs text-slate-500 dark:text-slate-400 mt-1.5 num">
          <span>${gbp0(b.range_low)}</span><span>${gbp0(b.range_high)}</span>
        </div>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">80% confidence range</p>
      </div>`;
  }
  els.headline.className = "flex-1 flex flex-col items-center justify-center text-center reveal";
  els.headline.innerHTML = `
    <p class="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">Estimated value</p>
    <p class="price-pill num text-brand dark:text-brand-light" id="price-figure" aria-live="polite">${gbp0(b.estimate)}</p>
    ${rangeHtml}
    <p class="mt-4 inline-flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M2 12h20"/></svg>
      Market-adjusted &times;${b.market_factor} toward current prices
    </p>`;
  countUp($("price-figure"), b.estimate);
}

const DEAL_META = {
  great:      { fill: "#059669", text: "text-emerald-700 dark:text-emerald-400", icon: "M20 6 9 17l-5-5" },
  good:       { fill: "#16a34a", text: "text-green-700 dark:text-green-400",   icon: "M20 6 9 17l-5-5" },
  fair:       { fill: "#0284c7", text: "text-sky-700 dark:text-sky-400",       icon: "M5 12h14" },
  high:       { fill: "#d97706", text: "text-amber-700 dark:text-amber-400",   icon: "M12 19V5M5 12l7-7 7 7" },
  overpriced: { fill: "#e11d48", text: "text-rose-700 dark:text-rose-400",     icon: "M12 5v14M5 12l7 7 7-7" },
};
const DEAL_ORDER = ["great", "good", "fair", "high", "overpriced"];

function gaugeArc(startDeg, endDeg, color) {
  const r = 78, cx = 100, cy = 100;
  const pt = (deg) => [cx + r * Math.cos((Math.PI * deg) / 180), cy - r * Math.sin((Math.PI * deg) / 180)];
  const [x1, y1] = pt(startDeg), [x2, y2] = pt(endDeg);
  return `<path d="M ${x1} ${y1} A ${r} ${r} 0 0 0 ${x2} ${y2}" stroke="${color}" stroke-width="14" fill="none" stroke-linecap="butt"/>`;
}

function renderDeal(deal, estimate) {
  if (!deal) { els.dealCard.classList.add("hidden"); return; }
  els.dealCard.classList.remove("hidden");
  els.dealCard.classList.add("reveal");
  const meta = DEAL_META[deal.rating] || DEAL_META.fair;
  // needle: clamp delta to [-20,+20]% -> angle 180(left/great)..0(right/overpriced)
  const d = Math.max(-20, Math.min(20, deal.delta_pct));
  const angle = 180 - ((d + 20) / 40) * 180;
  const nx = 100 + 62 * Math.cos((Math.PI * angle) / 180);
  const ny = 100 - 62 * Math.sin((Math.PI * angle) / 180);
  const segs = [[180,144],[144,108],[108,72],[72,36],[36,0]];
  const arcs = DEAL_ORDER.map((k, i) => gaugeArc(segs[i][0], segs[i][1], DEAL_META[k].fill)).join("");
  const sign = deal.delta_gbp > 0 ? "+" : "−";
  const verb = deal.delta_gbp > 0 ? "above" : "below";
  els.dealBody.innerHTML = `
    <div class="flex flex-col items-center">
      <svg viewBox="0 0 200 116" class="w-56 max-w-full" role="img" aria-label="Deal rating gauge showing ${deal.label}">
        ${arcs}
        <line class="gauge-needle" x1="100" y1="100" x2="${nx}" y2="${ny}" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
        <circle cx="100" cy="100" r="5" fill="currentColor"/>
      </svg>
      <p class="text-2xl font-bold ${meta.text} flex items-center gap-2 -mt-2">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="${meta.icon}"/></svg>
        ${deal.label}
      </p>
      <p class="text-sm text-slate-600 dark:text-slate-300 text-center mt-1">
        The asking price is <span class="num font-medium">${sign}${gbp0(Math.abs(deal.delta_gbp))}</span>
        (${Math.abs(deal.delta_pct)}%) ${verb} our estimate of <span class="num">${gbp0(estimate)}</span>.
      </p>
    </div>`;
}

function renderWhy(items) {
  if (!items || !items.length) { els.whyBody.innerHTML = "<p class='text-sm text-slate-400'>Not available.</p>"; return; }
  const max = Math.max(...items.map((i) => Math.abs(i.impact_gbp)), 1);
  els.whyBody.innerHTML = items.map((i) => {
    const w = Math.max(4, (Math.abs(i.impact_gbp) / max) * 100);
    const pos = i.impact_gbp >= 0;
    return `
      <div class="mb-3">
        <div class="flex justify-between text-xs mb-1">
          <span class="text-slate-700 dark:text-slate-300">${i.label}</span>
          <span class="num font-medium ${pos ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}">${pos ? "+" : "−"}${gbp0(Math.abs(i.impact_gbp))}</span>
        </div>
        <div class="bar-track"><div class="bar-fill" style="background:${pos ? "#059669" : "#e11d48"}" data-w="${w}"></div></div>
      </div>`;
  }).join("");
  // animate widths after paint
  requestAnimationFrame(() =>
    els.whyBody.querySelectorAll(".bar-fill").forEach((el) => { el.style.width = el.dataset.w + "%"; }));
}

function renderDepreciation(series) {
  if (!series || series.length < 2) { els.deprBody.innerHTML = "<p class='text-sm text-slate-400'>Not available.</p>"; return; }
  const W = 460, H = 210, pad = 38;
  const vals = series.map((p) => p.value);
  const maxV = Math.max(...vals), minV = Math.min(...vals) * 0.9;
  const x = (i) => pad + (i / (series.length - 1)) * (W - pad * 2);
  const y = (v) => H - pad - ((v - minV) / (maxV - minV || 1)) * (H - pad * 2);
  const linePts = series.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  const areaPts = `${pad},${H - pad} ${linePts} ${W - pad},${H - pad}`;
  // chart is presentational (aria-hidden via the wrapping svg); the visually
  // hidden data table below is the accessible equivalent. Dots are not
  // focusable, so the chart never traps keyboard focus inside aria-hidden.
  const dots = series.map((p, i) =>
    `<circle class="chart-dot" cx="${x(i)}" cy="${y(p.value)}" r="3.5" fill="#1E40AF"
       data-x="${x(i)}" data-y="${y(p.value)}" data-label="${p.calendar_year} · ${gbp0(p.value)} (${p.pct_of_today}%)"></circle>
     <text x="${x(i)}" y="${H - pad + 16}" text-anchor="middle" font-size="10" class="num" fill="currentColor" opacity="0.55">${p.calendar_year}</text>`
  ).join("");
  const last = series[series.length - 1];
  const rows = series.map((p) => `<tr><td>${p.calendar_year}</td><td>${num(p.mileage)} mi</td><td>${gbp0(p.value)}</td><td>${p.pct_of_today}%</td></tr>`).join("");
  els.deprBody.innerHTML = `
    <div class="chart-wrap text-slate-400 dark:text-slate-500">
      <svg viewBox="0 0 ${W} ${H}" class="w-full" aria-hidden="true">
        <defs><linearGradient id="deprFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#3B82F6" stop-opacity="0.25"/><stop offset="100%" stop-color="#3B82F6" stop-opacity="0"/>
        </linearGradient></defs>
        <polyline points="${areaPts}" fill="url(#deprFill)" stroke="none"/>
        <polyline points="${linePts}" fill="none" stroke="#1E40AF" stroke-width="2.5"/>
        ${dots}
      </svg>
      <div class="chart-tooltip" id="depr-tip"></div>
    </div>
    <p class="text-xs text-slate-500 dark:text-slate-400 mt-2">
      By ${last.calendar_year} (age ${last.age}, ~${num(last.mileage)} miles) the model projects about
      <span class="num font-semibold text-slate-700 dark:text-slate-200">${gbp0(last.value)}</span> — ${last.pct_of_today}% of today's value.
    </p>
    <table class="sr-only"><caption>Depreciation forecast</caption>
      <thead><tr><th>Year</th><th>Mileage</th><th>Value</th><th>% of today</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  // tooltip wiring
  const tip = $("depr-tip"), wrap = els.deprBody.querySelector(".chart-wrap");
  const svg = wrap.querySelector("svg");
  const show = (dot) => {
    const r = svg.getBoundingClientRect(), scale = r.width / W;
    tip.textContent = dot.dataset.label;
    tip.style.left = (+dot.dataset.x) * scale + "px";
    tip.style.top = (+dot.dataset.y) * scale + "px";
    tip.classList.add("show");
  };
  wrap.querySelectorAll(".chart-dot").forEach((dot) => {
    dot.addEventListener("mouseenter", () => show(dot));
    dot.addEventListener("mouseleave", () => tip.classList.remove("show"));
  });
}

function renderComparables(items) {
  if (!items || !items.length) { els.compBody.innerHTML = "<p class='text-sm text-slate-400'>None found.</p>"; return; }
  els.compBody.innerHTML = `
    <div class="-mx-2">${items.map((c) => `
      <div class="comp-row flex items-center justify-between gap-3 px-2 py-2.5">
        <div class="min-w-0">
          <p class="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">${c.year} ${c.brand} ${c.model}</p>
          <p class="text-xs text-slate-500 dark:text-slate-400 num truncate">${num(c.mileage)} mi · ${c.transmission} · ${c.fuelType} · ${c.engineSize}L</p>
        </div>
        <p class="text-sm font-semibold num text-slate-900 dark:text-slate-100 shrink-0">${gbp0(c.price)}</p>
      </div>`).join("")}</div>`;
}

/* ---------- skeleton + submit ------------------------------------------- */
function showSkeleton() {
  els.headline.className = "flex-1 flex flex-col items-center justify-center w-full";
  els.headline.innerHTML = `
    <div class="skeleton h-3 w-24 mb-3"></div>
    <div class="skeleton h-10 w-44 mb-4"></div>
    <div class="skeleton h-2 w-full"></div>`;
}

els.form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const data = Object.fromEntries(new FormData(els.form).entries());
  els.submit.disabled = true;
  // gate the save/compare actions until this valuation finishes loading
  els.saveBtn.disabled = true; els.addCompareBtn.disabled = true;
  currentValuation = null;
  showSkeleton();
  try {
    const r = await fetch(`${API}/predict`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await r.json();
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    renderHeadline(body);
    renderDeal(body.deal, body.estimate);
    renderWhy(body.explanation);
    renderDepreciation(body.depreciation);
    renderComparables(body.comparables);
    els.results.classList.remove("hidden");
    // capture for save / compare, reset action-button states
    currentValuation = { inputs: data, report: body };
    els.resultActions.classList.remove("hidden");
    els.saveBtn.disabled = false; els.addCompareBtn.disabled = false;
    resetActionBtn(els.saveBtn, "Save to garage");
    resetActionBtn(els.addCompareBtn, "Add to compare");
  } catch (err) {
    els.headline.className = "flex-1 flex flex-col items-center justify-center text-center";
    els.headline.innerHTML = `<p class="text-sm text-rose-600 dark:text-rose-400">Error: ${err.message}</p>`;
  } finally {
    els.submit.disabled = false;
  }
});

/* ===================== Garage + Compare + view router =================== */
const LABEL = (i) => `${i.year} ${i.brand} ${i.model}`;
const SPEC = (i) => `${num(i.mileage)} mi · ${i.transmission} · ${i.fuelType} · ${i.engineSize}L`;
const DEAL_PILL = {
  great: "bg-emerald-100 text-emerald-700", good: "bg-green-100 text-green-700",
  fair: "bg-sky-100 text-sky-700", high: "bg-amber-100 text-amber-700",
  overpriced: "bg-rose-100 text-rose-700",
};

function loadStore(key) { try { return JSON.parse(localStorage.getItem(key)) || []; } catch { return []; } }
function saveStore(key, arr) { try { localStorage.setItem(key, JSON.stringify(arr)); } catch {} }
let garage = loadStore("av-garage");
let compareSet = loadStore("av-compare");

function resetActionBtn(btn, label) {
  btn.classList.remove("done");
  btn.lastChild.textContent = " " + label;
}
function markDone(btn, label) { btn.classList.add("done"); btn.lastChild.textContent = " " + label; }

function updateCounts() {
  els.garageCount.textContent = garage.length;
  els.compareCount.textContent = compareSet.length;
  els.garageCount.classList.toggle("show", garage.length > 0);
  els.compareCount.classList.toggle("show", compareSet.length > 0);
  els.clearGarage.classList.toggle("hidden", garage.length === 0);
}

/* ---- view router ---- */
function switchView(view) {
  for (const [name, el] of [["value", els.viewValue], ["garage", els.viewGarage], ["compare", els.viewCompare]]) {
    el.hidden = name !== view;
  }
  document.querySelectorAll(".view-tab").forEach((t) => {
    const on = t.dataset.view === view;
    t.classList.toggle("is-active", on);
    if (on) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current");
  });
  if (view === "garage") renderGarage();
  if (view === "compare") renderCompare();
  if (location.hash.slice(1) !== view) history.replaceState(null, "", "#" + view);
  window.scrollTo({ top: 0, behavior: REDUCED ? "auto" : "smooth" });
}
document.querySelectorAll(".view-tab").forEach((t) =>
  t.addEventListener("click", () => switchView(t.dataset.view)));
window.addEventListener("hashchange", () => {
  const v = location.hash.slice(1);
  if (["value", "garage", "compare"].includes(v)) switchView(v);
});

/* ---- save / add-to-compare ---- */
els.saveBtn.addEventListener("click", () => {
  if (!currentValuation) return;
  const entry = { id: Date.now() + "" + Math.round(Math.random() * 999), ...currentValuation };
  garage.unshift(entry); saveStore("av-garage", garage);
  updateCounts(); markDone(els.saveBtn, "Saved ✓");
});
els.addCompareBtn.addEventListener("click", () => {
  if (!currentValuation) return;
  if (compareSet.length >= 4) { markDone(els.addCompareBtn, "Compare full (4)"); return; }
  compareSet.push({ id: Date.now() + "" + Math.round(Math.random() * 999), ...currentValuation });
  saveStore("av-compare", compareSet);
  updateCounts(); markDone(els.addCompareBtn, "Added to compare ✓");
});
els.clearGarage.addEventListener("click", () => {
  garage = []; saveStore("av-garage", garage); updateCounts(); renderGarage();
});

/* ---- garage render ---- */
function renderGarage() {
  if (!garage.length) {
    els.garageBody.innerHTML = `<div class="card p-8 text-center text-sm text-slate-500 dark:text-slate-400">
      No saved valuations yet. Value a car, then choose <span class="font-medium">Save to garage</span>.</div>`;
    return;
  }
  els.garageBody.innerHTML = `<div class="garage-grid">${garage.map((e) => {
    const r = e.report, i = e.inputs;
    const deal = r.deal ? `<span class="pill ${DEAL_PILL[r.deal.rating] || ""}">${r.deal.label}</span>` : "";
    return `<div class="card p-4 garage-card" data-id="${e.id}">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="font-medium text-sm truncate">${LABEL(i)}</p>
          <p class="text-xs text-slate-500 dark:text-slate-400 num truncate">${SPEC(i)}</p>
        </div>
        <button class="icon-btn danger g-remove" data-id="${e.id}" aria-label="Remove ${LABEL(i)} from garage" title="Remove">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>
        </button>
      </div>
      <p class="price-pill num text-brand dark:text-brand-light" style="font-size:1.6rem">${gbp0(r.estimate)}</p>
      <div class="flex items-center justify-between">
        <p class="text-xs text-slate-500 dark:text-slate-400 num">${r.range_low != null ? gbp0(r.range_low) + "–" + gbp0(r.range_high) : ""}</p>
        ${deal}
      </div>
      <div class="flex gap-2 mt-1">
        <button class="action-btn g-view" data-id="${e.id}" style="font-size:0.78rem;padding:0.4rem 0.7rem">View</button>
        <button class="action-btn g-compare" data-id="${e.id}" style="font-size:0.78rem;padding:0.4rem 0.7rem">Compare</button>
      </div>
    </div>`;
  }).join("")}</div>`;
  els.garageBody.querySelectorAll(".g-remove").forEach((b) => b.addEventListener("click", () => {
    garage = garage.filter((e) => e.id !== b.dataset.id); saveStore("av-garage", garage); updateCounts(); renderGarage();
  }));
  els.garageBody.querySelectorAll(".g-view").forEach((b) => b.addEventListener("click", () => {
    const e = garage.find((x) => x.id === b.dataset.id); if (e) loadValuation(e);
  }));
  els.garageBody.querySelectorAll(".g-compare").forEach((b) => b.addEventListener("click", () => {
    const e = garage.find((x) => x.id === b.dataset.id);
    if (e && compareSet.length < 4 && !compareSet.some((c) => c.id === e.id)) {
      compareSet.push(e); saveStore("av-compare", compareSet); updateCounts();
    }
    switchView("compare");
  }));
}

/* re-display a saved car in the Value view */
function loadValuation(e) {
  currentValuation = { inputs: e.inputs, report: e.report };
  applyPreset({ ...e.inputs, year: e.inputs.year, askingPrice: e.inputs.askingPrice });
  renderHeadline(e.report);
  renderDeal(e.report.deal, e.report.estimate);
  renderWhy(e.report.explanation);
  renderDepreciation(e.report.depreciation);
  renderComparables(e.report.comparables);
  els.results.classList.remove("hidden");
  els.resultActions.classList.remove("hidden");
  resetActionBtn(els.saveBtn, "Save to garage");
  resetActionBtn(els.addCompareBtn, "Add to compare");
  switchView("value");
}

/* ---- compare render ---- */
function renderCompare() {
  if (compareSet.length < 1) {
    els.compareBody.innerHTML = `<div class="card p-8 text-center text-sm text-slate-500 dark:text-slate-400">
      Nothing to compare yet. Value a car and choose <span class="font-medium">Add to compare</span>, or add cars from your garage.</div>`;
    return;
  }
  const cell = (e, fn) => `<td>${fn(e)}</td>`;
  const rows = [
    ["Estimate", (e) => `<span class="num font-semibold text-brand dark:text-brand-light">${gbp0(e.report.estimate)}</span>`],
    ["80% range", (e) => e.report.range_low != null ? `<span class="num">${gbp0(e.report.range_low)} – ${gbp0(e.report.range_high)}</span>` : "—"],
    ["Deal", (e) => e.report.deal ? `<span class="pill ${DEAL_PILL[e.report.deal.rating] || ""}">${e.report.deal.label}</span>` : "—"],
    ["Mileage", (e) => `<span class="num">${num(e.inputs.mileage)} mi</span>`],
    ["Top value driver", (e) => { const x = (e.report.explanation || [])[0]; return x ? `${x.label} (${x.impact_gbp >= 0 ? "+" : "−"}${gbp0(Math.abs(x.impact_gbp))})` : "—"; }],
    ["Value in 5 yrs", (e) => { const d = e.report.depreciation; const last = d && d[d.length - 1]; return last ? `<span class="num">${gbp0(last.value)} (${last.pct_of_today}%)</span>` : "—"; }],
  ];
  els.compareBody.innerHTML = `<div class="card p-4 sm:p-5"><div class="cmp-wrap"><table class="cmp-table">
    <thead><tr><th></th>${compareSet.map((e) => `<th scope="col">
      <div class="flex items-start justify-between gap-2">
        <span>${LABEL(e.inputs)}</span>
        <button class="icon-btn danger c-remove" data-id="${e.id}" aria-label="Remove ${LABEL(e.inputs)} from compare" title="Remove">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>
      <span class="block text-xs font-normal text-slate-500 dark:text-slate-400 num">${SPEC(e.inputs)}</span>
    </th>`).join("")}</tr></thead>
    <tbody>${rows.map(([label, fn]) => `<tr><th scope="row">${label}</th>${compareSet.map((e) => cell(e, fn)).join("")}</tr>`).join("")}</tbody>
  </table></div></div>`;
  els.compareBody.querySelectorAll(".c-remove").forEach((b) => b.addEventListener("click", () => {
    compareSet = compareSet.filter((e) => e.id !== b.dataset.id); saveStore("av-compare", compareSet); updateCounts(); renderCompare();
  }));
}

updateCounts();
// restore the view from the URL hash on load (e.g. a bookmarked #garage)
const initialView = location.hash.slice(1);
if (["garage", "compare"].includes(initialView)) switchView(initialView);
loadVocab();
