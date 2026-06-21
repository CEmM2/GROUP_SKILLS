# Mermaid module — opt-in topology for AutViam reports

> **Attribution.** The zoom/pan/fit/expand diagram engine in Block 3 (and the chrome in Blocks 1–2) is adapted from the **visual-explainer** skill by **Nico Bailon** (`nicobailon`), MIT © 2025 — specifically its `templates/mermaid-flowchart.html`. The interaction engine is ported largely verbatim; the theme-wiring (reading `report_theme.css` vars via `getComputedStyle`) and the ◐-toggle re-render are AutViam additions. See `CREDITS.md` for the full notice.

The frozen report shell (`references/report_shell.md`) deliberately ships **no Mermaid machinery** so the common case stays a single static page. When a report genuinely needs **topology** — a flow, sequence, state machine, data-flow, or an architecture overview where the *connections* carry the meaning — opt in by reading this file and pasting the three blocks below into the page you're already building with the frozen shell.

Read this once per session, the first time a report needs a diagram. Everything here is theme-wired to `templates/report_theme.css`: the diagram inherits the frozen Seuss palette and **re-renders when the ◐ toggle flips** `data-theme`, so light and dark both look intentional with zero extra work.

## When to use Mermaid vs. the shell's static primitives

| Content | Use |
|---|---|
| Pipeline / flowchart / decision tree | **Mermaid** (`flowchart TD`) |
| Sequence / lifelines | **Mermaid** (`sequenceDiagram`) |
| State machine | **Mermaid** (`stateDiagram-v2`, but see the label caveat) |
| Data-flow with edge labels | **Mermaid** (`flowchart TD` + `\|labels\|`) |
| Architecture **overview** (≤8 nodes, topology matters) | **Mermaid** |
| Architecture **detail** (rich per-module content) | shell `.card` grid — *not* Mermaid |
| A short linear A→B→C status strip | shell `.pipe` / `.pstate` — *not* Mermaid |
| Comparison / matrix / audit rows | shell `.tbl-scroll` table — *not* Mermaid |

If the thing you want to show is **content in boxes**, use cards. If it's **arrows between boxes**, use Mermaid. The hybrid pattern (a small Mermaid overview followed by `.card` detail) is the default for anything 15+ elements — never cram 15+ nodes into one diagram; it renders unreadably small even with zoom.

## Block 1 — HTML (one `.diagram-shell` per diagram)

Drop inside `.wrap`. The `<script type="text/plain" class="diagram-source">` holds the Mermaid source; it is read, not executed.

```html
<section class="diagram-shell">
  <p class="diagram-shell__hint">Ctrl/Cmd + wheel to zoom · scroll/drag to pan · double-click to fit · ⛶ opens full size</p>
  <div class="mermaid-wrap">
    <div class="zoom-controls">
      <button type="button" data-action="zoom-in" title="Zoom in">+</button>
      <button type="button" data-action="zoom-out" title="Zoom out">&minus;</button>
      <button type="button" data-action="zoom-fit" title="Smart fit">&#8634;</button>
      <button type="button" data-action="zoom-one" title="1:1 zoom">1:1</button>
      <button type="button" data-action="zoom-expand" title="Open full size">&#x26F6;</button>
      <span class="zoom-label">Loading…</span>
    </div>
    <div class="mermaid-viewport"><div class="mermaid mermaid-canvas"></div></div>
  </div>
  <script type="text/plain" class="diagram-source">
    flowchart TD
      A["Sidecar<br/>handshake.py"] -->|"LOGIC_LOOM_API_READY:&lt;port&gt;"| B["sidecar.rs parser"]
      B --> C["Tauri state"]
  </script>
</section>
```

## Block 2 — CSS (append to the same `<style>` block, after the frozen theme + shell CSS)

This is **only** the diagram chrome — no colors are hard-coded; everything resolves to `report_theme.css` vars, so the diagram matches the frozen palette in both themes.

```css
.diagram-shell { position:relative; margin:0 0 22px; }
.diagram-shell__hint { font-family:var(--font-mono); font-size:11px; color:var(--text-muted); margin-bottom:8px; opacity:.8; }
.mermaid-wrap { position:relative; background:var(--bg-surface); border:var(--card-border-width) solid var(--border); border-radius:var(--radius-card); box-shadow:var(--card-shadow); padding:28px 20px; overflow:hidden; display:flex; justify-content:center; align-items:center; min-height:360px; cursor:grab; }
.mermaid-wrap.is-panning { cursor:grabbing; user-select:none; }
.zoom-controls { position:absolute; top:8px; right:8px; display:flex; gap:2px; z-index:10; background:var(--bg-surface); border:2px solid var(--border); border-radius:10px; padding:2px; }
.zoom-controls button { width:28px; height:28px; border:none; background:transparent; color:var(--text-muted); font-family:var(--font-mono); font-size:14px; cursor:pointer; border-radius:8px; display:flex; align-items:center; justify-content:center; transition:background .15s,color .15s; }
.zoom-controls button:hover { background:var(--pill-bg); color:var(--text-bright); }
.zoom-label { font-family:var(--font-mono); font-size:10px; color:var(--text-muted); padding:0 6px; white-space:nowrap; }
.mermaid-viewport { position:relative; overflow:hidden; width:100%; height:100%; min-height:300px; }
.mermaid-canvas { position:absolute; top:0; left:0; }
.mermaid .nodeLabel { font-family:var(--font-main) !important; font-size:16px !important; }
.mermaid .edgeLabel { font-family:var(--font-mono) !important; font-size:13px !important; }
.mermaid .node rect, .mermaid .node circle, .mermaid .node polygon, .mermaid .node path { stroke-width:1.5px !important; }
.mermaid .edgeLabel { background:var(--bg-surface) !important; }
```

## Block 3 — JS (ES module; place once before `</body>`, after the toggle script)

Faithful port of the proven zoom/pan/fit engine, plus two AutViam additions: **(a)** `themeVars()` reads the frozen palette from `report_theme.css` via `getComputedStyle` instead of hard-coding teal, and **(b)** a `MutationObserver` on `data-theme` re-initializes Mermaid and re-renders every diagram when the ◐ toggle flips, so the baked-in SVG colors track the theme.

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  import elkLayouts from 'https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk/dist/mermaid-layout-elk.esm.min.mjs';

  const config = { fitPadding:28, minHeight:360, maxHeightPx:960, maxHeightVh:0.84, maxInitialZoom:1.8, minZoom:0.08, maxZoom:6.5, zoomStep:0.14, readabilityFloor:0.58 };
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  let activeDrag = null;
  addEventListener('mousemove', (e) => activeDrag?.onMove(e));
  addEventListener('mouseup', () => { activeDrag?.onEnd(); activeDrag = null; });

  // (a) Read the frozen Seuss palette from report_theme.css — never hard-code colors.
  function themeVars() {
    const cs = getComputedStyle(document.documentElement);
    const v = (n) => cs.getPropertyValue(n).trim();
    return {
      fontFamily: v('--font-main') || "'Baloo 2', system-ui, sans-serif",
      fontSize: '16px',
      background: v('--bg-surface'),
      mainBkg: v('--accent-bg'),
      primaryColor: v('--accent-bg'), primaryBorderColor: v('--accent'), primaryTextColor: v('--text-bright'),
      secondaryColor: v('--purple-bg'), secondaryBorderColor: v('--purple'), secondaryTextColor: v('--text-bright'),
      tertiaryColor: v('--green-bg'), tertiaryBorderColor: v('--green'), tertiaryTextColor: v('--text-bright'),
      lineColor: v('--text-muted'),
      clusterBkg: v('--bg-elevated'), clusterBorder: v('--border'),
      noteBkgColor: v('--orange-bg'), noteTextColor: v('--text-bright'), noteBorderColor: v('--orange'),
      titleColor: v('--text-bright'), edgeLabelBackground: v('--bg-surface'),
    };
  }
  function bgColor() { return getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#FFF8E7'; }

  mermaid.registerLayoutLoaders(elkLayouts);
  function initMermaid() {
    mermaid.initialize({ startOnLoad:false, theme:'base', look:'classic', layout:'elk', securityLevel:'loose', themeVariables: themeVars() });
  }
  initMermaid();

  const shells = [];

  function initDiagram(shell) {
    const wrap = shell.querySelector('.mermaid-wrap');
    const viewport = shell.querySelector('.mermaid-viewport');
    const canvas = shell.querySelector('.mermaid-canvas');
    const source = shell.querySelector('.diagram-source');
    const label = shell.querySelector('.zoom-label');
    if (!wrap || !viewport || !canvas || !source || !label) { console.error('initDiagram: missing elements', shell); return; }

    let zoom = 1, fitMode = 'contain', panX = 0, panY = 0, svgW = 0, svgH = 0;
    let sx = 0, sy = 0, spx = 0, spy = 0, touchDist = 0, touchCx = 0, touchCy = 0;
    let renderSeq = 0;

    function constrainPan() {
      const vpW = viewport.clientWidth, vpH = viewport.clientHeight, rW = svgW * zoom, rH = svgH * zoom, pad = config.fitPadding;
      panX = (rW + pad * 2 <= vpW) ? (vpW - rW) / 2 : clamp(panX, vpW - rW - pad, pad);
      panY = (rH + pad * 2 <= vpH) ? (vpH - rH) / 2 : clamp(panY, vpH - rH - pad, pad);
    }
    function applyTransform() {
      const svg = canvas.querySelector('svg'); if (!svg || !svgW) return;
      constrainPan();
      svg.style.width = (svgW * zoom) + 'px'; svg.style.height = (svgH * zoom) + 'px';
      canvas.style.transform = `translate(${panX}px, ${panY}px)`;
      label.textContent = Math.round(zoom * 100) + '% — ' + fitMode;
    }
    function canPan() {
      const rW = svgW * zoom, rH = svgH * zoom;
      return rW + config.fitPadding * 2 > viewport.clientWidth || rH + config.fitPadding * 2 > viewport.clientHeight;
    }
    function computeSmartFit() {
      const vpW = viewport.clientWidth, vpH = viewport.clientHeight;
      const aW = Math.max(80, vpW - config.fitPadding * 2), aH = Math.max(80, vpH - config.fitPadding * 2);
      const contain = Math.min(aW / svgW, aH / svgH);
      let z = contain, mode = 'contain';
      if (contain < config.readabilityFloor) {
        const chartR = svgH / svgW, vpR = vpH / Math.max(vpW, 1);
        if (chartR >= vpR) { z = aW / svgW; mode = 'width-priority'; } else { z = aH / svgH; mode = 'height-priority'; }
      }
      return { zoom: clamp(z, config.minZoom, config.maxInitialZoom), mode };
    }
    function fitDiagram() {
      if (!svgW) return;
      const fit = computeSmartFit(); zoom = fit.zoom; fitMode = fit.mode;
      panX = (viewport.clientWidth - svgW * zoom) / 2; panY = (viewport.clientHeight - svgH * zoom) / 2; applyTransform();
    }
    function setOneToOne() {
      zoom = clamp(1, config.minZoom, config.maxZoom); fitMode = '1:1';
      panX = (viewport.clientWidth - svgW * zoom) / 2; panY = (viewport.clientHeight - svgH * zoom) / 2; applyTransform();
    }
    function zoomAround(factor, cx, cy) {
      const next = clamp(zoom * factor, config.minZoom, config.maxZoom), ratio = next / zoom;
      panX = cx - ratio * (cx - panX); panY = cy - ratio * (cy - panY); zoom = next; fitMode = 'custom'; applyTransform();
    }
    function readSvgNaturalSize(svg) {
      let w = 0, h = 0;
      if (svg.viewBox?.baseVal?.width > 0) { w = svg.viewBox.baseVal.width; h = svg.viewBox.baseVal.height; }
      if (!w) { w = parseFloat(svg.getAttribute('width')) || 0; h = parseFloat(svg.getAttribute('height')) || 0; }
      if (!w) { const b = svg.getBBox(); w = b.width; h = b.height; }
      if (!w) { const r = svg.getBoundingClientRect(); w = r.width || 1000; h = r.height || 700; }
      if (!svg.getAttribute('viewBox')) svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      return { w, h };
    }
    function setAdaptiveHeight() {
      if (!svgW) return;
      const usableW = Math.max(280, wrap.getBoundingClientRect().width - 2);
      const idealH = (svgH / svgW) * usableW + config.fitPadding * 2;
      const maxVp = Math.floor(innerHeight * config.maxHeightVh);
      const hardMax = Math.min(config.maxHeightPx, Math.max(config.minHeight + 40, maxVp));
      wrap.style.height = Math.round(clamp(idealH, config.minHeight, hardMax)) + 'px';
    }
    function openInNewTab() {
      const svg = canvas.querySelector('svg'); if (!svg) return;
      const clone = svg.cloneNode(true); clone.style.width = ''; clone.style.height = '';
      const bg = bgColor();
      const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Diagram</title><style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:${bg};padding:40px;box-sizing:border-box}svg{max-width:100%;max-height:90vh;height:auto}</style></head><body>${clone.outerHTML}</body></html>`;
      open(URL.createObjectURL(new Blob([html], { type: 'text/html' })), '_blank');
    }
    async function render() {
      const seq = ++renderSeq;
      try {
        const code = source.textContent.trim();
        if (!code) { label.textContent = 'Error: Empty source'; return; }
        const id = 'd' + seq + '-' + (shells.indexOf(handle) + 1);
        const { svg } = await mermaid.render(id, code);
        if (seq !== renderSeq) return; // a newer re-theme render superseded this one
        canvas.innerHTML = svg;
        const svgNode = canvas.querySelector('svg');
        if (!svgNode) { label.textContent = 'Error: No SVG'; return; }
        const size = readSvgNaturalSize(svgNode); svgW = size.w; svgH = size.h;
        svgNode.removeAttribute('width'); svgNode.removeAttribute('height');
        svgNode.style.maxWidth = 'none'; svgNode.style.display = 'block';
        setAdaptiveHeight(); fitDiagram();
      } catch (err) {
        console.error('Mermaid render failed:', err);
        label.textContent = 'Error: ' + (err.message || 'Render failed');
      }
    }

    const actions = {
      'zoom-in': () => zoomAround(1 + config.zoomStep, viewport.clientWidth / 2, viewport.clientHeight / 2),
      'zoom-out': () => zoomAround(1 / (1 + config.zoomStep), viewport.clientWidth / 2, viewport.clientHeight / 2),
      'zoom-fit': fitDiagram, 'zoom-one': setOneToOne, 'zoom-expand': openInNewTab
    };
    Object.entries(actions).forEach(([action, handler]) => wrap.querySelector(`[data-action="${action}"]`)?.addEventListener('click', handler));
    viewport.addEventListener('dblclick', fitDiagram);
    viewport.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) { e.preventDefault(); const r = viewport.getBoundingClientRect(); const f = e.deltaY < 0 ? 1 + config.zoomStep : 1 / (1 + config.zoomStep); zoomAround(f, e.clientX - r.left, e.clientY - r.top); return; }
      if (canPan()) { e.preventDefault(); panX -= e.deltaX; panY -= e.deltaY; applyTransform(); }
    }, { passive: false });
    viewport.addEventListener('mousedown', (e) => {
      if (e.target.closest('.zoom-controls') || !canPan()) return;
      wrap.classList.add('is-panning'); sx = e.clientX; sy = e.clientY; spx = panX; spy = panY; e.preventDefault();
      activeDrag = { onMove: (ev) => { panX = spx + (ev.clientX - sx); panY = spy + (ev.clientY - sy); applyTransform(); }, onEnd: () => wrap.classList.remove('is-panning') };
    });
    viewport.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; spx = panX; spy = panY; }
      else if (e.touches.length === 2) { const dx = e.touches[0].clientX - e.touches[1].clientX, dy = e.touches[0].clientY - e.touches[1].clientY; touchDist = Math.sqrt(dx*dx+dy*dy); const r = viewport.getBoundingClientRect(); touchCx = (e.touches[0].clientX + e.touches[1].clientX)/2 - r.left; touchCy = (e.touches[0].clientY + e.touches[1].clientY)/2 - r.top; }
    }, { passive: true });
    viewport.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && canPan()) { if (touchDist > 0) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; spx = panX; spy = panY; touchDist = 0; } e.preventDefault(); panX = spx + (e.touches[0].clientX - sx); panY = spy + (e.touches[0].clientY - sy); applyTransform(); }
      else if (e.touches.length === 2 && touchDist > 0) { e.preventDefault(); const dx = e.touches[0].clientX - e.touches[1].clientX, dy = e.touches[0].clientY - e.touches[1].clientY, d = Math.sqrt(dx*dx+dy*dy); zoomAround(d / touchDist, touchCx, touchCy); touchDist = d; }
    }, { passive: false });
    new ResizeObserver(() => { if (svgW) { setAdaptiveHeight(); fitDiagram(); } }).observe(wrap);

    const handle = { render };
    shells.push(handle);
    render();
  }

  document.querySelectorAll('.diagram-shell').forEach(initDiagram);

  // (b) Re-theme on the ◐ toggle: re-init Mermaid with the new palette, re-render every diagram.
  let rt = null;
  new MutationObserver(() => { clearTimeout(rt); rt = setTimeout(() => { initMermaid(); shells.forEach((s) => s.render()); }, 60); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
</script>
```

## Mermaid gotchas (carry these every time)

- **Theme is `'base'` + `themeVariables`, always.** Never another built-in theme — they ignore the palette. The `themeVars()` reader above is the single source of color.
- **`securityLevel:'loose'`** is required so `<br/>` in labels renders as a line break instead of escaped text.
- **Line breaks use `<br/>`, never `\n`.** `\n` renders as literal text. Example: `A["client.ts<br/>resolveApiBase()"]`.
- **Layout direction:** prefer `flowchart TD` (top-down). Use `LR` only for a simple 3–4 node linear flow — it spreads wide and shrinks labels otherwise.
- **`stateDiagram-v2` label parser is strict:** colons, parentheses, `<br/>`, and HTML entities cause silent "Syntax error in text". If a state label needs any of those (`cancel()`, `curate: true`, multi-line), use `flowchart TD` with rounded nodes and quoted edge labels `|"text"|` instead.
- **Never define a page-level `.node` CSS class.** Mermaid uses `.node` internally on `<g>` elements with `transform: translate(...)`; a page-level `.node` rule leaks in and breaks layout. The frozen shell's card class is `.card`, so there is no collision here — just don't add one.
- **Scaling:** ≤8 nodes render fine. 10–12 nodes: bump `fontSize` to 18–20 in `themeVars()` and raise `maxInitialZoom`. **15+ elements: don't scale — use the hybrid pattern** (a ≤8-node Mermaid overview + `.card` detail grid below).
- **ELK layout needs the package** (`@mermaid-js/layout-elk`, imported above). Without `registerLayoutLoaders`, Mermaid silently falls back to dagre — still works, just looser positioning.
- **C4:** use `flowchart TD` + `subgraph` for C4 boundaries, not native `C4Context` (it hard-codes its own colors and ignores `themeVariables`).
