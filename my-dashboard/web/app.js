const statusEl = document.getElementById("status");
const applyProgressEl = document.getElementById("applyProgress");
const applyProgressBarEl = document.getElementById("applyProgressBar");
const applyBtn = document.getElementById("apply");
const tilesEl = document.getElementById("tiles");
const safeViewportEl = document.getElementById("safeViewport");
const resetBtn = document.getElementById("resetConfig");
const scheduleInput = document.getElementById("updateInterval");
const borderWidthInput = document.getElementById("borderWidth");
const borderRadiusInput = document.getElementById("borderRadius");
const borderStyleSelect = document.getElementById("borderStyle");
const borderColorSelect = document.getElementById("borderColor");
const layoutPanelEl = document.getElementById("layoutPanel");
const configPanelEl = document.getElementById("configPanel");
const backToLayoutBtn = document.getElementById("backToLayout");
const canvas = document.getElementById("previewCanvas");
const ctx = canvas.getContext("2d", { alpha: false });

const SAFE = { left: 60, top: 35, right: 55, bottom: 10 };
const DEFAULT_W = 800;
const DEFAULT_H = 480;
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

const initialSafeWidth = DEFAULT_W - SAFE.left - SAFE.right;
const initialSafeHeight = DEFAULT_H - SAFE.top - SAFE.bottom;
viewportSize = {
  width: initialSafeWidth,
  height: initialSafeHeight,
  scale: 1,
  baseWidth: initialSafeWidth,
  baseHeight: initialSafeHeight,
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
  appState.previewRequest = (async () => {
    try {
      const res = await fetchJson("/api/preview", {
        method: "POST",
        body: JSON.stringify(config),
      });
      const src = res.image_data || `${res.image}?ts=${Date.now()}`;
      previewImage = await loadPreviewImage(src);
      previewReady = true;
      updateSafeViewport();
      assignPreviewSlices(currentTiles);
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
      sx: SAFE.left + rect.left,
      sy: SAFE.top + rect.top,
      sw: rect.w,
      sh: rect.h,
    };
  });
};

const computeTileRects = (tiles, cols, rows, gutterBase) => {
  const baseWidth = viewportSize.baseWidth;
  const baseHeight = viewportSize.baseHeight;
  const colWBase = Math.floor((baseWidth - gutterBase * (cols - 1)) / cols);
  const rowHBase = Math.floor((baseHeight - gutterBase * (rows - 1)) / rows);
  return tiles.map((tile) => {
    const left = tile.col * (colWBase + gutterBase);
    const top = tile.row * (rowHBase + gutterBase);
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
    currentTiles.forEach((tile, idx) => {
      const baseRect = rects[idx];
      if (!baseRect) return;
      let rect = getAnimatedRect(idx, baseRect, now);
      if (isDragging && idx === dragSourceIndex) {
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
  Object.keys(pluginMeta.defaults).forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = pluginMeta.names?.[name] || name;
    if (tile.plugin === name) opt.selected = true;
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
    cfgWrap.appendChild(label);

    if (def.type === "enum") {
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
      return;
    }

    if (def.type === "list") {
      const list = Array.isArray(current[key]) ? current[key] : [];
      const listWrap = document.createElement("div");
      listWrap.className = "array-list";
      listWrap.dataset.key = key;
      listWrap.dataset.itemType = def.itemType || "string";
      list.forEach((value) => {
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

    const input = document.createElement("input");
    input.dataset.key = key;
    if (def.type === "number") {
      input.type = "number";
      if (def.min !== undefined) input.min = def.min;
      if (def.max !== undefined) input.max = def.max;
      if (def.step !== undefined) input.step = def.step;
      input.value = current[key] ?? "";
    } else if (def.type === "boolean") {
      input.type = "checkbox";
      input.checked = Boolean(current[key]);
    } else {
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
    update_interval_minutes: scheduleInput.value === "" ? null : Number(scheduleInput.value),
    layout: {
      cols: currentLayout.cols,
      rows: currentLayout.rows,
      gutter: parseInt(document.getElementById("gutter").value, 10),
      border: {
        width: borderWidthInput.value === "" ? 0 : Number(borderWidthInput.value),
        radius: borderRadiusInput.value === "" ? 0 : Number(borderRadiusInput.value),
        style: borderStyleSelect.value,
        color: borderColorSelect.value,
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

const normalizeConfig = (cfg) => JSON.stringify(cfg || {});

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
  resetBtn.classList.toggle("hidden", !dirty);
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
  const safeW = base.safeWidth * scale;
  const safeH = base.safeHeight * scale;
  viewportSize = { width: safeW, height: safeH, scale, baseWidth: base.safeWidth, baseHeight: base.safeHeight };
  canvas.width = base.safeWidth;
  canvas.height = base.safeHeight;
  canvas.style.width = `${safeW}px`;
  canvas.style.height = `${safeH}px`;
  safeViewportEl.style.width = `${safeW}px`;
  safeViewportEl.style.height = `${safeH}px`;
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
  const pluginMeta = await fetchJson("/api/plugins");
  const config = await fetchJson("/api/config");
  currentConfig = config;
  currentLayout = { cols: config.layout.cols, rows: config.layout.rows };
  document.getElementById("gutter").value = config.layout.gutter;
  borderWidthInput.value = config.layout.border?.width ?? 1;
  borderRadiusInput.value = config.layout.border?.radius ?? 0;
  borderStyleSelect.value = config.layout.border?.style ?? "solid";
  borderColorSelect.value = config.layout.border?.color ?? "black";
  if (config.update_interval_minutes != null) {
    scheduleInput.value = String(config.update_interval_minutes);
  } else {
    scheduleInput.value = parseScheduleMinutes(config.update_schedule);
  }
  renderTiles(config.layout.tiles, pluginMeta);
  updateSafeViewport();
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
  scheduleInput.addEventListener("input", updateResetState);
  scheduleInput.addEventListener("change", updateResetState);
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

document.getElementById("saveConfig").addEventListener("click", async () => {
  try {
    const config = collectConfig();
    await fetchJson("/api/config", {
      method: "POST",
      body: JSON.stringify(config),
    });
    currentConfig = config;
    updateResetState();
    setStatus("Config saved");
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

resetBtn.addEventListener("click", async () => {
  if (!currentConfig) return;
  const pluginMeta = await fetchJson("/api/plugins");
  currentLayout = { cols: currentConfig.layout.cols, rows: currentConfig.layout.rows };
  document.getElementById("gutter").value = currentConfig.layout.gutter;
  borderWidthInput.value = currentConfig.layout.border?.width ?? 1;
  borderRadiusInput.value = currentConfig.layout.border?.radius ?? 0;
  borderStyleSelect.value = currentConfig.layout.border?.style ?? "solid";
  borderColorSelect.value = currentConfig.layout.border?.color ?? "black";
  if (currentConfig.update_interval_minutes != null) {
    scheduleInput.value = String(currentConfig.update_interval_minutes);
  } else {
    scheduleInput.value = parseScheduleMinutes(currentConfig.update_schedule);
  }
  renderTiles(currentConfig.layout.tiles, pluginMeta);
  updateResetState();
});

window.addEventListener("resize", () => {
  updateSafeViewport();
});
if (!appState.initialized) {
  appState.initialized = true;
  init();
}
