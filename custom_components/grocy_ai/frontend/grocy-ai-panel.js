// Grocy AI sidebar panel: book stock from the phone with the camera.
// Plain web component without build step or external libraries.

const MAX_SIDE = 1600; // px, photos are scaled down before upload
const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];
const SCAN_INTERVAL = 250; // ms between live barcode detections

const TEXTS = {
  en: {
    title: "Grocy AI",
    plus: "Purchased (+)",
    minus: "Used (−)",
    barcode: "Barcode",
    scan: "Camera",
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
    shoot: "Take photo",
    cancel: "Cancel",
    camBarcode: "Hold the barcode in the frame",
    camBbd: "Best-before date sharp and large in the frame",
    noLiveCamera:
      "The camera can only be opened directly when Home Assistant is used via HTTPS. " +
      "Until then pick a photo.",
  },
  de: {
    title: "Grocy AI",
    plus: "Eingekauft (+)",
    minus: "Verbraucht (−)",
    barcode: "Barcode",
    scan: "Kamera",
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
    shoot: "Auslösen",
    cancel: "Abbrechen",
    camBarcode: "Barcode ins Bild halten",
    camBbd: "MHD groß und scharf ins Bild",
    noLiveCamera:
      "Die Kamera lässt sich nur direkt öffnen, wenn Home Assistant über HTTPS " +
      "aufgerufen wird. Bis dahin ein Foto auswählen.",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

// getUserMedia only exists in secure contexts (HTTPS or localhost).
const canUseLiveCamera = () =>
  Boolean(window.isSecureContext && navigator.mediaDevices?.getUserMedia);

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

  disconnectedCallback() {
    this._stopCamera?.();
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
                   : `<button id="bbd-photo" class="secondary wide" ${busy ? "disabled" : ""}>📷 ${t.bbdPhoto}</button>
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
        ${canUseLiveCamera() ? "" : `<div class="hint small">ℹ️ ${t.noLiveCamera}</div>`}
      </div>
      <input id="file" type="file" accept="image/*" capture="environment" hidden>
    `;
    const $ = (id) => this.shadowRoot.getElementById(id);
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    menu.hass = this._hass;
    menu.narrow = this._narrow;

    $("plus").onclick = () => this._setMode("plus");
    $("minus").onclick = () => this._setMode("minus");
    $("barcode").oninput = (ev) => (this._barcode = ev.target.value.trim());
    $("amount").oninput = (ev) => (this._amount = ev.target.value);
    $("scan").onclick = () => this._scanBarcode();
    $("book").onclick = () => this._book();
    if ($("bbd-photo")) $("bbd-photo").onclick = () => this._photographBbd();
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

  // Returns {code} (barcode detected live), {blob} (photo) or null (cancelled).
  async _capture(kind) {
    if (canUseLiveCamera()) {
      try {
        return await this._liveCapture(kind);
      } catch (err) {
        // Permission denied or no camera: fall back to the file picker.
        console.warn("grocy_ai: live camera unavailable", err);
      }
    }
    const file = await this._pickFile();
    return file ? { blob: (await shrink(file)).blob } : null;
  }

  _pickFile() {
    return new Promise((resolve) => {
      const input = this.shadowRoot.getElementById("file");
      input.onchange = () => {
        const file = input.files?.[0] || null;
        input.value = "";
        resolve(file);
      };
      input.click();
    });
  }

  async _liveCapture(kind) {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
      audio: false,
    });
    const t = this._t;
    const overlay = document.createElement("div");
    overlay.className = "camera";
    overlay.innerHTML = `
      <video playsinline muted autoplay></video>
      <div class="frame ${kind}"></div>
      <div class="cam-hint">${kind === "barcode" ? t.camBarcode : t.camBbd}</div>
      <div class="cam-bar">
        <button class="secondary" data-action="cancel">${t.cancel}</button>
        <button class="primary shoot" data-action="shoot">${t.shoot}</button>
      </div>`;
    this.shadowRoot.appendChild(overlay);
    const video = overlay.querySelector("video");
    video.srcObject = stream;
    await video.play().catch(() => {});
    const detector = kind === "barcode" ? await makeDetector() : null;

    return new Promise((resolve) => {
      let done = false;
      let timer;
      const finish = (value) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        stream.getTracks().forEach((track) => track.stop());
        overlay.remove();
        this._stopCamera = null;
        resolve(value);
      };
      this._stopCamera = () => finish(null);
      overlay.querySelector('[data-action="cancel"]').onclick = () => finish(null);
      overlay.querySelector('[data-action="shoot"]').onclick = async () =>
        finish({ blob: await grabFrame(video) });
      if (detector) {
        const scan = async () => {
          if (done) return;
          try {
            const found = await detector.detect(video);
            if (found[0]?.rawValue) {
              finish({ code: found[0].rawValue });
              return;
            }
          } catch (_err) {
            // video not ready yet
          }
          timer = setTimeout(scan, SCAN_INTERVAL);
        };
        scan();
      }
    });
  }

  async _scanBarcode() {
    const shot = await this._capture("barcode");
    if (!shot) return;
    this._message = null;
    if (shot.code) {
      this._barcode = shot.code;
      this._render();
      return;
    }
    this._setBusy(this._t.reading);
    try {
      let code = await detectInImage(shot.blob);
      if (!code) {
        const result = await this._call("read_barcode", { image: await this._upload(shot.blob) });
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

  async _photographBbd() {
    const shot = await this._capture("bbd");
    if (!shot?.blob) return;
    this._clearBbdPhoto(false);
    this._bbdPhoto = { blob: shot.blob, url: URL.createObjectURL(shot.blob) };
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

function toJpeg(source, width, height) {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
}

async function shrink(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  return { blob: await toJpeg(bitmap, bitmap.width, bitmap.height) };
}

function grabFrame(video) {
  return toJpeg(video, video.videoWidth, video.videoHeight);
}

// The browser's own barcode reader (Chrome on Android); null when unavailable.
async function makeDetector() {
  if (!("BarcodeDetector" in window)) return null;
  try {
    const supported = await window.BarcodeDetector.getSupportedFormats();
    const formats = BARCODE_FORMATS.filter((f) => supported.includes(f));
    return formats.length ? new window.BarcodeDetector({ formats }) : null;
  } catch (_err) {
    return null;
  }
}

// Without a local reader the photo goes to AI Task via grocy_ai.read_barcode.
async function detectInImage(blob) {
  const detector = await makeDetector();
  if (!detector) return "";
  try {
    const found = await detector.detect(await createImageBitmap(blob));
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
  .hint.small { margin-top: 16px; text-align: left; }
  .photo img { width: 96px; height: 96px; object-fit: cover; border-radius: 10px; }
  .msg { margin-top: 12px; padding: 14px; border-radius: 10px; line-height: 1.5; overflow-wrap: anywhere;
    background: var(--card-background-color); border-left: 6px solid; }
  .msg.ok { border-color: var(--success-color, #43a047); }
  .msg.err { border-color: var(--error-color, #db4437); }
  .camera { position: fixed; inset: 0; z-index: 10; background: #000; display: flex; flex-direction: column; }
  .camera video { flex: 1; width: 100%; min-height: 0; object-fit: cover; }
  .camera .frame { position: absolute; left: 10%; right: 10%; top: 35%; height: 22%;
    border: 3px solid rgba(255, 255, 255, 0.85); border-radius: 12px; pointer-events: none; }
  .camera .frame.bbd { top: 30%; height: 30%; }
  .cam-hint { position: absolute; top: 16px; left: 0; right: 0; text-align: center; color: #fff;
    font-size: 16px; text-shadow: 0 1px 3px #000; }
  .cam-bar { display: flex; gap: 12px; padding: 16px; padding-bottom: calc(16px + env(safe-area-inset-bottom));
    background: #000; }
  .cam-bar button { flex: 1; margin: 0; }
  .cam-bar .secondary { background: #333; color: #fff; border-color: #555; }
`;

if (!customElements.get("grocy-ai-panel")) {
  customElements.define("grocy-ai-panel", GrocyAiPanel);
}
