// Grocy AI sidebar panel: book stock from the phone with the camera.
// Plain web component without build step or external libraries.

const MAX_SIDE = 1600; // px, photos are scaled down before upload
const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];

const TEXTS = {
  en: {
    title: "Grocy AI",
    plus: "Purchased (+)",
    minus: "Used (−)",
    barcode: "Barcode",
    scan: "Photo",
    amount: "Amount",
    bbd: "Best-before date",
    bbdPhoto: "Photograph best-before date",
    bbdOr: "or enter date",
    remove: "Remove",
    book: "Book",
    reading: "Reading barcode …",
    booking: "Booking …",
    noBarcode: "No barcode recognized – please try again or type it in.",
    needBarcode: "Please scan or enter a barcode first.",
    stock: "stock",
    created: "New product created from Open Food Facts.",
    src: {
      ai: "from photo",
      manual: "entered",
      default: "default shelf life",
      never: "never expires",
      unset: "no default shelf life set",
    },
    aiError: "Best-before date not readable from photo, default used",
    error: "Error",
  },
  de: {
    title: "Grocy AI",
    plus: "Eingekauft (+)",
    minus: "Verbraucht (−)",
    barcode: "Barcode",
    scan: "Foto",
    amount: "Menge",
    bbd: "MHD",
    bbdPhoto: "MHD fotografieren",
    bbdOr: "oder Datum eingeben",
    remove: "Entfernen",
    book: "Buchen",
    reading: "Lese Barcode …",
    booking: "Buche …",
    noBarcode: "Kein Barcode erkannt – bitte nochmal versuchen oder eintippen.",
    needBarcode: "Bitte zuerst einen Barcode scannen oder eingeben.",
    stock: "Bestand",
    created: "Neues Produkt über Open Food Facts angelegt.",
    src: {
      ai: "vom Foto",
      manual: "eingegeben",
      default: "Standard-Haltbarkeit",
      never: "läuft nie ab",
      unset: "keine Standard-Haltbarkeit hinterlegt",
    },
    aiError: "MHD auf dem Foto nicht lesbar, Standard verwendet",
    error: "Fehler",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

class GrocyAiPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._mode = "plus";
    this._barcode = "";
    this._amount = 1;
    this._bbdDate = "";
    this._bbdPhoto = null; // {blob, url}
    this._busy = "";
    this._message = null; // {ok, html}
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._render();
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.narrow = narrow;
  }

  get _t() {
    return (this._hass?.language || "en").startsWith("de") ? TEXTS.de : TEXTS.en;
  }

  _render() {
    const t = this._t;
    const plus = this._mode === "plus";
    const busy = Boolean(this._busy);
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <div class="title">${t.title}</div>
      </div>
      <div class="content">
        <div class="segment">
          <button id="plus" class="${plus ? "active" : ""}">${t.plus}</button>
          <button id="minus" class="${plus ? "" : "active"}">${t.minus}</button>
        </div>

        <label>${t.barcode}</label>
        <div class="row">
          <input id="barcode" inputmode="numeric" autocomplete="off" value="${esc(this._barcode)}">
          <button id="scan" class="secondary" ${busy ? "disabled" : ""}>📷 ${t.scan}</button>
        </div>

        <label>${t.amount}</label>
        <input id="amount" type="number" min="0.01" step="any" inputmode="decimal" value="${esc(this._amount)}">

        ${
          plus
            ? `<label>${t.bbd}</label>
               ${
                 this._bbdPhoto
                   ? `<div class="row photo">
                        <img src="${this._bbdPhoto.url}" alt="">
                        <button id="bbd-remove" class="secondary">✕ ${t.remove}</button>
                      </div>`
                   : `<button id="bbd-photo" class="secondary wide">📷 ${t.bbdPhoto}</button>
                      <div class="hint">${t.bbdOr}</div>
                      <input id="bbd-date" type="date" value="${esc(this._bbdDate)}">`
               }`
            : ""
        }

        <button id="book" class="primary" ${busy ? "disabled" : ""}>
          ${busy ? esc(this._busy) : t.book}
        </button>

        ${
          this._message
            ? `<div class="msg ${this._message.ok ? "ok" : "err"}">${this._message.html}</div>`
            : ""
        }
      </div>
      <input id="file-barcode" type="file" accept="image/*" capture="environment" hidden>
      <input id="file-bbd" type="file" accept="image/*" capture="environment" hidden>
    `;
    const $ = (id) => this.shadowRoot.getElementById(id);
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    menu.hass = this._hass;
    menu.narrow = this._narrow;

    $("plus").onclick = () => this._setMode("plus");
    $("minus").onclick = () => this._setMode("minus");
    $("barcode").oninput = (ev) => (this._barcode = ev.target.value.trim());
    $("amount").oninput = (ev) => (this._amount = ev.target.value);
    $("scan").onclick = () => $("file-barcode").click();
    $("file-barcode").onchange = (ev) => this._onBarcodePhoto(ev.target);
    $("file-bbd").onchange = (ev) => this._onBbdPhoto(ev.target);
    $("book").onclick = () => this._book();
    if ($("bbd-photo")) $("bbd-photo").onclick = () => $("file-bbd").click();
    if ($("bbd-date")) $("bbd-date").oninput = (ev) => (this._bbdDate = ev.target.value);
    if ($("bbd-remove")) $("bbd-remove").onclick = () => this._clearBbdPhoto(true);
  }

  _setMode(mode) {
    this._mode = mode;
    this._message = null;
    this._render();
  }

  _setBusy(text) {
    this._busy = text;
    this._render();
  }

  async _onBarcodePhoto(input) {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    this._message = null;
    this._setBusy(this._t.reading);
    try {
      const { bitmap, blob } = await shrink(file);
      let code = await detectLocally(bitmap);
      if (!code) {
        const result = await this._call("read_barcode", { image: await this._upload(blob) });
        code = result?.recognized ? result.barcode : "";
      }
      if (code) {
        this._barcode = code;
      } else {
        this._message = { ok: false, html: esc(this._t.noBarcode) };
      }
    } catch (err) {
      this._message = { ok: false, html: `${this._t.error}: ${esc(err.message || err)}` };
    }
    this._setBusy("");
  }

  async _onBbdPhoto(input) {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    const { blob } = await shrink(file);
    this._clearBbdPhoto(false);
    this._bbdPhoto = { blob, url: URL.createObjectURL(blob) };
    this._bbdDate = "";
    this._render();
  }

  _clearBbdPhoto(render) {
    if (this._bbdPhoto) URL.revokeObjectURL(this._bbdPhoto.url);
    this._bbdPhoto = null;
    if (render) this._render();
  }

  async _book() {
    const t = this._t;
    if (!this._barcode) {
      this._message = { ok: false, html: esc(t.needBarcode) };
      this._render();
      return;
    }
    this._message = null;
    this._setBusy(t.booking);
    try {
      const plus = this._mode === "plus";
      const data = { barcode: this._barcode, amount: Number(this._amount) || 1 };
      if (plus && this._bbdPhoto) data.image = await this._upload(this._bbdPhoto.blob);
      else if (plus && this._bbdDate) data.best_before_date = this._bbdDate;
      const res = await this._call(plus ? "add_stock" : "consume_stock", data);
      this._message = { ok: true, html: this._describe(res) };
      this._barcode = "";
      this._amount = 1;
      this._bbdDate = "";
      this._clearBbdPhoto(false);
    } catch (err) {
      this._message = { ok: false, html: `${t.error}: ${esc(err.message || err)}` };
    }
    this._setBusy("");
  }

  _describe(res) {
    const t = this._t;
    const sign = this._mode === "plus" ? "+" : "−";
    let html = `✅ <b>${esc(res.product_name)}</b>: ${sign}${esc(res.amount)} → ${t.stock} ${esc(res.stock_amount)}`;
    if (res.best_before_date) {
      const date = res.best_before_date.startsWith("2999") ? "∞" : esc(res.best_before_date);
      html += `<br>${t.bbd}: ${date} (${esc(t.src[res.best_before_source] || res.best_before_source)})`;
    }
    if (res.ai_error) html += `<br>⚠️ ${t.aiError} (${esc(res.ai_error)})`;
    if (res.product_created) html += `<br>🆕 ${t.created}`;
    return html;
  }

  async _call(service, data) {
    const res = await this._hass.callWS({
      type: "call_service",
      domain: "grocy_ai",
      service,
      service_data: data,
      return_response: true,
    });
    return res.response;
  }

  async _upload(blob) {
    const init = { method: "POST", body: blob, headers: { "Content-Type": blob.type } };
    const resp = this._hass.fetchWithAuth
      ? await this._hass.fetchWithAuth("/api/grocy_ai/photo", init)
      : await fetch("/api/grocy_ai/photo", {
          ...init,
          headers: { ...init.headers, Authorization: `Bearer ${this._hass.auth.data.access_token}` },
        });
    if (!resp.ok) throw new Error(`Upload ${resp.status}`);
    return resp.json();
  }
}

async function shrink(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  return { bitmap, blob };
}

// Use the browser's own barcode reader when available (Chrome on Android);
// otherwise the photo goes to AI Task via grocy_ai.read_barcode.
async function detectLocally(bitmap) {
  if (!("BarcodeDetector" in window)) return "";
  try {
    const supported = await window.BarcodeDetector.getSupportedFormats();
    const formats = BARCODE_FORMATS.filter((f) => supported.includes(f));
    if (!formats.length) return "";
    const found = await new window.BarcodeDetector({ formats }).detect(bitmap);
    return found[0]?.rawValue || "";
  } catch (_err) {
    return "";
  }
}

const STYLE = `
  :host { display: block; min-height: 100vh; background: var(--primary-background-color);
    color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
  .toolbar { display: flex; align-items: center; height: var(--header-height, 56px); padding: 0 12px;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, var(--text-primary-color, #fff)); }
  .title { font-size: 20px; margin-left: 8px; }
  .content { max-width: 520px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; }
  label { margin-top: 8px; font-size: 14px; color: var(--secondary-text-color); }
  input { font-size: 18px; padding: 12px; border-radius: 10px; border: 1px solid var(--divider-color);
    background: var(--card-background-color); color: var(--primary-text-color); min-width: 0; }
  .row { display: flex; gap: 8px; align-items: center; }
  .row input { flex: 1; }
  button { font-size: 16px; padding: 12px 16px; border-radius: 10px; border: none; cursor: pointer; }
  button:disabled { opacity: 0.6; }
  .primary { margin-top: 16px; font-size: 20px; padding: 18px; background: var(--primary-color);
    color: var(--text-primary-color, #fff); }
  .secondary { background: var(--secondary-background-color, #e0e0e0); color: var(--primary-text-color);
    border: 1px solid var(--divider-color); white-space: nowrap; }
  .wide { width: 100%; padding: 16px; }
  .segment { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border-radius: 10px; overflow: hidden;
    border: 1px solid var(--divider-color); }
  .segment button { border-radius: 0; background: var(--card-background-color); color: var(--primary-text-color); }
  .segment button.active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .hint { text-align: center; font-size: 13px; color: var(--secondary-text-color); }
  .photo img { width: 96px; height: 96px; object-fit: cover; border-radius: 10px; }
  .msg { margin-top: 12px; padding: 14px; border-radius: 10px; line-height: 1.5;
    background: var(--card-background-color); border-left: 6px solid; }
  .msg.ok { border-color: var(--success-color, #43a047); }
  .msg.err { border-color: var(--error-color, #db4437); }
`;

if (!customElements.get("grocy-ai-panel")) {
  customElements.define("grocy-ai-panel", GrocyAiPanel);
}
