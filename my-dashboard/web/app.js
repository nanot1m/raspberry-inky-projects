const img = document.getElementById("dashboard");
const statusEl = document.getElementById("status");
const tilesEl = document.getElementById("tiles");
const overlayEl = document.getElementById("overlay");
const safeViewportEl = document.getElementById("safeViewport");
const resetBtn = document.getElementById("resetConfig");
const scheduleInput = document.getElementById("updateInterval");
const previewTilesEl = document.getElementById("previewTiles");
const previewLoadingEl = document.getElementById("previewLoading");
const borderWidthInput = document.getElementById("borderWidth");
const borderRadiusInput = document.getElementById("borderRadius");
const borderStyleSelect = document.getElementById("borderStyle");
const borderColorSelect = document.getElementById("borderColor");
let activeTileIndex = null;
const SAFE = { left: 60, top: 35, right: 55, bottom: 10 };
let viewportSize = { width: 0, height: 0, scale: 1, baseWidth: 0, baseHeight: 0 };
let currentTiles = [];
let currentPluginMeta = null;
let dragSourceIndex = null;
let dragTargetIndex = null;
let isDragging = false;
let dragTargetRect = null;
let lastOverlayRects = new Map();
let rectElements = new Map();
let hoverIndex = null;
let isPreviewHover = false;
let presetPreview = null;
let overlayMode = "current";
let presetPreviewTimer = null;
let overlayRects = new Map();
let dragPointerId = null;
let dragStart = null;
let dragPreviewTile = null;
let previewTileElements = new Map();
let currentPreviewSrc = "/generated/dashboard.png";

const setStatus = (msg, ok = true) => {
  statusEl.textContent = msg;
  statusEl.style.color = ok ? "#0a5" : "#c00";
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
let previewRequest = appState.previewRequest;
const cancelPreviewTimer = () => {
  if (previewTimer) {
    clearTimeout(previewTimer);
    previewTimer = null;
  }
};
const waitForImageLoad = (src) => new Promise((resolve, reject) => {
  const onLoad = () => {
    cleanup();
    resolve();
  };
  const onError = () => {
    cleanup();
    reject(new Error("Failed to load preview image"));
  };
  const cleanup = () => {
    img.removeEventListener("load", onLoad);
    img.removeEventListener("error", onError);
  };
  img.addEventListener("load", onLoad);
  img.addEventListener("error", onError);
  img.src = src;
});

const setPreviewLoading = (loading) => {
  if (!previewLoadingEl) return;
  previewLoadingEl.classList.toggle("visible", loading);
};

const requestPreview = async (config, successMessage = "Preview updated") => {
  if (appState.previewRequest) return appState.previewRequest;
  cancelPreviewTimer();
  setStatus("Generating preview...");
  setPreviewLoading(true);
  appState.previewRequest = (async () => {
    try {
      const res = await fetchJson("/api/preview", {
        method: "POST",
        body: JSON.stringify(config),
      });
      const src = res.image_data || `${res.image}?ts=${Date.now()}`;
      currentPreviewSrc = src;
      await waitForImageLoad(src);
      updateSafeViewport();
      assignPreviewSlices(currentTiles);
      renderPreviewTiles(currentTiles);
      setStatus(successMessage);
      return res;
    } catch (err) {
      setStatus(err.message, false);
      throw err;
    } finally {
      setPreviewLoading(false);
      appState.previewRequest = null;
    }
  })();
  return appState.previewRequest;
};

let previewTimer = null;
const schedulePreview = () => {
  cancelPreviewTimer();
};

const refreshImage = (path = "/generated/dashboard.png") => {
  currentPreviewSrc = `${path}?ts=${Date.now()}`;
  img.src = currentPreviewSrc;
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
      bgX: -(SAFE.left + rect.left),
      bgY: -(SAFE.top + rect.top),
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

const getBorderConfig = () => ({
  width: borderWidthInput.value === "" ? 0 : Number(borderWidthInput.value),
  radius: borderRadiusInput.value === "" ? 0 : Number(borderRadiusInput.value),
  style: borderStyleSelect.value,
  color: borderColorSelect.value,
});

const renderPreviewTiles = (tiles, layoutOverride = null) => {
  if (!viewportSize.width || !viewportSize.height) return;
  if (!img.naturalWidth || !img.naturalHeight) return;
  const cols = layoutOverride?.cols ?? currentLayout.cols;
  const rows = layoutOverride?.rows ?? currentLayout.rows;
  const gutterBase = parseInt(document.getElementById("gutter").value, 10) || 0;
  const rects = computeTileRects(tiles, cols, rows, gutterBase);
  const scale = viewportSize.scale;
  const fullW = img.naturalWidth;
  const fullH = img.naturalHeight;
  previewTilesEl.style.width = `${fullW}px`;
  previewTilesEl.style.height = `${fullH}px`;
  previewTilesEl.style.transform = `scale(${scale})`;
  previewTilesEl.style.transformOrigin = "top left";
  const updateTile = (tileEl, rect, idx) => {
    const left = rect.left;
    const top = rect.top;
    const width = rect.w + 1;
    const height = rect.h + 1;
    tileEl.style.left = `${left}px`;
    tileEl.style.top = `${top}px`;
    tileEl.style.width = `${width}px`;
    tileEl.style.height = `${height}px`;
    const preview = tiles[idx]?.preview;
    const bgX = preview?.bgX ?? -(SAFE.left + left);
    const bgY = preview?.bgY ?? -(SAFE.top + top);
    tileEl.style.backgroundImage = `url(${currentPreviewSrc})`;
    tileEl.style.backgroundSize = `${fullW}px ${fullH}px`;
    tileEl.style.backgroundPosition = `${bgX}px ${bgY}px`;
  };

  if (previewTileElements.size === tiles.length && previewTilesEl.childElementCount === tiles.length) {
    rects.forEach((rect, idx) => {
      const tileEl = previewTileElements.get(idx);
      if (!tileEl) return;
      updateTile(tileEl, rect, idx);
    });
    return;
  }

  previewTilesEl.innerHTML = "";
  previewTileElements = new Map();
  rects.forEach((rect, idx) => {
    const tile = document.createElement("div");
    tile.className = "preview-tile";
    tile.dataset.index = String(previewTileElements.size);
    updateTile(tile, rect, idx);
    previewTilesEl.appendChild(tile);
    previewTileElements.set(Number(tile.dataset.index), tile);
  });
};

const updateOverlayVisibility = () => {
  const show = isPreviewHover || isDragging || activeTileIndex !== null || Boolean(presetPreview);
  overlayEl.classList.toggle("visible", show);
  overlayEl.classList.toggle("mode-hover", isPreviewHover && overlayMode === "current");
  overlayEl.classList.toggle("mode-active-only", !isPreviewHover && activeTileIndex !== null && overlayMode === "current");
  overlayEl.classList.toggle("mode-preset", overlayMode === "preset");
};

const applyOverlayState = () => {
  rectElements.forEach((rect, idx) => {
    if (overlayMode !== "current") {
      rect.classList.remove("active", "hovered", "dragging", "drop-target");
      return;
    }
    rect.classList.toggle("active", activeTileIndex === idx);
    rect.classList.toggle("hovered", hoverIndex === idx);
    rect.classList.toggle("dragging", dragSourceIndex === idx);
    rect.classList.toggle("drop-target", dragTargetIndex === idx && dragSourceIndex !== idx);
  });
  updateOverlayVisibility();
};

const reorderTiles = (fromIndex, toIndex) => {
  if (fromIndex === toIndex) return;
  const next = [...currentTiles];
  const [moved] = next.splice(fromIndex, 1);
  if (!moved) return;
  next.splice(toIndex, 0, moved);
  currentTiles = next;
  renderTiles(currentTiles, currentPluginMeta);
  drawOverlay(currentTiles);
  renderPreviewTiles(currentTiles);
  updateResetState();
};

const swapTilePositions = (fromIndex, toIndex) => {
  if (fromIndex === toIndex) return;
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
  renderTiles(currentTiles, currentPluginMeta);
  drawOverlay(currentTiles);
  renderPreviewTiles(currentTiles);
  updateResetState();
};

const renderTileConfig = (tiles, pluginMeta) => {
  tilesEl.innerHTML = "";
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

const normalizeConfig = (cfg) => JSON.stringify(cfg || {});

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
  drawOverlay(tiles);
  renderPreviewTiles(tiles);
  requestPreview(collectConfig(), "Preview updated").catch(() => {});
  updateResetState();
};

const updateSafeViewport = () => {
  if (!img.naturalWidth || !img.naturalHeight) return;
  const targetWidth = safeViewportEl.parentElement.clientWidth;
  const scale = targetWidth / img.naturalWidth;
  const safeWBase = img.naturalWidth - SAFE.left - SAFE.right;
  const safeHBase = img.naturalHeight - SAFE.top - SAFE.bottom;
  const safeW = safeWBase * scale;
  const safeH = safeHBase * scale;
  safeViewportEl.style.width = `${safeW}px`;
  safeViewportEl.style.height = `${safeH}px`;
  img.style.transform = `translate(${-SAFE.left * scale}px, ${-SAFE.top * scale}px) scale(${scale})`;
  img.style.transformOrigin = "top left";
  viewportSize = { width: safeW, height: safeH, scale, baseWidth: safeWBase, baseHeight: safeHBase };
};

const drawOverlay = (tiles, layoutOverride = null, mode = "current") => {
  overlayMode = mode;
  overlayEl.innerHTML = "";
  rectElements = new Map();
  const width = viewportSize.width;
  const height = viewportSize.height;
  if (!width || !height) {
    updateOverlayVisibility();
    return;
  }
  const cols = layoutOverride?.cols ?? currentLayout.cols;
  const rows = layoutOverride?.rows ?? currentLayout.rows;
  const gutterBase = parseInt(document.getElementById("gutter").value, 10) || 0;
  const baseWidth = viewportSize.baseWidth;
  const baseHeight = viewportSize.baseHeight;
  const colWBase = Math.floor((baseWidth - gutterBase * (cols - 1)) / cols);
  const rowHBase = Math.floor((baseHeight - gutterBase * (rows - 1)) / rows);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${baseWidth} ${baseHeight}`);
  svg.addEventListener("pointermove", (event) => {
    if (!isDragging || dragPointerId !== event.pointerId) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = baseWidth / rect.width;
    const scaleY = baseHeight / rect.height;
    const localX = (event.clientX - rect.left) * scaleX;
    const localY = (event.clientY - rect.top) * scaleY;
    if (dragStart && dragPreviewTile) {
      const dx = localX - dragStart.x;
      const dy = localY - dragStart.y;
      dragPreviewTile.style.transform = `translate(${dx}px, ${dy}px)`;
    }
    let nextIndex = null;
    for (const [idx, box] of overlayRects.entries()) {
      if (
        localX >= box.left &&
        localX <= box.left + box.w &&
        localY >= box.top &&
        localY <= box.top + box.h
      ) {
        nextIndex = idx;
        break;
      }
    }
    if (nextIndex !== null && nextIndex !== dragTargetIndex) {
      dragTargetIndex = nextIndex;
      applyOverlayState();
    }
  });
  svg.addEventListener("pointercancel", () => {
    if (!isDragging) return;
    dragSourceIndex = null;
    dragTargetIndex = null;
    dragTargetRect = null;
    isDragging = false;
    dragStart = null;
    if (dragPreviewTile) {
      dragPreviewTile.classList.remove("dragging");
      dragPreviewTile.style.transform = "";
      dragPreviewTile.style.zIndex = "";
    }
    dragPreviewTile = null;
    if (dragPointerId !== null) {
      svg.releasePointerCapture(dragPointerId);
    }
    dragPointerId = null;
    drawOverlay(currentTiles);
  });
  svg.addEventListener("pointerup", () => {
    if (!isDragging) return;
    if (dragSourceIndex !== null && dragTargetIndex !== null) {
      const nextActive = dragSourceIndex;
      isDragging = false;
      dragTargetRect = null;
      dragStart = null;
      if (dragPreviewTile) {
        dragPreviewTile.classList.remove("dragging");
        dragPreviewTile.style.transform = "";
        dragPreviewTile.style.zIndex = "";
      }
      dragPreviewTile = null;
      if (dragPointerId !== null) {
        svg.releasePointerCapture(dragPointerId);
      }
      dragPointerId = null;
      swapTilePositions(dragSourceIndex, dragTargetIndex);
      activeTileIndex = nextActive;
      renderTileConfig(currentTiles, currentPluginMeta);
      applyOverlayState();
      dragSourceIndex = null;
      dragTargetIndex = null;
      return;
    }
    dragSourceIndex = null;
    dragTargetIndex = null;
    dragTargetRect = null;
    isDragging = false;
    dragStart = null;
    if (dragPreviewTile) {
      dragPreviewTile.classList.remove("dragging");
      dragPreviewTile.style.transform = "";
      dragPreviewTile.style.zIndex = "";
    }
    dragPreviewTile = null;
    if (dragPointerId !== null) {
      svg.releasePointerCapture(dragPointerId);
    }
    dragPointerId = null;
    applyOverlayState();
  });
  svg.addEventListener("pointerleave", () => {
    if (!isDragging) return;
    dragSourceIndex = null;
    dragTargetIndex = null;
    dragTargetRect = null;
    isDragging = false;
    dragStart = null;
    if (dragPreviewTile) {
      dragPreviewTile.classList.remove("dragging");
      dragPreviewTile.style.transform = "";
      dragPreviewTile.style.zIndex = "";
    }
    dragPreviewTile = null;
    if (dragPointerId !== null) {
      svg.releasePointerCapture(dragPointerId);
    }
    dragPointerId = null;
    applyOverlayState();
  });

  const nextOverlayRects = new Map();
  tiles.forEach((tile, idx) => {
    const left = tile.col * (colWBase + gutterBase);
    const top = tile.row * (rowHBase + gutterBase);
    const w = colWBase * tile.colspan + gutterBase * (tile.colspan - 1);
    const h = rowHBase * tile.rowspan + gutterBase * (tile.rowspan - 1);
    const bbox = { left, top, w, h };
    nextOverlayRects.set(idx, bbox);
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", left + 1);
    rect.setAttribute("y", top + 1);
    rect.setAttribute("width", Math.max(0, w - 2));
    rect.setAttribute("height", Math.max(0, h - 2));
    rectElements.set(idx, rect);
    rect.addEventListener("click", () => {
      if (isDragging) return;
      activeTileIndex = idx;
      renderTileConfig(currentTiles, currentPluginMeta);
      drawOverlay(tiles);
    });
    rect.addEventListener("pointerdown", (event) => {
      isDragging = true;
      dragSourceIndex = idx;
      dragTargetIndex = idx;
      dragTargetRect = rect;
      dragPointerId = event.pointerId;
      const svgRect = svg.getBoundingClientRect();
      const localX = (event.clientX - svgRect.left) * (baseWidth / svgRect.width);
      const localY = (event.clientY - svgRect.top) * (baseHeight / svgRect.height);
      dragStart = {
        x: localX,
        y: localY,
      };
      dragPreviewTile = previewTileElements.get(idx) || null;
      if (dragPreviewTile) {
        dragPreviewTile.classList.add("dragging");
        dragPreviewTile.style.zIndex = "5";
      }
      svg.setPointerCapture(event.pointerId);
      hoverIndex = null;
      applyOverlayState();
    });
    rect.addEventListener("pointerenter", () => {
      if (isDragging) {
        dragTargetIndex = idx;
        if (dragTargetRect && dragTargetRect !== rect) {
          dragTargetRect.classList.remove("drop-target");
        }
        dragTargetRect = rect;
        applyOverlayState();
        return;
      }
      hoverIndex = idx;
      applyOverlayState();
    });
    rect.addEventListener("pointerleave", () => {
      if (isDragging) return;
      if (hoverIndex === idx) {
        hoverIndex = null;
        applyOverlayState();
      }
    });
    const prev = lastOverlayRects.get(idx);
    svg.appendChild(rect);
  });
  overlayEl.appendChild(svg);
  lastOverlayRects = nextOverlayRects;
  overlayRects = nextOverlayRects;
  applyOverlayState();
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
  drawOverlay(preset.tiles, presetPreview.layout, "preset");
  renderPreviewTiles(preset.tiles, presetPreview.layout);
};

const clearPresetPreview = () => {
  if (presetPreviewTimer) clearTimeout(presetPreviewTimer);
  presetPreviewTimer = setTimeout(() => {
    presetPreviewTimer = null;
    if (!presetPreview) return;
    presetPreview = null;
    drawOverlay(currentTiles);
    renderPreviewTiles(currentTiles);
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
  drawOverlay(currentTiles);
  renderPreviewTiles(currentTiles);
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => applyPreset(btn.dataset.preset, pluginMeta));
    btn.addEventListener("mouseenter", () => showPresetPreview(btn.dataset.preset));
    btn.addEventListener("mouseleave", () => clearPresetPreview());
  });
  tilesEl.addEventListener("input", updateResetState);
  tilesEl.addEventListener("change", updateResetState);
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
  safeViewportEl.addEventListener("mouseenter", () => {
    isPreviewHover = true;
    updateOverlayVisibility();
  });
  safeViewportEl.addEventListener("mouseleave", () => {
    isPreviewHover = false;
    hoverIndex = null;
    updateOverlayVisibility();
    applyOverlayState();
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
  updateOverlayVisibility();
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
    await requestPreview(config, "Preview generated");
    updateResetState();
  } catch (e) {
    setStatus(e.message, false);
  }
});

document.getElementById("apply").addEventListener("click", async () => {
  try {
    const config = collectConfig();
    await fetchJson("/api/apply", {
      method: "POST",
      body: JSON.stringify(config),
    });
    setStatus("Uploaded to device");
    requestPreview(config, "Preview updated").catch(() => {});
    updateResetState();
  } catch (e) {
    setStatus(e.message, false);
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
  drawOverlay(currentTiles);
  renderPreviewTiles(currentTiles);
  updateResetState();
});

img.addEventListener("load", () => {
  updateSafeViewport();
  drawOverlay(currentTiles);
  renderPreviewTiles(currentTiles);
});
window.addEventListener("resize", () => {
  updateSafeViewport();
  drawOverlay(currentTiles);
  renderPreviewTiles(currentTiles);
});
document.addEventListener("click", (event) => {
  const inPreview = safeViewportEl.contains(event.target);
  const layoutPanel = tilesEl.closest(".panel");
  if (inPreview || (layoutPanel && layoutPanel.contains(event.target))) return;
  if (activeTileIndex === null) return;
  activeTileIndex = null;
  renderTileConfig(currentTiles, currentPluginMeta);
  drawOverlay(currentTiles);
});
if (!appState.initialized) {
  appState.initialized = true;
  init();
}
