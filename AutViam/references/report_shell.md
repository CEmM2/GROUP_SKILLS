# Report shell — the one page skeleton for all AutViam reports

Every AutViam report (`gen-plan` visual companion, `plan-review`, `diff-review`, `fact-check` banner, `arch`, `explain`) renders as a **single self-contained `.html`** using the **frozen theme** at `templates/report_theme.css`. There is no aesthetic-selection step, no font/palette choice, no `surf` image generation, no slide mode. One theme, always. Read this file once per session when you first build a report.

**Topology is an opt-in module, not a default.** The shell ships no Mermaid machinery — most reports are static and don't need it. When a report genuinely needs a diagram with real edges (a flow, sequence, state machine, data-flow, or an architecture overview), read `references/mermaid_module.md` and paste its three blocks in. It's theme-wired to this shell and re-renders on the ◐ toggle. If what you want is *content in boxes*, use the `.card`/`.cards` and `.tbl-scroll` primitives below instead — reserve Mermaid for *arrows between boxes*.

## Build rules

1. **Inline the theme.** Read `templates/report_theme.css` and paste it verbatim into a `<style>` block in `<head>` (keeps the file self-contained — no external asset except the Google Fonts `@import` already in the theme).
2. **Append the shell CSS** below into the same `<style>` block.
3. **Theme toggle, not theme choice.** The page ships `data-theme="light"`; the ◐ button flips to dark. Both must look intentional — the frozen theme already defines both.
4. **Output location.** Transient reports → `~/.agent/diagrams/<name>.html`. A `gen-plan` companion → next to the plan under `dev/` (e.g. `dev/plans/<slug>-plan.html`). Open it (`open` on macOS) and tell the user the path.
5. **Content is structure, not prose dumps.** Cards, tables, Good/Bad/Ugly grids, pipelines — never paste whole source files. Snippets only, in `<pre>`.
6. **No emoji section-header boxes, no gradient text, no glow** — the theme's badges/labels cover emphasis.

## Shell CSS (append after the frozen theme)

```css
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:var(--font-main); background:var(--bg); color:var(--text); min-height:100vh; transition:background .35s,color .35s; }
.topbar { position:sticky; top:0; z-index:50; background:var(--topbar-bg); color:var(--topbar-text); box-shadow:var(--topbar-shadow); padding:14px 28px; display:flex; align-items:center; gap:16px; }
.topbar h1 { font-size:22px; font-weight:800; }
.topbar .kick { font-size:13px; opacity:.85; font-weight:600; }
.theme-toggle { margin-left:auto; cursor:pointer; border:2px solid var(--topbar-text); background:transparent; color:var(--topbar-text); border-radius:50%; width:38px; height:38px; font-size:18px; }
.tabs { display:flex; gap:10px; padding:18px 28px 0; flex-wrap:wrap; max-width:1180px; margin:0 auto; }
.tab { cursor:pointer; border:var(--card-border-width) solid var(--border); background:var(--bg-surface); color:var(--text); font-family:var(--font-main); font-weight:700; font-size:15px; padding:10px 20px; border-radius:var(--radius) var(--radius) 0 0; box-shadow:var(--card-shadow); }
.tab[aria-selected="true"] { background:var(--accent-bg); color:var(--accent); border-color:var(--accent-border); transform:translateY(-2px); }
.wrap { max-width:1180px; margin:0 auto; padding:24px 28px 80px; }
.panel { display:none; } .panel[data-active="true"] { display:block; }
.lede { font-size:16px; color:var(--text-muted); margin:6px 0 22px; line-height:1.55; }
.card { background:var(--bg-surface); border:var(--card-border-width) solid var(--border); border-radius:var(--radius-card); box-shadow:var(--card-shadow); padding:22px 24px; margin:0 0 22px; }
.card h2 { font-size:20px; font-weight:800; color:var(--text-bright); margin-bottom:4px; }
.card h3 { font-size:16px; font-weight:700; color:var(--text-bright); margin:18px 0 8px; }
.card p { line-height:1.6; margin:8px 0; } .card ul,.card ol { margin:8px 0 8px 22px; line-height:1.65; }
.badge { display:inline-flex; align-items:center; gap:4px; font-size:12px; font-weight:600; padding:3px 10px; border-radius:12px; border:1.5px solid transparent; }
.badge.green{background:var(--green-bg);color:var(--green);border-color:var(--green-border);} .badge.orange{background:var(--orange-bg);color:var(--orange);border-color:var(--orange-border);}
.badge.red{background:var(--diff-del-bg);color:var(--red);border-color:var(--red);} .badge.gray{background:var(--count-bg);color:var(--text-muted);} .badge.accent{background:var(--accent-bg);color:var(--accent);border-color:var(--accent-border);}
.badge.uncertain{background:var(--count-bg);color:var(--text-muted);border:1.5px dashed var(--border);} .badge.new{background:var(--green-bg);color:var(--green);border-color:var(--green-border);} .badge.modified{background:var(--orange-bg);color:var(--orange);border-color:var(--orange-border);}
pre { background:var(--bg-input); border:2px solid var(--border); border-radius:var(--radius); padding:14px 16px; overflow-x:auto; margin:12px 0; font-family:var(--font-mono); font-size:13.5px; line-height:1.55; white-space:pre-wrap; word-break:break-word; }
code.inline { font-family:var(--font-mono); background:var(--pill-bg); border:1px solid var(--border); border-radius:8px; padding:1px 7px; font-size:13px; color:var(--text-bright); }
.tbl-scroll { overflow-x:auto; } table { border-collapse:collapse; width:100%; margin:12px 0; font-size:13.5px; }
th,td { text-align:left; padding:9px 12px; border-bottom:2px solid var(--border); vertical-align:top; min-width:0; overflow-wrap:break-word; }
th { background:var(--bg-elevated); color:var(--text-bright); font-weight:700; } tr:last-child td { border-bottom:none; }
.callout { border-left:5px solid var(--accent); background:var(--accent-bg); border-radius:0 var(--radius) var(--radius) 0; padding:12px 16px; margin:14px 0; }
.callout.warn{border-left-color:var(--orange);background:var(--orange-bg);} .callout.note{border-left-color:var(--green);background:var(--green-bg);} .callout.bad{border-left-color:var(--red);background:var(--diff-del-bg);}
.gbu { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin:12px 0; }
.gbu>div { border:2px solid var(--border); border-radius:var(--radius); padding:10px 14px; min-width:0; }
.gbu .g{border-left:5px solid var(--green);} .gbu .b{border-left:5px solid var(--red);} .gbu .u{border-left:5px solid var(--orange);} .gbu .q{border-left:5px solid var(--accent);}
.gbu h4 { font-size:14px; margin-bottom:4px; color:var(--text-bright); }
.pipe { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; align-items:center; } .arr { color:var(--text-muted); font-weight:800; }
.pstate { font-size:13px; font-weight:700; padding:5px 12px; border-radius:20px; border:2px solid var(--border); background:var(--bg-elevated); }
.tag { font-family:var(--font-mono); font-size:12px; color:var(--text-muted); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; margin:12px 0; }
```

`.cards` is a responsive card grid (used by `arch` for per-module detail and by any report with N sibling cards). `.badge.uncertain` (dashed) marks a fact-check-spine item that couldn't be grounded; `.badge.new` / `.badge.modified` tag feature deltas. For *uncertain edges* inside a Mermaid diagram, use the dashed-arrow syntax (`-.->`), not a badge.

## HTML skeleton

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{title}}</title>
<style>/* 1) paste templates/report_theme.css   2) paste the shell CSS above */</style>
</head>
<body>
<div class="topbar">
  <div><h1>{{title}}</h1><div class="kick">{{subtitle}}</div></div>
  <button class="theme-toggle" aria-label="toggle theme"
    onclick="(function(r){var n=r.getAttribute('data-theme')==='light'?'dark':'light';r.setAttribute('data-theme',n);})(document.documentElement)">◐</button>
</div>
<!-- Optional tabs (only for multi-section reviews). Single-section reports skip tabs and use plain .card sections. -->
<div class="wrap">
  <!-- .card / .tbl-scroll table / .gbu / .callout sections here -->
</div>
<!-- Include only if you used tabs: -->
<script>
function showTab(i, btn){
  document.querySelectorAll('.panel').forEach((p,j)=>p.setAttribute('data-active', j===i?'true':'false'));
  document.querySelectorAll('.tab').forEach(t=>t.setAttribute('aria-selected','false'));
  btn.setAttribute('aria-selected','true'); window.scrollTo({top:0,behavior:'smooth'});
}
</script>
</body>
</html>
```

## Good/Bad/Ugly block (shared by plan-review & diff-review)

```html
<div class="gbu">
  <div class="g"><h4>Good</h4>…</div>
  <div class="b"><h4>Bad</h4>…</div>
  <div class="u"><h4>Ugly</h4>…</div>
  <div class="q"><h4>Questions</h4>…</div>
</div>
```
If a category is empty, render "None found" — never omit it.
