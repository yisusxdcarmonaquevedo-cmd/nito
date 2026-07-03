// Nito — feed de ofertas bilingüe (ES/EN) con búsqueda dentro de la categoría
// activa, filtros, orden, guardados y pie informativo.
// Guardados: solo se persisten ASINs (localStorage). La vista "Guardadas" se pinta
// filtrando el feed VIVO -> si una oferta caduca desaparece de ahí, y si su precio
// cambia se muestra el actualizado. Sin lógica extra de sincronización.
const MARKET = "us";
const CUR = { USD: "$", EUR: "€", GBP: "£" };
const CATS = [
  "Tecnología y Gadgets",
  "Hogar y Cocina",
  "Deporte y Fitness",
  "Salud, Belleza y Cuidado Personal",
  "Moda y Accesorios",
  "Entretenimiento y Oficina",
];
const CAT_EN = {
  "Tecnología y Gadgets": "Tech & Gadgets",
  "Hogar y Cocina": "Home & Kitchen",
  "Deporte y Fitness": "Sports & Fitness",
  "Salud, Belleza y Cuidado Personal": "Health & Beauty",
  "Moda y Accesorios": "Fashion & Accessories",
  "Entretenimiento y Oficina": "Entertainment & Office",
};

const STR = {
  es: {
    all: "Todas",
    searchPh: "Buscar ofertas…",
    searchPhIn: (c) => `Buscar en ${c}…`,
    region: "Amazon EE.UU.",
    sortLabel: "Ordenar",
    sortOpts: { recent: "Más recientes", discount: "Mayor descuento", price: "Precio más bajo", rating: "Mejor valoradas" },
    results: (n) => `<b>${n}</b> oferta${n === 1 ? "" : "s"}`,
    inCat: (c) => ` en <b>${c}</b>`,
    forQ: (q) => ` para “<b>${q}</b>”`,
    savedLabel: "Guardadas",
    savedInfo: " guardadas",
    saveTip: "Guardar oferta",
    emptyTitle: "Nada por aquí…",
    emptySub: "No hay ofertas que encajen con tu búsqueda ahora mismo. Prueba otra categoría o vuelve en un rato: entran ofertas nuevas durante todo el día.",
    emptySavedTitle: "No tienes ofertas guardadas",
    emptySavedSub: "Toca el corazón de cualquier oferta para guardarla aquí. Si una oferta guardada caduca, se retira sola.",
    cta: "Ver oferta ↗",
    save: "ahorras",
    verified: "✓ comprobado",
    newBadge: "Nuevo",
    disclaimer: "Precio orientativo · consulta el final en Amazon",
    blurb: "Encontramos las mejores ofertas de Amazon, las verificamos y te las servimos listas. Tú solo ahorras.",
    catsTitle: "Categorías",
    how: "Cómo funciona",
    aff: "Aviso de afiliados",
    contact: "Contacto",
    updated: "Actualizado",
    legal: "En calidad de afiliado de Amazon, Nito obtiene ingresos por las compras adscritas que cumplen los requisitos aplicables.",
    loadError: "No se pudieron cargar las ofertas. Inténtalo más tarde.",
    modalOk: "Entendido",
    info: {
      como: { t: "Cómo funciona Nito", b: "Rastreamos las ofertas de Amazon durante todo el día, descartamos las flojas (menos de un 30% de descuento o mala valoración) y comprobamos una a una que sigan activas antes de mostrártelas. Cada tarjeta indica cuándo fue verificada por última vez." },
      afiliados: { t: "Aviso de afiliados", b: "Nito participa en el Programa de Afiliados de Amazon. Cuando compras a través de nuestros enlaces, Amazon nos paga una pequeña comisión sin coste extra para ti. Es lo que nos permite mantener el servicio gratis." },
    },
  },
  en: {
    all: "All",
    searchPh: "Search deals…",
    searchPhIn: (c) => `Search in ${c}…`,
    region: "Amazon US",
    sortLabel: "Sort",
    sortOpts: { recent: "Newest", discount: "Biggest discount", price: "Lowest price", rating: "Top rated" },
    results: (n) => `<b>${n}</b> deal${n === 1 ? "" : "s"}`,
    inCat: (c) => ` in <b>${c}</b>`,
    forQ: (q) => ` for “<b>${q}</b>”`,
    savedLabel: "Saved",
    savedInfo: " saved",
    saveTip: "Save deal",
    emptyTitle: "Nothing here…",
    emptySub: "No deals match your search right now. Try another category or check back soon — new deals come in all day.",
    emptySavedTitle: "No saved deals yet",
    emptySavedSub: "Tap the heart on any deal to save it here. If a saved deal expires, it's removed automatically.",
    cta: "See deal ↗",
    save: "you save",
    verified: "✓ checked",
    newBadge: "New",
    disclaimer: "Indicative price · check the final price on Amazon",
    blurb: "We find the best Amazon deals, verify them, and serve them ready. You just save.",
    catsTitle: "Categories",
    how: "How it works",
    aff: "Affiliate disclosure",
    contact: "Contact",
    updated: "Updated",
    legal: "As an Amazon Associate, Nito earns from qualifying purchases.",
    loadError: "Couldn't load deals. Please try again later.",
    modalOk: "Got it",
    info: {
      como: { t: "How Nito works", b: "We track Amazon deals all day long, discard the weak ones (less than 30% off or poorly rated) and check one by one that they're still live before showing them. Each card shows when it was last verified." },
      afiliados: { t: "Affiliate disclosure", b: "Nito participates in the Amazon Associates Program. When you buy through our links, Amazon pays us a small commission at no extra cost to you. That's what keeps this service free." },
    },
  },
};

let ALL = [];
let META = {};
let active = "__all__";
let query = "";
let sortBy = "recent";
let savedMode = false;
let saved = new Set(JSON.parse(localStorage.getItem("nito-saved") || "[]"));
let lang = localStorage.getItem("nito-lang") || ((navigator.language || "en").toLowerCase().startsWith("es") ? "es" : "en");
let theme = localStorage.getItem("nito-theme") ||
  (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

/* ---------- modo oscuro (se aplica al instante, antes de cargar el feed) ---------- */
const MOON_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 14.5 A8.5 8.5 0 1 1 9.5 4 A7 7 0 0 0 20 14.5 Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>`;
const SUN_SVG = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="4.5" stroke="currentColor" stroke-width="2"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;

function applyTheme() {
  document.body.classList.toggle("dark", theme === "dark");
  const btn = document.getElementById("theme-toggle");
  btn.innerHTML = theme === "dark" ? SUN_SVG : MOON_SVG;
  btn.setAttribute("aria-label", theme === "dark" ? "Modo claro / Light mode" : "Modo oscuro / Dark mode");
  // El logo del header cambia a su variante clara sobre fondo oscuro.
  const logo = document.querySelector(".brand-logo");
  if (logo) logo.src = theme === "dark" ? "logo_dark.png?v=1" : "logo.png?v=1";
}
document.getElementById("theme-toggle").addEventListener("click", () => {
  theme = theme === "dark" ? "light" : "dark";
  localStorage.setItem("nito-theme", theme);
  applyTheme();
});
applyTheme();

const t = () => STR[lang];
const catLabel = (c) => (c === "__all__" ? t().all : lang === "en" ? CAT_EN[c] || c : c);
const dispTitle = (d) => (lang === "es" ? d.title_es || d.title : d.title);

fetch(`deals_${MARKET}.json`, { cache: "no-store" })
  .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
  .then((data) => {
    ALL = data.deals || [];
    META = data;
    pruneSaved();
    initLang();
    initSearch();
    initSort();
    initSaved();
    initBanner();
    initFooterEvents();
    applyLang();
  })
  .catch((err) => {
    document.getElementById("result-info").textContent = t().loadError;
    console.error("Feed error:", err);
  });

/* ---------- guardados ---------- */
function pruneSaved() {
  // Si una oferta ya no está en el feed (caducó), sale también de guardados.
  const vivos = new Set(ALL.map((d) => d.asin));
  saved = new Set([...saved].filter((a) => vivos.has(a)));
  persistSaved();
}
function persistSaved() {
  localStorage.setItem("nito-saved", JSON.stringify([...saved]));
}
function initSaved() {
  document.getElementById("saved-btn").addEventListener("click", () => {
    savedMode = !savedMode;
    const btn = document.getElementById("saved-btn");
    btn.classList.toggle("active", savedMode);
    btn.setAttribute("aria-pressed", String(savedMode));
    render();
  });
  document.getElementById("grid").addEventListener("click", (e) => {
    const b = e.target.closest(".save-btn");
    if (!b) return;
    e.preventDefault();
    const asin = b.dataset.asin;
    if (saved.has(asin)) saved.delete(asin);
    else saved.add(asin);
    persistSaved();
    updateSavedUI();
    if (savedMode) render();
    else b.classList.toggle("on", saved.has(asin));
  });
}
function updateSavedUI() {
  const n = saved.size;
  const count = document.getElementById("saved-count");
  count.textContent = n;
  count.hidden = n === 0;
  document.getElementById("saved-label").textContent = t().savedLabel;
}

/* ---------- idioma ---------- */
function initLang() {
  document.querySelectorAll(".langbox button").forEach((b) =>
    b.addEventListener("click", () => {
      if (b.dataset.lang === lang) return;
      lang = b.dataset.lang;
      localStorage.setItem("nito-lang", lang);
      applyLang();
    })
  );
}

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll(".langbox button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
  document.getElementById("region-label").textContent = t().region;
  document.getElementById("sort-label").textContent = t().sortLabel;
  const sel = document.getElementById("sort");
  sel.innerHTML = Object.entries(t().sortOpts)
    .map(([v, l]) => `<option value="${v}"${v === sortBy ? " selected" : ""}>${l}</option>`)
    .join("");
  const inp = document.getElementById("search");
  inp.placeholder = active === "__all__" ? t().searchPh : t().searchPhIn(catLabel(active));
  document.getElementById("footer-blurb").textContent = t().blurb;
  document.getElementById("footer-cats-title").textContent = t().catsTitle;
  document.getElementById("link-como").textContent = t().how;
  document.getElementById("link-afiliados").textContent = t().aff;
  document.getElementById("link-contacto").textContent = t().contact;
  document.getElementById("updated-label").textContent = t().updated;
  document.getElementById("legal-line").textContent = t().legal;
  document.getElementById("year").textContent = new Date().getFullYear();
  document.getElementById("gen-time").textContent = fmtTime(META.generated_at);
  document.getElementById("footer-cats").innerHTML = CATS.map(
    (c) => `<li><a data-cat="${esc(c)}">${esc(catLabel(c))}</a></li>`
  ).join("");
  updateSavedUI();
  initFilters();
  buildBanner();
  render();
}

/* ---------- banner rotatorio (se alimenta de los mejores chollos vivos) ---------- */
let hbIndex = 0;
let hbTimer = null;

function initBanner() {
  document.getElementById("hb-prev").addEventListener("click", () => hbGo(-1));
  document.getElementById("hb-next").addEventListener("click", () => hbGo(1));
  document.getElementById("hb-dots").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-i]");
    if (!b) return;
    hbIndex = Number(b.dataset.i);
    hbApply();
    hbRestart();
  });
  const sec = document.getElementById("hero-banner");
  sec.addEventListener("mouseenter", hbStop);   // pausa al pasar el ratón
  sec.addEventListener("mouseleave", hbRestart);
}

function buildBanner() {
  // Los 4 mejores chollos vigentes (mayor descuento, con foto y descripción).
  // Como el feed caduca y se renueva solo, el banner se regenera automáticamente.
  const top = ALL
    .filter((d) => d.image && (d.post || d.post_en))
    .sort((a, b) => (b.discount_pct || 0) - (a.discount_pct || 0))
    .slice(0, 4);
  const sec = document.getElementById("hero-banner");
  if (top.length < 2) {
    sec.hidden = true;
    hbStop();
    return;
  }
  sec.hidden = false;
  document.getElementById("hb-track").innerHTML = top.map((d) => {
    const post = lang === "en" ? d.post_en || d.post : d.post || d.post_en;
    return `<div class="hb-slide">
      <div class="hb-text">
        <span class="hb-badge">-${Math.round(d.discount_pct || 0)}%</span>
        <h2>${esc(dispTitle(d))}</h2>
        <p>${esc(post || "")}</p>
        <a class="hb-cta" href="${esc(d.url)}" target="_blank" rel="nofollow sponsored noopener">${t().cta}</a>
      </div>
      <div class="hb-img"><img src="${esc(d.image)}" alt="${esc(dispTitle(d))}" loading="lazy"></div>
    </div>`;
  }).join("");
  document.getElementById("hb-dots").innerHTML = top
    .map((_, i) => `<button data-i="${i}" aria-label="Ir al ${i + 1}"></button>`)
    .join("");
  hbIndex = 0;
  hbApply();
  hbRestart();
}

function hbGo(delta) {
  const n = document.querySelectorAll(".hb-slide").length;
  if (!n) return;
  hbIndex = (hbIndex + delta + n) % n;
  hbApply();
  hbRestart();
}

function hbApply() {
  document.getElementById("hb-track").style.transform = `translateX(-${hbIndex * 100}%)`;
  document.querySelectorAll("#hb-dots button").forEach((b, i) =>
    b.classList.toggle("on", i === hbIndex)
  );
}

function hbStop() {
  if (hbTimer) clearInterval(hbTimer);
  hbTimer = null;
}

function hbRestart() {
  hbStop();
  hbTimer = setInterval(() => hbGo(1), 5000);  // rota solo cada 5 segundos
}

/* ---------- filtros ---------- */
function initFilters() {
  const nav = document.getElementById("filters");
  const cats = ["__all__", ...CATS];
  nav.innerHTML = cats
    .map((c) => {
      const n = c === "__all__" ? ALL.length : ALL.filter((d) => d.category === c).length;
      const badge = n > 0 ? `<span class="n">${n}</span>` : "";
      return `<button class="chip${c === active ? " active" : ""}" data-cat="${esc(c)}">${esc(catLabel(c))}${badge}</button>`;
    })
    .join("");
  nav.onclick = (e) => {
    const b = e.target.closest(".chip");
    if (b) selectCat(b.dataset.cat);
  };
}

function selectCat(cat) {
  active = cat;
  document.querySelectorAll(".chip").forEach((x) => x.classList.toggle("active", x.dataset.cat === cat));
  const inp = document.getElementById("search");
  inp.placeholder = cat === "__all__" ? t().searchPh : t().searchPhIn(catLabel(cat));
  render();
}

/* ---------- búsqueda (dentro de la categoría activa) ---------- */
function initSearch() {
  const inp = document.getElementById("search");
  const clr = document.getElementById("clear-search");
  inp.addEventListener("input", () => {
    query = inp.value.trim();
    clr.hidden = query === "";
    render();
  });
  clr.addEventListener("click", () => {
    inp.value = "";
    query = "";
    clr.hidden = true;
    inp.focus();
    render();
  });
}

function norm(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/* ---------- orden ---------- */
function initSort() {
  document.getElementById("sort").addEventListener("change", (e) => {
    sortBy = e.target.value;
    render();
  });
}

function sorted(list) {
  const l = [...list];
  if (sortBy === "discount") l.sort((a, b) => (b.discount_pct || 0) - (a.discount_pct || 0));
  else if (sortBy === "price") l.sort((a, b) => (a.price_new ?? 1e9) - (b.price_new ?? 1e9));
  else if (sortBy === "rating") l.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  else l.sort((a, b) => (b.published_at || "").localeCompare(a.published_at || ""));
  return l;
}

/* ---------- render ---------- */
function render() {
  let list = savedMode ? ALL.filter((d) => saved.has(d.asin)) : ALL;
  if (active !== "__all__") list = list.filter((d) => d.category === active);
  if (query) {
    const q = norm(query);
    list = list.filter((d) => norm(`${d.title} ${d.title_es || ""} ${d.asin}`).includes(q));
  }
  list = sorted(list);

  document.getElementById("grid").innerHTML = list.map(card).join("");

  const empty = document.getElementById("empty");
  empty.hidden = list.length > 0;
  if (!empty.hidden) {
    const sinGuardadas = savedMode && saved.size === 0;
    document.getElementById("empty-title").textContent = sinGuardadas ? t().emptySavedTitle : t().emptyTitle;
    document.getElementById("empty-sub").textContent = sinGuardadas ? t().emptySavedSub : t().emptySub;
  }

  let info = t().results(list.length);
  if (savedMode) info += t().savedInfo;
  if (active !== "__all__") info += t().inCat(esc(catLabel(active)));
  if (query) info += t().forQ(esc(query));
  document.getElementById("result-info").innerHTML = info;
}

function card(d) {
  const cur = CUR[d.currency] || "$";
  const price = d.price_new != null ? `<span class="price">${cur}${fmtNum(d.price_new)}</span>` : "";
  const old = d.price_old != null ? `<span class="old">${cur}${fmtNum(d.price_old)}</span>` : "";
  const save =
    d.price_old != null && d.price_new != null
      ? `<span class="save">${t().save} ${cur}${fmtNum(Math.round((d.price_old - d.price_new) * 100) / 100)}</span>`
      : "";
  const disc = d.discount_pct != null ? `<span class="badge">-${Math.round(d.discount_pct)}%</span>` : "";
  const nuevo = isNew(d.published_at) ? `<span class="badge-new">${t().newBadge}</span>` : "";
  const rate = d.rating != null ? `<span class="rate">★ ${d.rating}</span>` : "";
  const img = d.image
    ? `<img src="${esc(d.image)}" alt="${esc(dispTitle(d))}" loading="lazy" onerror="this.style.display='none'">`
    : "";
  const ver = d.revalidated_at ? `<p class="verified">${t().verified} ${fmtTime(d.revalidated_at)}</p>` : "";
  const post = lang === "en" ? d.post_en || d.post : d.post || d.post_en;
  const corazon = `<button class="save-btn${saved.has(d.asin) ? " on" : ""}" data-asin="${esc(d.asin)}" aria-label="${t().saveTip}" title="${t().saveTip}">
      <svg viewBox="0 0 24 24" fill="none"><path d="M12 20.5 C7 16 3.5 12.8 3.5 9.2 A4.7 4.7 0 0 1 12 6.6 A4.7 4.7 0 0 1 20.5 9.2 C20.5 12.8 17 16 12 20.5 Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
    </button>`;
  return `<article class="deal">
    <div class="thumb"><span class="thumb-fallback">Nito</span>${disc}${nuevo}${corazon}${img}</div>
    <div class="deal-body">
      ${d.category ? `<span class="pill">${esc(catLabel(d.category))}</span>` : ""}
      <h3 class="deal-title">${esc(dispTitle(d))}</h3>
      ${post ? `<p class="deal-post">${esc(post)}</p>` : ""}
      <div class="price-row">${price}${old}${save}${rate}</div>
      <a class="cta" href="${esc(d.url)}" target="_blank" rel="nofollow sponsored noopener">${t().cta}</a>
      ${ver}
      <p class="disclaimer">${t().disclaimer}</p>
    </div>
  </article>`;
}

/* ---------- footer ---------- */
function initFooterEvents() {
  document.getElementById("footer-cats").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-cat]");
    if (!a) return;
    selectCat(a.dataset.cat);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  document.querySelectorAll("a[data-info]").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      openInfo(a.dataset.info);
    })
  );
}

function openInfo(key) {
  const info = t().info[key];
  if (!info) return;
  const prev = document.getElementById("info-modal");
  if (prev) prev.remove();
  const div = document.createElement("div");
  div.id = "info-modal";
  div.style.cssText =
    "position:fixed;inset:0;background:rgba(14,44,58,.55);display:flex;align-items:center;justify-content:center;z-index:50;padding:16px";
  div.innerHTML = `<div style="background:#fff;border-radius:14px;max-width:440px;padding:24px 22px" role="dialog" aria-label="${esc(info.t)}">
      <h3 style="margin:0 0 10px;font-size:17px;color:#0E4A5E">${esc(info.t)}</h3>
      <p style="margin:0 0 18px;font-size:14px;color:#51707a;line-height:1.6">${esc(info.b)}</p>
      <button id="close-info" style="background:#16617D;color:#fff;border:0;border-radius:9px;padding:9px 18px;font-size:14px;cursor:pointer">${t().modalOk}</button>
    </div>`;
  div.addEventListener("click", (e) => {
    if (e.target === div || e.target.id === "close-info") div.remove();
  });
  document.body.appendChild(div);
}

/* ---------- utilidades ---------- */
function isNew(iso) {
  if (!iso) return false;
  return Date.now() - new Date(iso).getTime() < 12 * 3600 * 1000;
}
function fmtNum(n) {
  return Number.isInteger(n) ? n : n.toFixed(2);
}
function fmtTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(lang === "es" ? "es" : "en", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch (e) {
    return "";
  }
}
function esc(s) {
  return (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}
