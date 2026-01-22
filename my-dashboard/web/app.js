const statusEl = document.getElementById("status");
const applyProgressEl = document.getElementById("applyProgress");
const applyProgressBarEl = document.getElementById("applyProgressBar");
const applyBtn = document.getElementById("apply");
const updateBtn = document.getElementById("updateApp");
const saveConfigBtn = document.getElementById("saveConfig");
const saveAsBtn = document.getElementById("saveAs");
const tilesEl = document.getElementById("tiles");
const safeViewportEl = document.getElementById("safeViewport");
const presetSelect = document.getElementById("presetSelect");
const deletePresetBtn = document.getElementById("deletePreset");
const previewStubInput = document.getElementById("previewStub");
const scheduleInput = document.getElementById("updateInterval");
const borderWidthInput = document.getElementById("borderWidth");
const borderRadiusInput = document.getElementById("borderRadius");
const borderStyleSelect = document.getElementById("borderStyle");
const borderColorSelect = document.getElementById("borderColor");
const borderDitherInput = document.getElementById("borderDither");
const borderDitherColorSelect = document.getElementById("borderDitherColor");
const borderDitherStepInput = document.getElementById("borderDitherStep");
const borderDitherRatioInput = document.getElementById("borderDitherRatio");
const backgroundColorSelect = document.getElementById("backgroundColor");
const backgroundDitherInput = document.getElementById("backgroundDither");
const backgroundDitherColorSelect = document.getElementById("backgroundDitherColor");
const backgroundDitherStepInput = document.getElementById("backgroundDitherStep");
const backgroundDitherRatioInput = document.getElementById("backgroundDitherRatio");
const fontFamilySelect = document.getElementById("fontFamily");
const fontTitleInput = document.getElementById("fontTitle");
const fontSubInput = document.getElementById("fontSub");
const fontBodyInput = document.getElementById("fontBody");
const fontMetaInput = document.getElementById("fontMeta");
const fontTempInput = document.getElementById("fontTemp");
const uploadFontBtn = document.getElementById("uploadFont");
const fontFileInput = document.getElementById("fontFile");
const safeLeftInput = document.getElementById("safeLeft");
const safeTopInput = document.getElementById("safeTop");
const safeRightInput = document.getElementById("safeRight");
const safeBottomInput = document.getElementById("safeBottom");
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");
const borderDitherOptionsEl = document.getElementById("borderDitherOptions");
const backgroundDitherOptionsEl = document.getElementById("backgroundDitherOptions");

const PALETTE_HEX = {
  black: "#000000",
  white: "#ffffff",
  green: "#008000",
  blue: "#0000ff",
  red: "#ff0000",
  yellow: "#ffff00",
  orange: "#ffa500",
};
const layoutPanelEl = document.getElementById("layoutPanel");
const configPanelEl = document.getElementById("configPanel");
const backToLayoutBtn = document.getElementById("backToLayout");
const canvas = document.getElementById("previewCanvas");
const ctx = canvas.getContext("2d", { alpha: false });

let SAFE = { left: 4, top: 4, right: 4, bottom: 4 };
let DEFAULT_W = 800;
let DEFAULT_H = 480;
const ANIM_DURATION = 160;

let activeTileIndex = null;
let viewportSize = { width: 0, height: 0, scale: 1, baseWidth: 0, baseHeight: 0 };
let currentTiles = [];
let currentPluginMeta = null;
let previewImage = null;
let previewReady = false;
let dragSourceIndex = null;
let dragTargetIndex = null;
let isDragging = false;
let dragPointerId = null;
let dragStart = null;
let dragOffset = { x: 0, y: 0 };
let hoverIndex = null;
let isPreviewHover = false;
let presetPreview = null;
let presetPreviewTimer = null;
let tileAnimations = new Map();
let applyStatusTimer = null;
let updateCheckTimer = null;
let ditherPreviewTimer = null;
let availableFonts = [];

const initialSafeWidth = DEFAULT_W;
const initialSafeHeight = DEFAULT_H;
viewportSize = {
  width: initialSafeWidth,
  height: initialSafeHeight,
  scale: 1,
  baseWidth: DEFAULT_W - SAFE.left - SAFE.right,
  baseHeight: DEFAULT_H - SAFE.top - SAFE.bottom,
  offsetX: SAFE.left,
  offsetY: SAFE.top,
};
canvas.width = initialSafeWidth;
canvas.height = initialSafeHeight;
canvas.style.width = `${initialSafeWidth}px`;
canvas.style.height = `${initialSafeHeight}px`;
safeViewportEl.style.width = `${initialSafeWidth}px`;
safeViewportEl.style.height = `${initialSafeHeight}px`;

const setStatus = (msg, ok = true) => {
  statusEl.textContent = msg;
  statusEl.style.color = ok ? "#0a5" : "#c00";
};

const setUploading = (isUploading) => {
  applyBtn.disabled = isUploading;
  appState.uploading = isUploading;
};

const updateDitherVisibility = () => {
  if (borderDitherOptionsEl && borderDitherInput) {
    borderDitherOptionsEl.classList.toggle("hidden", !borderDitherInput.checked);
  }
  if (backgroundDitherOptionsEl && backgroundDitherInput) {
    backgroundDitherOptionsEl.classList.toggle("hidden", !backgroundDitherInput.checked);
  }
};

const scheduleDitherPreview = () => {
  if (ditherPreviewTimer) clearTimeout(ditherPreviewTimer);
  ditherPreviewTimer = setTimeout(() => {
    ditherPreviewTimer = null;
    requestPreview(collectConfig(), "Preview updated", true).catch(() => {});
  }, 250);
};

const applySafeArea = (data) => {
  if (!data || typeof data !== "object") return;
  const next = { ...SAFE };
  if (Number.isFinite(data.left)) next.left = Number(data.left);
  if (Number.isFinite(data.top)) next.top = Number(data.top);
  if (Number.isFinite(data.right)) next.right = Number(data.right);
  if (Number.isFinite(data.bottom)) next.bottom = Number(data.bottom);
  SAFE = next;
  if (Number.isFinite(data.width)) DEFAULT_W = Number(data.width);
  if (Number.isFinite(data.height)) DEFAULT_H = Number(data.height);
};

const toHex = (value, fallback = "#000000") => {
  if (!value) return fallback;
  if (typeof value === "string" && value.startsWith("#") && value.length >= 7) {
    return value.slice(0, 7).toLowerCase();
  }
  const named = PALETTE_HEX[String(value).toLowerCase()];
  return named || fallback;
};

let palettesInitialized = false;
const refreshColorPalettes = () => {
  document.querySelectorAll(".color-palette").forEach((palette) => {
    const targetId = palette.dataset.target;
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    const value = toHex(target.value, "#000000");
    const swatches = [...palette.querySelectorAll(".color-swatch[data-color]")];
    const customBtn = swatches.find((btn) => btn.dataset.color === "custom");
    const paletteColors = swatches
      .map((btn) => btn.dataset.color?.toLowerCase())
      .filter((color) => color && color !== "custom");
    const isPaletteColor = paletteColors.includes(value);
    swatches.forEach((btn) => {
      const color = btn.dataset.color?.toLowerCase();
      btn.classList.toggle("active", color === value);
    });
    if (customBtn) {
      if (isPaletteColor) {
        customBtn.classList.remove("active");
        customBtn.classList.remove("custom-active");
        customBtn.style.removeProperty("--custom-color");
        customBtn.style.background = "";
      } else {
        customBtn.classList.add("active");
        customBtn.classList.add("custom-active");
        customBtn.style.setProperty("--custom-color", value);
        customBtn.style.background = "";
      }
    }
  });
};

const initColorPalettes = () => {
  if (palettesInitialized) {
    refreshColorPalettes();
    return;
  }
  palettesInitialized = true;
  document.querySelectorAll(".color-palette").forEach((palette) => {
    const targetId = palette.dataset.target;
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    const updateActive = () => {
      const value = toHex(target.value, "#000000");
      const swatches = [...palette.querySelectorAll(".color-swatch[data-color]")];
      const customBtn = swatches.find((btn) => btn.dataset.color === "custom");
      const paletteColors = swatches
        .map((btn) => btn.dataset.color?.toLowerCase())
        .filter((color) => color && color !== "custom");
      const isPaletteColor = paletteColors.includes(value);
      swatches.forEach((btn) => {
        const color = btn.dataset.color?.toLowerCase();
        btn.classList.toggle("active", color === value);
      });
      if (customBtn) {
        if (isPaletteColor) {
          customBtn.classList.remove("active");
          customBtn.classList.remove("custom-active");
          customBtn.style.removeProperty("--custom-color");
          customBtn.style.background = "";
        } else {
          customBtn.classList.add("active");
          customBtn.classList.add("custom-active");
          customBtn.style.setProperty("--custom-color", value);
          customBtn.style.background = "";
        }
      }
    };
    palette.addEventListener("click", (event) => {
      const btn = event.target.closest(".color-swatch[data-color]");
      if (!btn || !btn.dataset.color) return;
      if (btn.dataset.color === "custom") return;
      target.value = btn.dataset.color.toLowerCase();
      target.dispatchEvent(new Event("change", { bubbles: true }));
      updateActive();
    });
    target.addEventListener("change", updateActive);
    updateActive();
  });
};

const isPaletteEnum = (def) => {
  if (def.type !== "enum") return false;
  const options = Array.isArray(def.options) ? def.options : [];
  return options.length > 0 && options.every((opt) => Boolean(PALETTE_HEX[String(opt).toLowerCase()]));
};

const buildPaletteControl = (options, currentValue, onSelect) => {
  const palette = document.createElement("div");
  palette.className = "color-palette";
  const normalized = String(currentValue || "").toLowerCase();
  options.forEach((opt) => {
    const name = String(opt).toLowerCase();
    const swatch = document.createElement("button");
    swatch.type = "button";
    swatch.className = "color-swatch";
    swatch.dataset.color = name;
    swatch.style.background = PALETTE_HEX[name];
    swatch.title = opt;
    swatch.setAttribute("aria-label", opt);
    if (name === normalized) swatch.classList.add("active");
    palette.appendChild(swatch);
  });
  palette.addEventListener("click", (event) => {
    const btn = event.target.closest(".color-swatch[data-color]");
    if (!btn || !btn.dataset.color) return;
    const selected = btn.dataset.color.toLowerCase();
    palette.querySelectorAll(".color-swatch[data-color]").forEach((swatch) => {
      swatch.classList.toggle("active", swatch.dataset.color === selected);
    });
    onSelect(selected);
  });
  return palette;
};

const updateSafeAreaFromInputs = (shouldPreview = true) => {
  const left = Number(safeLeftInput.value || 0);
  const top = Number(safeTopInput.value || 0);
  const right = Number(safeRightInput.value || 0);
  const bottom = Number(safeBottomInput.value || 0);
  SAFE = { left, top, right, bottom };
  updateSafeViewport();
  if (shouldPreview) {
    requestPreview(collectConfig(), "Preview updated", true).catch(() => {});
  }
};

const setActiveTab = (tabName) => {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.tab === tabName);
  });
};

const checkForUpdates = async () => {
  if (!updateBtn) return;
  updateBtn.disabled = true;
  updateBtn.classList.add("is-hidden");
  updateBtn.classList.remove("update-available");
  updateBtn.textContent = "Checking...";
  try {
    const data = await fetchJson("/api/update/check");
    if (data.error) {
      updateBtn.textContent = "Update";
      updateBtn.disabled = false;
      updateBtn.classList.add("is-hidden");
      return;
    }
    const available = Boolean(data.behind);
    updateBtn.classList.toggle("update-available", available);
    updateBtn.textContent = available ? "Update available" : "Update";
    updateBtn.disabled = !available;
    updateBtn.classList.toggle("is-hidden", !available);
  } catch (e) {
    updateBtn.textContent = "Update";
    updateBtn.disabled = false;
    updateBtn.classList.add("is-hidden");
  }
};

const refreshFontOptions = (selected) => {
  if (!fontFamilySelect) return;
  fontFamilySelect.innerHTML = "";
  availableFonts.forEach((font) => {
    const opt = document.createElement("option");
    opt.value = font.value;
    const label = String(font.label || font.value || "");
    opt.textContent = label.length > 24 ? `${label.slice(0, 21)}...` : label;
    opt.title = label;
    if (selected && selected === font.value) opt.selected = true;
    fontFamilySelect.appendChild(opt);
  });
};

const loadFonts = async (selected) => {
  const data = await fetchJson("/api/fonts");
  availableFonts = data.fonts || [];
  refreshFontOptions(selected);
};

const loadSafeArea = async () => {
  const data = await fetchJson("/api/safe-area");
  applySafeArea(data);
};

const uploadFont = async (file) => {
  const reader = new FileReader();
  const result = await new Promise((resolve, reject) => {
    reader.onerror = () => reject(new Error("Failed to read font file"));
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
  const base64 = String(result).split(",")[1] || "";
  const res = await fetchJson("/api/fonts", {
    method: "POST",
    body: JSON.stringify({
      name: file.name,
      data: base64,
    }),
  });
  await loadFonts(res.value);
  fontFamilySelect.value = res.value;
  updateResetState();
  setStatus("Font uploaded");
};

const uploadPhoto = async (file) => {
  const reader = new FileReader();
  const result = await new Promise((resolve, reject) => {
    reader.onerror = () => reject(new Error("Failed to read photo file"));
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(file);
  });
  const base64 = String(result).split(",")[1] || "";
  const res = await fetchJson("/api/photos", {
    method: "POST",
    body: JSON.stringify({
      name: file.name,
      data: base64,
    }),
  });
  setStatus("Photo uploaded");
  return res.value;
};

const setProgress = (percent, message = null) => {
  if (message) {
    setStatus(message);
  }
  if (percent == null) {
    applyProgressEl.classList.remove("active");
    applyProgressEl.setAttribute("aria-hidden", "true");
    applyProgressBarEl.style.width = "0%";
    return;
  }
  const bounded = Math.max(0, Math.min(100, percent));
  applyProgressEl.classList.add("active");
  applyProgressEl.setAttribute("aria-hidden", "false");
  applyProgressBarEl.style.width = `${bounded}%`;
};

const fetchJson = async (url, options = {}) => {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

const appState = window.__dashboardApp || { previewRequest: null, initialized: false };
window.__dashboardApp = appState;
const loadPreviewImage = (src) => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image);
  image.onerror = () => reject(new Error("Failed to load preview image"));
  image.src = src;
});

const requestPreview = async (config, successMessage = "Preview updated", showStatus = true) => {
  if (appState.previewRequest) return appState.previewRequest;
  if (showStatus) {
    setStatus("Generating preview...");
  }
  const payload = previewStubInput && previewStubInput.checked
    ? { ...config, preview_stub: true }
    : config;
  appState.previewRequest = (async () => {
    try {
      const res = await fetchJson("/api/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const src = res.image_data || `${res.image}?ts=${Date.now()}`;
      previewImage = await loadPreviewImage(src);
      previewReady = true;
      updateSafeViewport();
      if (showStatus && successMessage) {
        setStatus(successMessage);
      }
      return res;
    } catch (err) {
      setStatus(err.message, false);
      throw err;
    } finally {
      appState.previewRequest = null;
    }
  })();
  return appState.previewRequest;
};

const encodeConfig = (config) => {
  const json = JSON.stringify(config);
  const encoded = btoa(unescape(encodeURIComponent(json)));
  return encoded.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
};

const applyWithProgress = async (config) => {
  if (typeof EventSource === "undefined") {
    await fetchJson("/api/apply", {
      method: "POST",
      body: JSON.stringify(config),
    });
    await refreshApplyStatus();
    return;
  }

  return new Promise((resolve, reject) => {
    const payload = encodeConfig(config);
    const source = new EventSource(`/api/apply/stream?config=${encodeURIComponent(payload)}`);
    let finished = false;

    const finish = (ok, message) => {
      if (finished) return;
      finished = true;
      source.close();
      if (ok) {
        setProgress(100, message || "Upload complete");
        setTimeout(() => setProgress(null), 1200);
        resolve();
      } else {
        setProgress(null);
        setStatus(message || "Upload failed", false);
        reject(new Error(message || "Upload failed"));
      }
    };

    source.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgress(data.percent ?? 0, data.message || "Uploading...");
      } catch (err) {
        setProgress(10, "Uploading...");
      }
    });

    source.addEventListener("done", (event) => {
      let message = "Uploaded to device";
      try {
        const data = JSON.parse(event.data);
        message = data.message || message;
      } catch (err) {
        // ignore
      }
      finish(true, message);
    });

    source.addEventListener("failed", (event) => {
      let message = "Upload failed";
      try {
        const data = JSON.parse(event.data);
        message = data.message || message;
      } catch (err) {
        // ignore
      }
      finish(false, message);
    });

    source.addEventListener("error", () => {
      finish(false, "Upload failed");
    });
  });
};

const updateApplyStatus = (status) => {
  if (status.running) {
    setUploading(true);
    setProgress(status.percent ?? 20, status.message || "Uploading...");
    if (!applyStatusTimer) {
      applyStatusTimer = setInterval(refreshApplyStatus, 2000);
    }
    return;
  }

  if (applyStatusTimer) {
    clearInterval(applyStatusTimer);
    applyStatusTimer = null;
  }
  if (appState.uploading) {
    if (status.error) {
      setStatus(status.error, false);
      setProgress(null);
    } else {
      setProgress(100, "Upload complete");
      setTimeout(() => setProgress(null), 1200);
    }
  } else {
    setProgress(null);
  }
  setUploading(false);
};

const refreshApplyStatus = async () => {
  try {
    const status = await fetchJson("/api/apply/status");
    updateApplyStatus(status);
  } catch (err) {
    // ignore
  }
};

const assignPreviewSlices = (tiles, layoutOverride = null) => {
  const cols = layoutOverride?.cols ?? currentLayout.cols;
  const rows = layoutOverride?.rows ?? currentLayout.rows;
  const gutterBase = parseInt(document.getElementById("gutter").value, 10) || 0;
  const rects = computeTileRects(tiles, cols, rows, gutterBase);
  tiles.forEach((tile, idx) => {
    const rect = rects[idx];
    if (!rect) return;
    tile.preview = {
      sx: rect.left,
      sy: rect.top,
      sw: rect.w,
      sh: rect.h,
    };
  });
};

const computeTileRects = (tiles, cols, rows, gutterBase) => {
  const baseWidth = viewportSize.baseWidth;
  const baseHeight = viewportSize.baseHeight;
  const offsetX = viewportSize.offsetX || 0;
  const offsetY = viewportSize.offsetY || 0;
  const colWBase = Math.floor((baseWidth - gutterBase * (cols - 1)) / cols);
  const rowHBase = Math.floor((baseHeight - gutterBase * (rows - 1)) / rows);
  return tiles.map((tile) => {
    const left = offsetX + tile.col * (colWBase + gutterBase);
    const top = offsetY + tile.row * (rowHBase + gutterBase);
    const w = colWBase * tile.colspan + gutterBase * (tile.colspan - 1);
    const h = rowHBase * tile.rowspan + gutterBase * (tile.rowspan - 1);
    return { left, top, w, h };
  });
};

const getCanvasPoint = (event) => {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY,
  };
};

const findTileIndex = (point) => {
  const gutter = parseInt(document.getElementById("gutter").value, 10) || 0;
  const rects = computeTileRects(currentTiles, currentLayout.cols, currentLayout.rows, gutter);
  for (let i = 0; i < rects.length; i += 1) {
    const rect = rects[i];
    if (!rect) continue;
    if (
      point.x >= rect.left &&
      point.x <= rect.left + rect.w &&
      point.y >= rect.top &&
      point.y <= rect.top + rect.h
    ) {
      return i;
    }
  }
  return null;
};

const getBorderConfig = () => ({
  width: borderWidthInput.value === "" ? 0 : Number(borderWidthInput.value),
  radius: borderRadiusInput.value === "" ? 0 : Number(borderRadiusInput.value),
  style: borderStyleSelect.value,
  color: borderColorSelect.value,
});

const getPreviewBaseSize = () => {
  const w = previewImage ? previewImage.width : DEFAULT_W;
  const h = previewImage ? previewImage.height : DEFAULT_H;
  return {
    width: w,
    height: h,
    safeWidth: w - SAFE.left - SAFE.right,
    safeHeight: h - SAFE.top - SAFE.bottom,
  };
};

const startTileAnimations = (fromRects, toRects, indices) => {
  const start = performance.now();
  indices.forEach((idx) => {
    const from = fromRects[idx];
    const to = toRects[idx];
    if (!from || !to) return;
    tileAnimations.set(idx, {
      start,
      duration: ANIM_DURATION,
      from,
      to,
    });
  });
};

const getAnimatedRect = (idx, baseRect, now) => {
  const anim = tileAnimations.get(idx);
  if (!anim) return baseRect;
  const progress = Math.min(1, (now - anim.start) / anim.duration);
  const lerp = (a, b) => a + (b - a) * progress;
  const rect = {
    left: lerp(anim.from.left, anim.to.left),
    top: lerp(anim.from.top, anim.to.top),
    w: lerp(anim.from.w, anim.to.w),
    h: lerp(anim.from.h, anim.to.h),
  };
  if (progress >= 1) {
    tileAnimations.delete(idx);
  }
  return rect;
};

let rafId = null;
const drawLoop = (time) => {
  drawCanvas(time);
  rafId = requestAnimationFrame(drawLoop);
};

const drawPlaceholderRect = (rect) => {
  ctx.fillStyle = "#fff";
  ctx.fillRect(rect.left, rect.top, rect.w, rect.h);
  ctx.strokeStyle = "rgba(31, 93, 122, 0.25)";
  ctx.strokeRect(rect.left + 0.5, rect.top + 0.5, rect.w - 1, rect.h - 1);
};

const drawCanvas = (now) => {
  if (!canvas.width || !canvas.height) return;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const gutter = parseInt(document.getElementById("gutter").value, 10) || 0;
  const rects = computeTileRects(currentTiles, currentLayout.cols, currentLayout.rows, gutter);

  if (previewReady && previewImage) {
    if (isDragging) {
      currentTiles.forEach((tile, idx) => {
        const baseRect = rects[idx];
        if (!baseRect) return;
        let rect = getAnimatedRect(idx, baseRect, now);
        if (idx === dragSourceIndex) {
          rect = { ...rect, left: rect.left + dragOffset.x, top: rect.top + dragOffset.y };
        }
        const preview = tile.preview;
        if (preview && previewImage) {
          const srcW = Math.min(previewImage.width - preview.sx, preview.sw + 1);
          const srcH = Math.min(previewImage.height - preview.sy, preview.sh + 1);
          const dstW = rect.w + 1;
          const dstH = rect.h + 1;
          ctx.drawImage(
            previewImage,
            preview.sx,
            preview.sy,
            srcW,
            srcH,
            rect.left,
            rect.top,
            dstW,
            dstH
          );
        } else {
          drawPlaceholderRect(rect);
        }
      });
    } else {
      ctx.drawImage(previewImage, 0, 0, previewImage.width, previewImage.height, 0, 0, canvas.width, canvas.height);
    }
  } else {
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#6d675f";
    ctx.font = "14px \"Space Grotesk\", sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Loading preview…", canvas.width / 2, canvas.height / 2);
  }

  const drawOutline = (rect, opts = {}) => {
    const {
      stroke = "rgba(31, 93, 122, 0.8)",
      width = 2,
      dash = null,
      fill = null,
    } = opts;
    ctx.save();
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fillRect(rect.left, rect.top, rect.w, rect.h);
    }
    ctx.lineWidth = width;
    ctx.strokeStyle = stroke;
    if (dash) ctx.setLineDash(dash);
    ctx.strokeRect(rect.left + 1, rect.top + 1, rect.w - 2, rect.h - 2);
    ctx.restore();
  };

  if (presetPreview) {
    const presetRects = computeTileRects(
      presetPreview.tiles,
      presetPreview.layout.cols,
      presetPreview.layout.rows,
      gutter
    );
    presetRects.forEach((rect) => {
      drawOutline(rect, {
        stroke: "rgba(255, 255, 255, 0.95)",
        width: 3,
        fill: "rgba(0, 0, 0, 0.25)",
      });
    });
  }

  if (isDragging && dragTargetIndex !== null && rects[dragTargetIndex]) {
    drawOutline(rects[dragTargetIndex], {
      stroke: "rgba(31, 93, 122, 1)",
      width: 2,
      dash: [6, 4],
      fill: "rgba(31, 93, 122, 0.15)",
    });
  }

  if (isPreviewHover && hoverIndex !== null && rects[hoverIndex]) {
    drawOutline(rects[hoverIndex], {
      stroke: "rgba(31, 93, 122, 0.8)",
      width: 2,
      fill: "rgba(31, 93, 122, 0.18)",
    });
  } else if (activeTileIndex !== null && rects[activeTileIndex]) {
    drawOutline(rects[activeTileIndex], {
      stroke: "rgba(31, 93, 122, 0.8)",
      width: 2,
      fill: "rgba(31, 93, 122, 0.18)",
    });
  }
};

const swapTilePositions = (fromIndex, toIndex) => {
  if (fromIndex === toIndex) return;
  const gutter = parseInt(document.getElementById("gutter").value, 10) || 0;
  const fromRects = computeTileRects(currentTiles, currentLayout.cols, currentLayout.rows, gutter);
  const next = currentTiles.map((tile) => ({ ...tile }));
  const from = next[fromIndex];
  const to = next[toIndex];
  if (!from || !to) return;
  const fromPos = { col: from.col, row: from.row, colspan: from.colspan, rowspan: from.rowspan };
  from.col = to.col;
  from.row = to.row;
  from.colspan = to.colspan;
  from.rowspan = to.rowspan;
  to.col = fromPos.col;
  to.row = fromPos.row;
  to.colspan = fromPos.colspan;
  to.rowspan = fromPos.rowspan;
  currentTiles = next;
  const toRects = computeTileRects(currentTiles, currentLayout.cols, currentLayout.rows, gutter);
  startTileAnimations(fromRects, toRects, [fromIndex, toIndex]);
  renderTileConfig(currentTiles, currentPluginMeta);
  updateResetState();
};

const updatePanelVisibility = () => {
  const hasSelection = activeTileIndex != null;
  layoutPanelEl.classList.toggle("hidden", hasSelection);
  configPanelEl.classList.toggle("hidden", !hasSelection);
};

const renderTileConfig = (tiles, pluginMeta) => {
  tilesEl.innerHTML = "";
  updatePanelVisibility();
  if (activeTileIndex == null || !tiles[activeTileIndex]) {
    const empty = document.createElement("div");
    empty.className = "tile-empty";
    empty.textContent = "Select a tile in the preview to edit its settings.";
    tilesEl.appendChild(empty);
    return;
  }
  const tile = tiles[activeTileIndex];
  const idx = activeTileIndex;
  const wrap = document.createElement("div");
  wrap.className = "tile open";

  const options = document.createElement("div");
  options.className = "tile-options";

  const pluginRow = document.createElement("div");
  pluginRow.className = "config-grid plugin-row";
  const pluginLabel = document.createElement("label");
  pluginLabel.textContent = "Plugin";
  pluginRow.appendChild(pluginLabel);

  const select = document.createElement("select");
  const isFullscreen = currentLayout.cols === 1 &&
    currentLayout.rows === 1 &&
    tile.col === 0 &&
    tile.row === 0 &&
    tile.colspan === 1 &&
    tile.rowspan === 1;
  Object.keys(pluginMeta.defaults).forEach((name) => {
    if (name === "calendar" && !isFullscreen && tile.plugin !== "calendar") {
      return;
    }
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = pluginMeta.names?.[name] || name;
    if (tile.plugin === name) opt.selected = true;
    if (name === "calendar" && !isFullscreen) opt.disabled = true;
    select.appendChild(opt);
  });
  pluginRow.appendChild(select);
  options.appendChild(pluginRow);

  const cfgWrap = document.createElement("div");
  cfgWrap.className = "config-fields config-grid";
  options.appendChild(cfgWrap);

  const schema = pluginMeta.schemas[tile.plugin] || {};
  const defaults = pluginMeta.defaults[tile.plugin] || {};
  const current = tile.config || defaults;

  const addField = (key, def) => {
    const label = document.createElement("label");
    label.textContent = def.label || key;

    if (def.type === "enum") {
      cfgWrap.appendChild(label);
      if (isPaletteEnum(def)) {
        const input = document.createElement("input");
        input.type = "text";
        input.className = "color-picker-hidden";
        input.dataset.key = key;
        input.value = current[key] ?? def.options[0];
        const wrap = document.createElement("div");
        wrap.className = "color-input";
        wrap.appendChild(input);
        wrap.appendChild(buildPaletteControl(def.options, input.value, (value) => {
          input.value = value;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }));
        cfgWrap.appendChild(wrap);
      } else {
        const sel = document.createElement("select");
        sel.dataset.key = key;
        (def.options || []).forEach((optVal) => {
          const opt = document.createElement("option");
          opt.value = optVal;
          opt.textContent = optVal;
          if (current[key] === optVal) opt.selected = true;
          sel.appendChild(opt);
        });
        cfgWrap.appendChild(sel);
      }
      return;
    }

    if (def.type === "list") {
      cfgWrap.appendChild(label);
      if (def.help) {
        const help = document.createElement("div");
        help.className = "field-help";
        help.textContent = def.help;
        cfgWrap.appendChild(help);
      }
      const list = Array.isArray(current[key]) ? current[key] : [];
      const listWrap = document.createElement("div");
      listWrap.className = "array-list";
      listWrap.dataset.key = key;
      listWrap.dataset.itemType = def.itemType || "string";
      const itemFields = def.itemFields || null;

      const buildObjectRow = (value) => {
        const row = document.createElement("div");
        row.className = "array-item object-item";
        const fieldByKey = {};
        (itemFields || []).forEach((field) => {
          const fieldWrap = document.createElement("div");
          fieldWrap.className = "field";
          if (field.key === "name") {
            fieldWrap.classList.add("full");
          }
          const fieldLabel = document.createElement("label");
          fieldLabel.textContent = field.label || field.key;
          fieldWrap.appendChild(fieldLabel);
          let input;
          if (field.type === "enum" && isPaletteEnum(field)) {
            input = document.createElement("input");
            input.type = "text";
            input.className = "color-picker-hidden";
            input.dataset.field = field.key;
            input.value = value?.[field.key] ?? field.options?.[0] ?? "";
            const paletteWrap = document.createElement("div");
            paletteWrap.className = "color-input";
            paletteWrap.appendChild(input);
            paletteWrap.appendChild(buildPaletteControl(field.options || [], input.value, (selected) => {
              input.value = selected;
              input.dispatchEvent(new Event("change", { bubbles: true }));
            }));
            fieldWrap.appendChild(paletteWrap);
          } else if (field.type === "enum") {
            input = document.createElement("select");
            (field.options || []).forEach((optVal) => {
              const opt = document.createElement("option");
              opt.value = optVal;
              opt.textContent = optVal;
              input.appendChild(opt);
            });
            input.dataset.field = field.key;
            if (field.placeholder) input.placeholder = field.placeholder;
            input.value = value?.[field.key] ?? "";
            fieldWrap.appendChild(input);
          } else {
            input = document.createElement("input");
            input.type = "text";
            input.dataset.field = field.key;
            if (field.placeholder) input.placeholder = field.placeholder;
            input.value = value?.[field.key] ?? "";
            fieldWrap.appendChild(input);
          }
          row.appendChild(fieldWrap);
          fieldByKey[field.key] = fieldWrap;
        });
        const updateVisibility = () => {
          const typeValue = row.querySelector('[data-field="type"]')?.value || "";
          const typeLower = typeValue.toLowerCase();
          Object.entries(fieldByKey).forEach(([key, wrap]) => {
            if (key === "type" || key === "name" || key === "color") {
              wrap.classList.remove("hidden");
              return;
            }
            wrap.classList.add("hidden");
            if (typeLower === "ical_url" && key === "url") wrap.classList.remove("hidden");
            if (typeLower === "local" && key === "path") wrap.classList.remove("hidden");
            if (typeLower === "google" && (key === "calendar_id" || key === "api_key")) {
              wrap.classList.remove("hidden");
            }
          });
        };
        const typeSelect = row.querySelector('[data-field="type"]');
        if (typeSelect) {
          typeSelect.addEventListener("change", () => {
            updateVisibility();
            updateResetState();
          });
        }
        updateVisibility();
        const del = document.createElement("button");
        del.type = "button";
        del.textContent = "Remove";
        del.addEventListener("click", () => {
          row.remove();
          updateResetState();
        });
        row.appendChild(del);
        return row;
      };

      list.forEach((value) => {
        if (itemFields) {
          listWrap.appendChild(buildObjectRow(value));
          return;
        }
        const row = document.createElement("div");
        row.className = "array-item";
        const input = document.createElement("input");
        input.type = "text";
        if (def.itemType === "number") {
          input.type = "number";
          if (def.min !== undefined) input.min = def.min;
          if (def.max !== undefined) input.max = def.max;
          if (def.step !== undefined) input.step = def.step;
        }
        input.value = value ?? "";
        const del = document.createElement("button");
        del.type = "button";
        del.textContent = "Remove";
        del.addEventListener("click", () => {
          row.remove();
          updateResetState();
        });
        row.appendChild(input);
        row.appendChild(del);
        listWrap.appendChild(row);
      });
      const addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.textContent = "Add";
      addBtn.addEventListener("click", () => {
        if (itemFields) {
          listWrap.appendChild(buildObjectRow({}));
          updateResetState();
          return;
        }
        const row = document.createElement("div");
        row.className = "array-item";
        const input = document.createElement("input");
        input.type = def.itemType === "number" ? "number" : "text";
        if (def.itemType === "number") {
          if (def.min !== undefined) input.min = def.min;
          if (def.max !== undefined) input.max = def.max;
          if (def.step !== undefined) input.step = def.step;
        }
        const del = document.createElement("button");
        del.type = "button";
        del.textContent = "Remove";
        del.addEventListener("click", () => {
          row.remove();
          updateResetState();
        });
        row.appendChild(input);
        row.appendChild(del);
        listWrap.appendChild(row);
        updateResetState();
      });
      const actions = document.createElement("div");
      actions.className = "array-actions";
      actions.appendChild(addBtn);
      cfgWrap.appendChild(listWrap);
      cfgWrap.appendChild(actions);
      return;
    }

    if (def.type === "file") {
      cfgWrap.appendChild(label);
      const row = document.createElement("div");
      row.className = "font-row";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Upload";
      const input = document.createElement("input");
      input.type = "file";
      input.className = "file-hidden";
      input.accept = def.accept || ".png,.jpg,.jpeg,.bmp";
      button.addEventListener("click", () => input.click());
      input.addEventListener("change", async () => {
        const file = input.files && input.files[0];
        if (!file) return;
        try {
          const value = await uploadPhoto(file);
          const target = def.target || "path";
          const targetInput = cfgWrap.querySelector(`[data-key="${target}"]`);
          if (targetInput) {
            targetInput.value = value;
          }
          updateResetState();
        } catch (e) {
          setStatus(e.message, false);
        } finally {
          input.value = "";
        }
      });
      row.appendChild(button);
      row.appendChild(input);
      cfgWrap.appendChild(row);
      return;
    }

    const input = document.createElement("input");
    input.dataset.key = key;
    if (def.type === "number") {
      cfgWrap.appendChild(label);
      input.type = "number";
      if (def.min !== undefined) input.min = def.min;
      if (def.max !== undefined) input.max = def.max;
      if (def.step !== undefined) input.step = def.step;
      input.value = current[key] ?? "";
    } else if (def.type === "boolean") {
      input.type = "checkbox";
      input.checked = Boolean(current[key]);
      const row = document.createElement("div");
      row.className = "checkbox-row";
      const fieldId = `cfg-${idx}-${key}`;
      input.id = fieldId;
      label.setAttribute("for", fieldId);
      row.appendChild(label);
      row.appendChild(input);
      cfgWrap.appendChild(row);
      return;
    } else {
      cfgWrap.appendChild(label);
      input.type = "text";
      input.value = current[key] ?? "";
    }
    cfgWrap.appendChild(input);
  };

  Object.entries(schema).forEach(([key, def]) => addField(key, def));

  wrap.appendChild(options);
  wrap.dataset.index = idx;
  wrap.dataset.pluginSelect = "";
  wrap.dataset.configInput = "";
  select.className = "plugin-select";
  cfgWrap.classList.add("config-input");

  select.addEventListener("change", () => {
    const plugin = select.value;
    const defaultsForPlugin = pluginMeta.defaults[plugin] || {};
    currentTiles[idx] = { ...currentTiles[idx], plugin, config: { ...defaultsForPlugin } };
    renderTileConfig(currentTiles, pluginMeta);
    updateResetState();
  });

  tilesEl.appendChild(wrap);
};

const renderTiles = (tiles, pluginMeta) => {
  currentPluginMeta = pluginMeta;
  currentTiles = tiles.map((tile) => ({ ...tile }));
  renderTileConfig(currentTiles, pluginMeta);
};

const fetchPresets = async () => {
  const data = await fetchJson("/api/presets");
  return data;
};

const refreshPresetSelect = (presets, selectedName = "") => {
  presetSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Presets";
  presetSelect.appendChild(placeholder);
  const names = Object.keys(presets).sort();
  names.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    if (name === selectedName) opt.selected = true;
    presetSelect.appendChild(opt);
  });
  deletePresetBtn.disabled = !presetSelect.value || names.length <= 1;
};

const findMatchingPreset = (presets, config) => {
  const target = normalizeConfig(config);
  for (const [name, preset] of Object.entries(presets)) {
    if (normalizeConfig(preset) === target) return name;
  }
  return "";
};

const applyConfigToUI = async (config, options = {}) => {
  const pluginMeta = currentPluginMeta || await fetchJson("/api/plugins");
  currentLayout = { cols: config.layout.cols, rows: config.layout.rows };
  document.getElementById("gutter").value = config.layout.gutter;
  borderWidthInput.value = config.layout.border?.width ?? 1;
  borderRadiusInput.value = config.layout.border?.radius ?? 0;
  borderStyleSelect.value = config.layout.border?.style ?? "solid";
  borderColorSelect.value = toHex(config.layout.border?.color, "#000000");
  if (borderDitherInput) borderDitherInput.checked = Boolean(config.layout.border?.dither);
  if (borderDitherColorSelect) borderDitherColorSelect.value = toHex(config.layout.border?.dither_color, "#ffffff");
  if (borderDitherStepInput) borderDitherStepInput.value = config.layout.border?.dither_step ?? 2;
  if (borderDitherRatioInput) borderDitherRatioInput.value = config.layout.border?.dither_ratio ?? 0.5;
  backgroundColorSelect.value = toHex(config.layout.background?.color, "#ffffff");
  if (backgroundDitherInput) backgroundDitherInput.checked = Boolean(config.layout.background?.dither);
  if (backgroundDitherColorSelect) backgroundDitherColorSelect.value = toHex(config.layout.background?.dither_color, "#0000ff");
  if (backgroundDitherStepInput) backgroundDitherStepInput.value = config.layout.background?.dither_step ?? 2;
  if (backgroundDitherRatioInput) backgroundDitherRatioInput.value = config.layout.background?.dither_ratio ?? 0.5;
  const fonts = config.fonts || {};
  const desiredFont = fonts.family ?? "monogram-extended";
  if (availableFonts.length === 0) {
    await loadFonts(desiredFont);
  } else if (![...fontFamilySelect.options].some((opt) => opt.value === desiredFont)) {
    await loadFonts(desiredFont);
  } else {
    fontFamilySelect.value = desiredFont;
  }
  fontTitleInput.value = fonts.title ?? 32;
  fontSubInput.value = fonts.sub ?? 32;
  fontBodyInput.value = fonts.body ?? 16;
  fontMetaInput.value = fonts.meta ?? 16;
  fontTempInput.value = fonts.temp ?? 64;
  const safe = config.safe_area || {};
  safeLeftInput.value = safe.left ?? SAFE.left;
  safeTopInput.value = safe.top ?? SAFE.top;
  safeRightInput.value = safe.right ?? SAFE.right;
  safeBottomInput.value = safe.bottom ?? SAFE.bottom;
  updateSafeAreaFromInputs(false);
  updateDitherVisibility();
  refreshColorPalettes();
  if (config.update_interval_minutes != null) {
    scheduleInput.value = String(config.update_interval_minutes);
  } else {
    scheduleInput.value = parseScheduleMinutes(config.update_schedule);
  }
  renderTiles(config.layout.tiles, pluginMeta);
  updateResetState();
  updateResetState();
  currentConfig = config;
  updateResetState();
  if (presetSelect && !options.skipPresetRefresh) {
    const data = await fetchPresets();
    const presets = data.presets || {};
    const match = options.selectedPreset || data.active || findMatchingPreset(presets, config);
    refreshPresetSelect(presets, match);
  }
};

const parseScheduleMinutes = (schedule) => {
  if (!schedule) return "";
  const parts = schedule.trim().split(/\s+/);
  if (parts.length === 5 && parts[0].startsWith("*/")) {
    const minutes = Number(parts[0].slice(2));
    return Number.isFinite(minutes) ? String(minutes) : "";
  }
  if (schedule.trim() === "* * * * *") return "1";
  return "";
};

const readSelectedTileConfig = () => {
  const config = {};
  const wrap = tilesEl.querySelector(".config-input");
  if (!wrap) return config;
  wrap.querySelectorAll("[data-key]").forEach((el) => {
    const key = el.dataset.key;
    if (el.classList.contains("array-list")) {
      const items = [];
      if (el.dataset.itemType === "object") {
        el.querySelectorAll(".array-item").forEach((row) => {
          const obj = {};
          row.querySelectorAll("[data-field]").forEach((input) => {
            const fieldKey = input.dataset.field;
            if (!fieldKey) return;
            if (input.value.trim() !== "") obj[fieldKey] = input.value.trim();
          });
          if (Object.keys(obj).length > 0) items.push(obj);
        });
        config[key] = items;
        return;
      }
      el.querySelectorAll(".array-item input").forEach((input) => {
        if (input.type === "number") {
          if (input.value !== "") items.push(Number(input.value));
        } else if (input.value.trim() !== "") {
          items.push(input.value.trim());
        }
      });
      config[key] = items;
    } else if (el.type === "checkbox") {
      config[key] = el.checked;
    } else if (el.type === "number") {
      config[key] = el.value === "" ? null : Number(el.value);
    } else {
      config[key] = el.value;
    }
  });
  return config;
};

const collectConfig = () => {
  const tiles = [];
  const selectedPlugin = tilesEl.querySelector(".plugin-select")?.value;
  const borderCurrent = currentConfig?.layout?.border || {};
  const backgroundCurrent = currentConfig?.layout?.background || {};
  currentTiles.forEach((tile, idx) => {
    const existing = (currentConfig?.layout?.tiles || [])[idx] || {};
    const layoutFallback = currentTiles[idx] || {};
    const config = idx === activeTileIndex ? readSelectedTileConfig() : (tile.config || {});
    const plugin = idx === activeTileIndex && selectedPlugin ? selectedPlugin : tile.plugin;
    tiles.push({
      plugin,
      col: layoutFallback.col ?? existing.col,
      row: layoutFallback.row ?? existing.row,
      colspan: layoutFallback.colspan ?? existing.colspan,
      rowspan: layoutFallback.rowspan ?? existing.rowspan,
      config,
    });
  });
  return {
    version: currentConfig?.version ?? CONFIG_VERSION,
    active_preset: currentConfig?.active_preset ?? null,
    inky: currentConfig?.inky ?? null,
    update_interval_minutes: scheduleInput.value === "" ? null : Number(scheduleInput.value),
    fonts: {
      family: fontFamilySelect.value,
      title: Number(fontTitleInput.value),
      sub: Number(fontSubInput.value),
      body: Number(fontBodyInput.value),
      meta: Number(fontMetaInput.value),
      temp: Number(fontTempInput.value),
    },
    safe_area: {
      left: Number(safeLeftInput.value || 0),
      top: Number(safeTopInput.value || 0),
      right: Number(safeRightInput.value || 0),
      bottom: Number(safeBottomInput.value || 0),
    },
    layout: {
      cols: currentLayout.cols,
      rows: currentLayout.rows,
      gutter: parseInt(document.getElementById("gutter").value, 10),
      border: {
        width: borderWidthInput.value === "" ? 0 : Number(borderWidthInput.value),
        radius: borderRadiusInput.value === "" ? 0 : Number(borderRadiusInput.value),
        style: borderStyleSelect.value,
        color: borderColorSelect.value,
        dither: borderDitherInput ? borderDitherInput.checked : (borderCurrent.dither ?? false),
        dither_color: borderDitherColorSelect ? borderDitherColorSelect.value : (borderCurrent.dither_color ?? "white"),
        dither_step: borderDitherStepInput && borderDitherStepInput.value !== ""
          ? Number(borderDitherStepInput.value)
          : (borderCurrent.dither_step ?? 2),
        dither_ratio: borderDitherRatioInput && borderDitherRatioInput.value !== ""
          ? Number(borderDitherRatioInput.value)
          : (borderCurrent.dither_ratio ?? 0.5),
      },
      background: {
        color: backgroundColorSelect.value,
        dither: backgroundDitherInput ? backgroundDitherInput.checked : (backgroundCurrent.dither ?? false),
        dither_color: backgroundDitherColorSelect ? backgroundDitherColorSelect.value : (backgroundCurrent.dither_color ?? "white"),
        dither_step: backgroundDitherStepInput && backgroundDitherStepInput.value !== ""
          ? Number(backgroundDitherStepInput.value)
          : (backgroundCurrent.dither_step ?? 2),
        dither_ratio: backgroundDitherRatioInput && backgroundDitherRatioInput.value !== ""
          ? Number(backgroundDitherRatioInput.value)
          : (backgroundCurrent.dither_ratio ?? 0.5),
      },
      tiles,
    },
  };
};

const PRESETS = {
  full: { cols: 1, rows: 1, tiles: [{ col: 0, row: 0, colspan: 1, rowspan: 1 }] },
  halves: { cols: 2, rows: 1, tiles: [{ col: 0, row: 0, colspan: 1, rowspan: 1 }, { col: 1, row: 0, colspan: 1, rowspan: 1 }] },
  "left-full-right-halves": {
    cols: 2,
    rows: 2,
    tiles: [
      { col: 0, row: 0, colspan: 1, rowspan: 2 },
      { col: 1, row: 0, colspan: 1, rowspan: 1 },
      { col: 1, row: 1, colspan: 1, rowspan: 1 },
    ],
  },
  "left-halves-right-full": {
    cols: 2,
    rows: 2,
    tiles: [
      { col: 0, row: 0, colspan: 1, rowspan: 1 },
      { col: 0, row: 1, colspan: 1, rowspan: 1 },
      { col: 1, row: 0, colspan: 1, rowspan: 2 },
    ],
  },
  quarters: {
    cols: 2,
    rows: 2,
    tiles: [
      { col: 0, row: 0, colspan: 1, rowspan: 1 },
      { col: 1, row: 0, colspan: 1, rowspan: 1 },
      { col: 0, row: 1, colspan: 1, rowspan: 1 },
      { col: 1, row: 1, colspan: 1, rowspan: 1 },
    ],
  },
};

let currentLayout = { cols: 2, rows: 2 };
let currentConfig = null;
const CONFIG_VERSION = 1;

const stableStringify = (value) => {
  const normalize = (val) => {
    if (Array.isArray(val)) {
      return val.map((item) => normalize(item));
    }
    if (val && typeof val === "object") {
      const out = {};
      Object.keys(val).sort().forEach((key) => {
        const child = val[key];
        if (child === undefined) return;
        out[key] = normalize(child);
      });
      return out;
    }
    return val;
  };
  return JSON.stringify(normalize(value));
};

const normalizeConfig = (cfg) => {
  const clean = JSON.parse(JSON.stringify(cfg || {}));
  delete clean.update_schedule;
  if (clean.layout) {
    const border = clean.layout.border || {};
    border.color = toHex(border.color, "#000000");
    border.dither_color = toHex(border.dither_color, "#ffffff");
    clean.layout.border = border;
    const background = clean.layout.background || {};
    background.color = toHex(background.color, "#ffffff");
    background.dither_color = toHex(background.dither_color, "#ffffff");
    clean.layout.background = background;
  }
  if (clean.layout && Array.isArray(clean.layout.tiles)) {
    const defaults = currentPluginMeta?.defaults || {};
    clean.layout.tiles = clean.layout.tiles.map((tile) => {
      if (!tile || !tile.plugin) return tile;
      const base = defaults[tile.plugin] || {};
      return { ...tile, config: { ...base, ...(tile.config || {}) } };
    });
  }
  return stableStringify(clean);
};

const commitActiveTileConfig = () => {
  if (activeTileIndex === null) return;
  if (!currentTiles[activeTileIndex]) return;
  currentTiles[activeTileIndex] = {
    ...currentTiles[activeTileIndex],
    config: readSelectedTileConfig(),
  };
};

const updateResetState = () => {
  if (!currentConfig) return;
  let dirty = false;
  try {
    const nowCfg = collectConfig();
    dirty = normalizeConfig(nowCfg) !== normalizeConfig(currentConfig);
  } catch (e) {
    dirty = true;
  }
  saveConfigBtn.disabled = !dirty;
};

const applyPreset = (presetName, pluginMeta) => {
  const preset = PRESETS[presetName];
  if (!preset) return;
  presetPreview = null;
  const gutter = parseInt(document.getElementById("gutter").value, 10) || 0;
  const fromRects = computeTileRects(currentTiles, currentLayout.cols, currentLayout.rows, gutter);
  currentLayout = { cols: preset.cols, rows: preset.rows };
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.preset === presetName);
  });
  const tiles = preset.tiles.map((slot, i) => {
    const fallback = (currentConfig?.layout?.tiles || [])[i] || {};
    return {
      plugin: fallback.plugin || Object.keys(pluginMeta.defaults)[0],
      config: fallback.config || pluginMeta.defaults[fallback.plugin] || {},
      col: slot.col,
      row: slot.row,
      colspan: slot.colspan,
      rowspan: slot.rowspan,
    };
  });
  renderTiles(tiles, pluginMeta);
  const toRects = computeTileRects(currentTiles, currentLayout.cols, currentLayout.rows, gutter);
  if (fromRects.length === toRects.length) {
    startTileAnimations(fromRects, toRects, toRects.map((_, idx) => idx));
  }
  requestPreview(collectConfig(), "Preview updated").catch(() => {});
  updateResetState();
};

const updateSafeViewport = () => {
  const base = getPreviewBaseSize();
  const scale = 1;
  const fullW = base.width * scale;
  const fullH = base.height * scale;
  viewportSize = {
    width: fullW,
    height: fullH,
    scale,
    baseWidth: base.safeWidth,
    baseHeight: base.safeHeight,
    offsetX: SAFE.left,
    offsetY: SAFE.top,
  };
  canvas.width = base.width;
  canvas.height = base.height;
  canvas.style.width = `${fullW}px`;
  canvas.style.height = `${fullH}px`;
  safeViewportEl.style.width = `${fullW}px`;
  safeViewportEl.style.height = `${fullH}px`;
};

const showPresetPreview = (presetName) => {
  const preset = PRESETS[presetName];
  if (!preset) return;
  if (presetPreviewTimer) {
    clearTimeout(presetPreviewTimer);
    presetPreviewTimer = null;
  }
  hoverIndex = null;
  presetPreview = { tiles: preset.tiles, layout: { cols: preset.cols, rows: preset.rows } };
};

const clearPresetPreview = () => {
  if (presetPreviewTimer) clearTimeout(presetPreviewTimer);
  presetPreviewTimer = setTimeout(() => {
    presetPreviewTimer = null;
    if (!presetPreview) return;
    presetPreview = null;
  }, 100);
};

const init = async () => {
  try {
    await loadSafeArea();
  } catch (e) {
    // ignore safe area errors, fall back to defaults
  }
  updateSafeViewport();
  setActiveTab("layout");
  await loadFonts();
  if (updateBtn) {
    await checkForUpdates();
    updateCheckTimer = setInterval(checkForUpdates, 60000);
  }
  const pluginMeta = await fetchJson("/api/plugins");
  currentPluginMeta = pluginMeta;
  const config = await fetchJson("/api/config");
  currentConfig = config;
  const data = await fetchPresets();
  const presets = data.presets || {};
  const match = data.active || findMatchingPreset(presets, config);
  await applyConfigToUI(config, { selectedPreset: match, skipPresetRefresh: true });
  initColorPalettes();
  refreshPresetSelect(presets, match);
  if (rafId === null) {
    rafId = requestAnimationFrame(drawLoop);
  }
  refreshApplyStatus();
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => applyPreset(btn.dataset.preset, pluginMeta));
    btn.addEventListener("mouseenter", () => showPresetPreview(btn.dataset.preset));
    btn.addEventListener("mouseleave", () => clearPresetPreview());
  });
  tilesEl.addEventListener("input", updateResetState);
  tilesEl.addEventListener("change", updateResetState);
  tilesEl.addEventListener("input", () => {
    commitActiveTileConfig();
  });
  tilesEl.addEventListener("change", () => {
    commitActiveTileConfig();
  });
  backToLayoutBtn.addEventListener("click", () => {
    if (activeTileIndex === null) return;
    commitActiveTileConfig();
    activeTileIndex = null;
    renderTileConfig(currentTiles, currentPluginMeta);
  });
  document.getElementById("gutter").addEventListener("input", updateResetState);
  document.getElementById("gutter").addEventListener("change", updateResetState);
  borderWidthInput.addEventListener("input", updateResetState);
  borderWidthInput.addEventListener("change", updateResetState);
  borderRadiusInput.addEventListener("input", updateResetState);
  borderRadiusInput.addEventListener("change", updateResetState);
  borderStyleSelect.addEventListener("change", updateResetState);
  borderColorSelect.addEventListener("change", updateResetState);
  if (borderDitherInput) {
    borderDitherInput.addEventListener("change", updateResetState);
    borderDitherInput.addEventListener("change", () => {
      updateDitherVisibility();
      scheduleDitherPreview();
    });
  }
  if (borderDitherColorSelect) {
    borderDitherColorSelect.addEventListener("change", updateResetState);
    borderDitherColorSelect.addEventListener("change", scheduleDitherPreview);
  }
  if (borderDitherStepInput) {
    borderDitherStepInput.addEventListener("input", updateResetState);
    borderDitherStepInput.addEventListener("change", updateResetState);
    borderDitherStepInput.addEventListener("input", scheduleDitherPreview);
    borderDitherStepInput.addEventListener("change", scheduleDitherPreview);
  }
  if (borderDitherRatioInput) {
    borderDitherRatioInput.addEventListener("input", updateResetState);
    borderDitherRatioInput.addEventListener("change", updateResetState);
    borderDitherRatioInput.addEventListener("input", scheduleDitherPreview);
    borderDitherRatioInput.addEventListener("change", scheduleDitherPreview);
  }
  backgroundColorSelect.addEventListener("change", updateResetState);
  if (backgroundDitherInput) {
    backgroundDitherInput.addEventListener("change", updateResetState);
    backgroundDitherInput.addEventListener("change", () => {
      updateDitherVisibility();
      scheduleDitherPreview();
    });
  }
  if (backgroundDitherColorSelect) {
    backgroundDitherColorSelect.addEventListener("change", updateResetState);
    backgroundDitherColorSelect.addEventListener("change", scheduleDitherPreview);
  }
  if (backgroundDitherStepInput) {
    backgroundDitherStepInput.addEventListener("input", updateResetState);
    backgroundDitherStepInput.addEventListener("change", updateResetState);
    backgroundDitherStepInput.addEventListener("input", scheduleDitherPreview);
    backgroundDitherStepInput.addEventListener("change", scheduleDitherPreview);
  }
  if (backgroundDitherRatioInput) {
    backgroundDitherRatioInput.addEventListener("input", updateResetState);
    backgroundDitherRatioInput.addEventListener("change", updateResetState);
    backgroundDitherRatioInput.addEventListener("input", scheduleDitherPreview);
    backgroundDitherRatioInput.addEventListener("change", scheduleDitherPreview);
  }
  scheduleInput.addEventListener("input", updateResetState);
  scheduleInput.addEventListener("change", updateResetState);
  fontFamilySelect.addEventListener("change", updateResetState);
  fontTitleInput.addEventListener("input", updateResetState);
  fontTitleInput.addEventListener("change", updateResetState);
  fontSubInput.addEventListener("input", updateResetState);
  fontSubInput.addEventListener("change", updateResetState);
  fontBodyInput.addEventListener("input", updateResetState);
  fontBodyInput.addEventListener("change", updateResetState);
  fontMetaInput.addEventListener("input", updateResetState);
  fontMetaInput.addEventListener("change", updateResetState);
  fontTempInput.addEventListener("input", updateResetState);
  fontTempInput.addEventListener("change", updateResetState);
  safeLeftInput.addEventListener("input", updateResetState);
  safeLeftInput.addEventListener("change", updateResetState);
  safeTopInput.addEventListener("input", updateResetState);
  safeTopInput.addEventListener("change", updateResetState);
  safeRightInput.addEventListener("input", updateResetState);
  safeRightInput.addEventListener("change", updateResetState);
  safeBottomInput.addEventListener("input", updateResetState);
  safeBottomInput.addEventListener("change", updateResetState);
  [safeLeftInput, safeTopInput, safeRightInput, safeBottomInput].forEach((input) => {
    input.addEventListener("input", () => updateSafeAreaFromInputs());
    input.addEventListener("change", () => updateSafeAreaFromInputs());
  });
  uploadFontBtn.addEventListener("click", () => fontFileInput.click());
  fontFileInput.addEventListener("change", async () => {
    const file = fontFileInput.files && fontFileInput.files[0];
    if (!file) return;
    try {
      await uploadFont(file);
    } catch (e) {
      setStatus(e.message, false);
    } finally {
      fontFileInput.value = "";
    }
  });
  if (previewStubInput) {
    previewStubInput.addEventListener("change", () => {
      requestPreview(collectConfig(), "Preview updated", true).catch(() => {});
    });
  }
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
  });
  canvas.addEventListener("pointerenter", () => {
    isPreviewHover = true;
  });
  canvas.addEventListener("pointerleave", () => {
    isPreviewHover = false;
    hoverIndex = null;
  });
  canvas.addEventListener("pointerdown", (event) => {
    const point = getCanvasPoint(event);
    const hit = findTileIndex(point);
    if (hit === null) return;
    commitActiveTileConfig();
    assignPreviewSlices(currentTiles);
    isDragging = true;
    dragSourceIndex = hit;
    dragTargetIndex = hit;
    dragStart = point;
    dragOffset = { x: 0, y: 0 };
    dragPointerId = event.pointerId;
    canvas.setPointerCapture(event.pointerId);
    hoverIndex = null;
  });
  canvas.addEventListener("pointermove", (event) => {
    const point = getCanvasPoint(event);
    if (isDragging && dragPointerId === event.pointerId) {
      dragOffset = { x: point.x - dragStart.x, y: point.y - dragStart.y };
      const hit = findTileIndex(point);
      dragTargetIndex = hit;
      return;
    }
    hoverIndex = findTileIndex(point);
  });
  canvas.addEventListener("pointerup", () => {
    if (!isDragging) return;
    if (dragTargetIndex !== null && dragSourceIndex !== null) {
      swapTilePositions(dragSourceIndex, dragTargetIndex);
      activeTileIndex = dragSourceIndex;
      renderTileConfig(currentTiles, currentPluginMeta);
    }
    isDragging = false;
    if (dragPointerId !== null) {
      canvas.releasePointerCapture(dragPointerId);
    }
    dragSourceIndex = null;
    dragTargetIndex = null;
    dragPointerId = null;
    dragStart = null;
    dragOffset = { x: 0, y: 0 };
  });
  canvas.addEventListener("pointercancel", () => {
    isDragging = false;
    if (dragPointerId !== null) {
      canvas.releasePointerCapture(dragPointerId);
    }
    dragSourceIndex = null;
    dragTargetIndex = null;
    dragPointerId = null;
    dragStart = null;
    dragOffset = { x: 0, y: 0 };
  });
  requestPreview(config, "Preview updated").catch((e) => setStatus(e.message, false));
  updateResetState();
  for (const [name, preset] of Object.entries(PRESETS)) {
    const match =
      preset.cols === config.layout.cols &&
      preset.rows === config.layout.rows &&
      preset.tiles.length === (config.layout.tiles || []).length &&
      preset.tiles.every((t, i) => {
        const cur = (config.layout.tiles || [])[i] || {};
        return (
          t.col === cur.col &&
          t.row === cur.row &&
          t.colspan === cur.colspan &&
          t.rowspan === cur.rowspan
        );
      });
    if (match) {
      document.querySelectorAll(".preset-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.preset === name);
      });
      break;
    }
  }
  if (![...document.querySelectorAll(".preset-btn")].some((b) => b.classList.contains("active"))) {
    document.querySelectorAll(".preset-btn").forEach((btn) => btn.classList.remove("active"));
  }
};


const saveConfigAndPreset = async (presetName, activatePreset = false) => {
  const config = collectConfig();
  await fetchJson("/api/config", {
    method: "POST",
    body: JSON.stringify(config),
  });
  let savedName = "";
  if (presetName) {
    const presetRes = await fetchJson("/api/presets", {
      method: "POST",
      body: JSON.stringify({ name: presetName, config }),
    });
    savedName = presetRes.name || presetName;
    const data = await fetchPresets();
    const presets = data.presets || {};
    refreshPresetSelect(presets, savedName);
    if (activatePreset) {
      await fetchJson("/api/presets/activate", {
        method: "POST",
        body: JSON.stringify({ name: savedName }),
      });
      config.active_preset = savedName;
    }
  }
  currentConfig = config;
  updateResetState();
  return savedName;
};

saveConfigBtn.addEventListener("click", async () => {
  try {
    await saveConfigAndPreset(presetSelect.value || "");
    setStatus("Config saved");
  } catch (e) {
    setStatus(e.message, false);
  }
});

saveAsBtn.addEventListener("click", async () => {
  try {
    const presetName = window.prompt("Preset name", "");
    if (!presetName) {
      setStatus("Preset name is required", false);
      return;
    }
    const savedName = await saveConfigAndPreset(presetName, true);
    if (savedName) {
      presetSelect.value = savedName;
    }
    setStatus("Preset saved");
  } catch (e) {
    setStatus(e.message, false);
  }
});

document.getElementById("preview").addEventListener("click", async () => {
  try {
    const config = collectConfig();
    await requestPreview(config, "Preview generated", true);
    updateResetState();
  } catch (e) {
    setStatus(e.message, false);
  }
});

document.getElementById("apply").addEventListener("click", async () => {
  try {
    const config = collectConfig();
    setUploading(true);
    setProgress(5, "Preparing upload...");
    await applyWithProgress(config);
    requestPreview(config, null, false).catch(() => {});
    updateResetState();
  } catch (e) {
    setStatus(e.message, false);
  } finally {
    setUploading(false);
  }
});

if (updateBtn) {
  updateBtn.addEventListener("click", async () => {
    updateBtn.disabled = true;
    updateBtn.classList.remove("update-available");
    updateBtn.textContent = "Updating...";
    try {
      await fetchJson("/api/update/apply", { method: "POST", body: "{}" });
      setStatus("Updating, restarting server...");
      setTimeout(() => {
        window.location.reload();
      }, 5000);
    } catch (e) {
      setStatus(e.message, false);
      updateBtn.textContent = "Update";
      updateBtn.disabled = false;
    }
  });
}


presetSelect.addEventListener("change", async () => {
  const name = presetSelect.value;
  if (!name) {
    deletePresetBtn.disabled = true;
    return;
  }
  const data = await fetchPresets();
  const presets = data.presets || {};
  const config = presets[name];
  if (!config) return;
  await applyConfigToUI(config, { selectedPreset: name });
  currentConfig = { ...config, active_preset: name };
  const snapshot = collectConfig();
  snapshot.active_preset = name;
  currentConfig = snapshot;
  updateResetState();
  deletePresetBtn.disabled = false;
  setStatus("Generating preview...");
  const previewPromise = requestPreview(config, null, true).catch(() => {});
  try {
    await fetchJson("/api/presets/activate", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    await previewPromise;
    setStatus("Preset selected");
  } catch (e) {
    setStatus(e.message, false);
  }
});

deletePresetBtn.addEventListener("click", () => {
  const name = presetSelect.value;
  if (!name) return;
  fetchJson(`/api/presets?name=${encodeURIComponent(name)}`, { method: "DELETE" })
    .then(async () => {
      const data = await fetchPresets();
      const presets = data.presets || {};
      refreshPresetSelect(presets, "");
      setStatus("Preset deleted");
    })
    .catch((err) => {
      setStatus(err.message, false);
    });
});

window.addEventListener("resize", () => {
  updateSafeViewport();
});
if (!appState.initialized) {
  appState.initialized = true;
  init();
}
