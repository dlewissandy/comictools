"""
THE LIGHT TABLE: compose a panel's take from acetate layers, stacked in
comic-craft order — letters over foreground over figures over background.
The right side shows THE ROUGH: a live penciller's mock assembled from the
parts.  Toggle a layer's eye to lift its acetate off the table; slide a
figure left/center/right to block the shot; then INK the rough — the
composition goes to the coauthor to render as a real take.
"""
import os

from nicegui import ui

from gui.messaging import post_user_message
from gui.state import APPState
from schema import CharacterModel, ComicStyle, FrameLayout, Setting, PropAsset, CharacterVariant
from schema.character_reference import CharacterRef
from schema.setting import Prop

_ASPECT = {"landscape": "3/2", "portrait": "2/3", "square": "1/1"}

# Drag a figure to block the shot; scroll on it to scale for parallax.
# One global handler (self-guarded) serves every rough; main.py ships it
# in the page head (head HTML cannot be added after the page loads).
DRAG_JS = """
<script>
if (!window._roughDragInit) {
  window._roughDragInit = true;

  // hit-test through TRANSPARENT pixels: the figure you SEE is the one you grab
  function alphaAt(fig, cx, cy) {
    const img = fig.querySelector('img');
    if (!img || !img.naturalWidth) return 255;
    const r = fig.getBoundingClientRect();
    const scale = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight);
    const w = img.naturalWidth * scale, h = img.naturalHeight * scale;
    const ox = r.left + (r.width - w) / 2, oy = r.top + (r.height - h) / 2;
    let x = (cx - ox) / scale;
    const y = (cy - oy) / scale;
    if (fig.dataset.flip) x = img.naturalWidth - x;
    if (x < 0 || y < 0 || x >= img.naturalWidth || y >= img.naturalHeight) return 0;
    const c = window._roughHit || (window._roughHit = document.createElement('canvas'));
    c.width = 1; c.height = 1;
    const ctx = c.getContext('2d', {willReadFrequently: true});
    ctx.clearRect(0, 0, 1, 1);
    try {
      ctx.drawImage(img, x, y, 1, 1, 0, 0, 1, 1);
      return ctx.getImageData(0, 0, 1, 1).data[3];
    } catch (err) { return 255; }
  }

  function setH(fig, h) {
    fig.style.height = h + '%';
    const k = parseFloat(fig.dataset.war);
    if (k) fig.style.width = (h * k) + '%';
  }

  function pickFigure(e) {
    const cands = [...new Set(document.elementsFromPoint(e.clientX, e.clientY)
      .map(el => el.closest('.rough-drag')).filter(Boolean))];
    for (const f of cands) {
      const canvas = f.closest('.rough-canvas');
      if (canvas && canvas.dataset.locked) continue;   // the table is locked
      if (window._lineDead) continue;                  // moves can't save — don't fake it
      if (f.dataset.lock) continue;                    // this acetate is pinned
      if (alphaAt(f, e.clientX, e.clientY) > 20) return f;
    }
    return null;
  }

  // TAILS: real vector tails drawn on an SVG overlay, tip draggable
  const SVGNS = 'http://www.w3.org/2000/svg';
  function tailSvg(canvas) {
    let svg = canvas.querySelector('.rough-tails');
    if (!svg) {
      svg = document.createElementNS(SVGNS, 'svg');
      svg.setAttribute('class', 'rough-tails');
      canvas.appendChild(svg);
    }
    return svg;
  }
  window.roughDrawTails = function () {
    // LETTERS PRINT WHAT YOU BLOCK: a letter's size is stored in REFERENCE
    // units (px on a 520px-tall canvas — the compositor's own ruler), and
    // the on-screen font is derived from the live canvas height, so the
    // rough shows the print's true proportions at any pane width
    document.querySelectorAll('.rough-drag[data-scale="font"]').forEach((el) => {
      const c = el.closest('.rough-canvas');
      if (!c) return;
      const ch = c.getBoundingClientRect().height;
      if (!ch) return;
      const want = (parseFloat(el.dataset.fs) || 11) / 520 * ch;
      if (Math.abs((parseFloat(el.style.fontSize) || 0) - want) > 0.5) {
        el.style.fontSize = want + 'px';
      }
    });
    document.querySelectorAll('.rough-canvas').forEach((canvas) => {
      const svg = tailSvg(canvas);
      const cr = canvas.getBoundingClientRect();
      svg.setAttribute('viewBox', `0 0 ${cr.width} ${cr.height}`);
      svg.innerHTML = '';
      canvas.querySelectorAll('[data-kind="balloon"]').forEach((fig) => {
        if (fig.classList.contains('rough-balloon--sound-effect')) return;
        const br = fig.getBoundingClientRect();
        const bx = br.left + br.width / 2 - cr.left;
        const by = br.top + br.height / 2 - cr.top;
        const tx = (parseFloat(fig.dataset.tx) || 50) / 100 * cr.width;
        const ty = cr.height - (parseFloat(fig.dataset.ty) || 0) / 100 * cr.height;
        const dx = tx - bx, dy = ty - by;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len, uy = dy / len;
        // base: where the center->tip ray leaves the balloon's box
        const hw = br.width / 2, hh = br.height / 2;
        const t = 1 / Math.max(Math.abs(ux) / hw, Math.abs(uy) / hh);
        const ex = bx + ux * t * 0.92, ey = by + uy * t * 0.92;
        const px = -uy, py = ux;   // perpendicular
        if (fig.classList.contains('rough-balloon--thought')) {
          for (const [f, r] of [[0.3, 6], [0.58, 4.5], [0.82, 3]]) {
            const c = document.createElementNS(SVGNS, 'circle');
            c.setAttribute('cx', ex + (tx - ex) * f);
            c.setAttribute('cy', ey + (ty - ey) * f);
            c.setAttribute('r', r);
            c.setAttribute('class', 'rough-tail-shape');
            svg.appendChild(c);
          }
        } else {
          const w = Math.min(12, br.width / 4);
          const poly = document.createElementNS(SVGNS, 'polygon');
          poly.setAttribute('points',
            `${ex + px * w},${ey + py * w} ${ex - px * w},${ey - py * w} ${tx},${ty}`);
          poly.setAttribute('class', 'rough-tail-shape');
          svg.appendChild(poly);
        }
        if (window._roughSel === fig) {
          const tip = document.createElementNS(SVGNS, 'circle');
          tip.setAttribute('cx', tx);
          tip.setAttribute('cy', ty);
          tip.setAttribute('r', 7);
          tip.setAttribute('class', 'rh-tip');
          tip.dataset.for = fig.dataset.key;
          svg.appendChild(tip);
        }
      });
    });
  };
  const startTailObserver = () => new MutationObserver((muts) => {
      // tails redraw mutates its own SVG — never let that re-trigger us
      if (muts.every(m => m.target.closest && m.target.closest('.rough-tails'))) return;
      requestAnimationFrame(window.roughDrawTails);
    }).observe(document.body, {childList: true, subtree: true});
  if (document.body) startTailObserver();
  else document.addEventListener('DOMContentLoaded', startTailObserver);
  // pane resizes change the canvas height — letters re-derive their size
  window.addEventListener('resize', () => requestAnimationFrame(window.roughDrawTails));

  // SELECTION: border + corner grab handles, the familiar canvas metaphor
  function flushNudge() {
    // pending debounced writes (nudge + wheel) must land BEFORE anything
    // else happens — a button click writes the board and would clobber them
    if (window._nudgeT) { clearTimeout(window._nudgeT); window._nudgeT = null; }
    const p = window._nudgePending;
    window._nudgePending = null;
    if (p) report(p.f, p.c);
    if (window._wheelT) { clearTimeout(window._wheelT); window._wheelT = null; }
    const w = window._wheelPending;
    window._wheelPending = null;
    if (w) report(w.f, w.c);
  }
  function deselect() {
    flushNudge();
    document.querySelectorAll('.rough-sel-box').forEach(b => b.remove());
    document.querySelectorAll('.stack-row--sel').forEach(r => r.classList.remove('stack-row--sel'));
    window._roughSel = null;
  }
  function select(fig) {
    if (window._roughSel === fig) return;
    deselect();
    const box = document.createElement('div');
    box.className = 'rough-sel-box';
    for (const c of ['nw', 'ne', 'sw', 'se']) {
      const h = document.createElement('div');
      h.className = 'rh rh-' + c;
      box.appendChild(h);
    }
    fig.appendChild(box);
    window._roughSel = fig;
    // ONE SELECTION: the acetate and its stack row are the same thing —
    // selecting on the rough lights the row.  (No scrolling here: this runs
    // inside pointerdown, and moving the pane under the cursor breaks the
    // drag that is about to start.)
    const key = fig.dataset.key;
    document.querySelectorAll('.stack-row').forEach(r =>
      r.classList.toggle('stack-row--sel', r.dataset.key === key));
    // FIRST SELECTION teaches the hand: a placard at the moment of use.
    // If a repaint tears it down before it could be read, offer it again.
    if (!window._tableTaught) {
      window._tableTaught = true;
      const canvas = fig.closest('.rough-canvas');
      if (canvas) {
        const p = document.createElement('div');
        p.className = 'rough-placard';
        p.textContent = 'drag to move (snaps to thirds — Shift skips) · arrows nudge · ⌘-wheel resizes · [ ] or Alt-wheel tilts · ⌘Z takes it back · Esc lets go';
        canvas.appendChild(p);
        const born = performance.now();
        const tick = setInterval(() => {
          if (!p.isConnected) {
            clearInterval(tick);
            if (performance.now() - born < 3500) window._tableTaught = false;
            return;
          }
          if (performance.now() - born > 8000) { clearInterval(tick); p.remove(); }
        }, 500);
      }
    }
    requestAnimationFrame(window.roughDrawTails);
  }
  // ...and picking a row selects its acetate on the rough (two-way mirror)
  document.addEventListener('click', (e) => {
    const row = e.target.closest('.stack-row');
    if (!row || window._lineDead) return;
    if (e.target.closest('button, .q-btn, input, .q-menu, .q-dialog, .light-thumb')) return;
    const key = row.dataset.key;
    if (!key) return;
    const fig = document.querySelector(`.rough-drag[data-key="${CSS.escape(key)}"]`);
    if (fig && !fig.classList.contains('rough-locked')) {
      select(fig);
    } else {
      // nothing on the rough for this row (unposed / lifted / a group):
      // light the row alone so the selection is still visibly answered —
      // and on touch, this is what unfolds the row's tools
      document.querySelectorAll('.stack-row--sel').forEach(r => r.classList.remove('stack-row--sel'));
      row.classList.add('stack-row--sel');
    }
  });

  let drag = null;
  let resize = null;
  let tailDrag = null;

  // THE LINE-DEAD GUARD: if the studio's connection drops, table edits
  // would move pixels but save NOTHING — so the table freezes and says so,
  // instead of letting work silently evaporate until the next reload.
  window._lineDead = false;
  function watchLine() {
    const s = window.socket;
    if (!s || !s.on) { setTimeout(watchLine, 1000); return; }
    s.on('disconnect', () => {
      window._lineDead = true;
      document.querySelectorAll('.rough-canvas').forEach(c => c.classList.add('rough-line-dead'));
    });
    s.on('connect', () => {
      if (!window._lineDead) return;
      // a reconnect after death means a NEW server — this page is stale
      document.querySelectorAll('.rough-line-dead').forEach(c => c.dataset.deadReload = '1');
      setTimeout(() => location.reload(), 1200);
    });
  }
  if (document.readyState === 'complete') watchLine();
  else window.addEventListener('load', watchLine);

  // MOVE-UNDO: a ring of before-states; Cmd/Ctrl+Z walks it back
  window._roughUndo = window._roughUndo || [];
  function pushUndo(fig, canvas) {
    window._roughUndo.push({fig, canvas, left: fig.style.left, bottom: fig.style.bottom,
                            height: fig.style.height, width: fig.style.width,
                            fontSize: fig.style.fontSize, rot: fig.dataset.rot || '',
                            tx: fig.dataset.tx, ty: fig.dataset.ty});
    if (window._roughUndo.length > 60) window._roughUndo.shift();
  }
  function applyTransform(fig) {
    const deg = parseFloat(fig.dataset.rot) || 0;
    const flip = fig.dataset.flip ? ' scaleX(-1)' : '';
    const base = fig.dataset.scale === 'font' ? '' : 'translateX(-50%)';
    fig.style.transform = base + flip + (deg ? ` rotate(${deg}deg)` : '');
  }
  document.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;               // primary button only
    if (e.target.isContentEditable) return;   // typing, not dragging
    if (e.target.classList && e.target.classList.contains('rh-tip')) {
      const key = e.target.dataset.for;
      const canvas = e.target.closest('.rough-canvas');
      const fig = canvas.querySelector(`[data-key="${CSS.escape(key)}"]`);
      e.preventDefault();
      pushUndo(fig, canvas);
      tailDrag = {fig, canvas};
      return;
    }
    const handle = e.target.closest('.rh');
    if (handle) {
      const fig = handle.closest('.rough-drag');
      const r = fig.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      e.preventDefault();
      pushUndo(fig, fig.closest('.rough-canvas'));
      resize = {fig, canvas: fig.closest('.rough-canvas'), cx, cy,
                d0: Math.hypot(e.clientX - cx, e.clientY - cy),
                h0: parseFloat(fig.style.height) || 0,
                f0: parseFloat(fig.style.fontSize) || 11};
      return;
    }
    const fig = pickFigure(e);
    if (!fig) {
      // no acetate under the point — but an UNPOSED SILHOUETTE may be
      // there, click-shadowed by a transparent bounding box above it;
      // hand the click to it so click-to-pose always answers
      const silHit = document.elementsFromPoint(e.clientX, e.clientY)
        .map(el => el.closest && el.closest('.rough-silhouette')).find(Boolean);
      if (silHit && !(e.target.closest && e.target.closest('.rough-silhouette'))) {
        silHit.dispatchEvent(new MouseEvent('click', {bubbles: true}));
      }
      deselect();
      return;
    }
    const canvas = fig.closest('.rough-canvas');
    if (!canvas) return;
    e.preventDefault();
    select(fig);
    // grab offset: you drag from where you GRABBED, the figure doesn't
    // teleport its center to the cursor; a ~3px threshold keeps clicks
    // (and double-click jitter) from displacing anything at all
    const r0 = canvas.getBoundingClientRect();
    const hh0 = parseFloat(fig.style.height);
    const cx0 = ((e.clientX - r0.left) / r0.width) * 100;
    const cy0 = ((r0.bottom - e.clientY) / r0.height) * 100 - (isNaN(hh0) ? 2 : hh0 / 2);
    const l0 = parseFloat(fig.style.left);   // 0 is a legal position — no || here
    const b0 = parseFloat(fig.style.bottom);
    drag = {fig, canvas, z: fig.style.zIndex, sx: e.clientX, sy: e.clientY,
            offX: (isNaN(l0) ? 50 : l0) - cx0,
            offY: (isNaN(b0) ? 0 : b0) - cy0, live: false};
  });
  document.addEventListener('pointermove', (e) => {
    if (tailDrag) {
      const r = tailDrag.canvas.getBoundingClientRect();
      const tx = Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100));
      const ty = Math.max(-10, Math.min(100, ((r.bottom - e.clientY) / r.height) * 100));
      tailDrag.fig.dataset.tx = tx.toFixed(1);
      tailDrag.fig.dataset.ty = ty.toFixed(1);
      window.roughDrawTails();
      return;
    }
    if (resize) {
      const factor = Math.max(0.1, Math.hypot(e.clientX - resize.cx, e.clientY - resize.cy) / (resize.d0 || 1));
      if (resize.fig.dataset.scale === 'font') {
        const c = resize.fig.closest('.rough-canvas');
        const ch = (c ? c.getBoundingClientRect().height : 0) || 520;
        let ref = Math.max(6, Math.min(34, (resize.f0 * factor) * 520 / ch));
        resize.fig.dataset.fs = ref;
        resize.fig.style.fontSize = (ref / 520 * ch) + 'px';
      } else {
        setH(resize.fig, Math.max(15, Math.min(140, resize.h0 * factor)));
      }
      return;
    }
    if (!drag) return;
    if (!drag.live) {
      if (Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) < 3) return;
      drag.live = true;
      pushUndo(drag.fig, drag.canvas);
      drag.fig.style.zIndex = 99;  // ride above the stack while dragging
    }
    const r = drag.canvas.getBoundingClientRect();
    const hh = parseFloat(drag.fig.style.height);
    let x = ((e.clientX - r.left) / r.width) * 100 + drag.offX;
    let y = ((r.bottom - e.clientY) / r.height) * 100 - (isNaN(hh) ? 2 : hh / 2) + drag.offY;
    x = Math.max(-20, Math.min(120, x));
    y = Math.max(-80, Math.min(95, y));   // negative: peek up from below the frame
    // SNAP: center and thirds pull gently (the baseline too) — Shift opts out
    if (!e.shiftKey) {
      for (const s of [100 / 3, 50, 200 / 3]) {
        if (Math.abs(x - s) < 1.5) { x = s; break; }
      }
      if (Math.abs(y) < 1.5) y = 0;
    }
    drag.fig.style.left = x + '%';
    drag.fig.style.bottom = y + '%';
    drag.fig.style.top = 'auto';
    if (drag.fig.dataset.kind === 'balloon') window.roughDrawTails();
  });
  const report = (fig, canvas) => emitEvent('rough_block', {
      key: fig.dataset.key, series: canvas.dataset.series, issue: canvas.dataset.issue,
      scene: canvas.dataset.scene, panel: canvas.dataset.panel, cover: canvas.dataset.cover,
      insert: canvas.dataset.insert,
      x: parseFloat(fig.style.left), y: parseFloat(fig.style.bottom) || 0,
      h: parseFloat(fig.style.height) || 0,
      fs: fig.dataset.scale === 'font'
          ? Math.round((parseFloat(fig.dataset.fs) || 11) * 10) / 10 : 0,
      tx: parseFloat(fig.dataset.tx) || 0,
      ty: parseFloat(fig.dataset.ty) || 0,
      rot: parseFloat(fig.dataset.rot) || 0});
  document.addEventListener('pointerup', (e) => {
    if (tailDrag) {
      report(tailDrag.fig, tailDrag.canvas);
      tailDrag = null;
      return;
    }
    if (resize) {
      report(resize.fig, resize.canvas);
      resize = null;
      return;
    }
    if (!drag) return;
    drag.fig.style.zIndex = drag.z;
    if (drag.live) report(drag.fig, drag.canvas);  // a mere click moves nothing
    drag = null;
  });
  document.addEventListener('pointercancel', () => {
    if (drag) drag.fig.style.zIndex = drag.z;
    drag = resize = tailDrag = null;
  });
  document.addEventListener('wheel', (e) => {
    // PLAIN WHEEL ALWAYS SCROLLS THE PAGE.  Resizing takes a held modifier
    // (Ctrl/Cmd+wheel) and tilting takes Alt+wheel, on the SELECTED acetate
    // — after a drag the figure stays selected, and a bare scroll must
    // never reshape it on the way past.
    if (!e.ctrlKey && !e.metaKey && !e.altKey) return;
    const fig = pickFigure(e);
    if (!fig) return;
    if (window._roughSel !== fig) return;
    e.preventDefault();
    const canvas = fig.closest('.rough-canvas');
    if (e.altKey && fig.dataset.scale !== 'font') {
      // Alt+wheel TILTS the selected acetate; letters stay upright
      if (!window._wheelPending || window._wheelPending.f !== fig) pushUndo(fig, canvas);
      let deg = (parseFloat(fig.dataset.rot) || 0) + (e.deltaY < 0 ? 3 : -3);
      deg = Math.max(-180, Math.min(180, Math.round(deg)));
      fig.dataset.rot = deg;
      applyTransform(fig);
    } else if (fig.dataset.scale === 'font') {
      // size in REFERENCE units so the clamp means the same at any pane width
      const ch = canvas.getBoundingClientRect().height || 520;
      let ref = parseFloat(fig.dataset.fs)
                || (parseFloat(fig.style.fontSize) || 11) * 520 / ch;
      ref = Math.max(6, Math.min(34, ref * (e.deltaY < 0 ? 1.08 : 0.92)));
      fig.dataset.fs = ref;
      fig.style.fontSize = (ref / 520 * ch) + 'px';
    } else {
      let h = parseFloat(fig.style.height) || 50;
      h = Math.max(15, Math.min(140, h * (e.deltaY < 0 ? 1.06 : 0.94)));
      setH(fig, h);
    }
    // persist once the change settles — not one write per wheel tick; a
    // pending write for ANOTHER figure flushes first, never gets dropped
    const pend = window._wheelPending;
    if (pend && pend.f !== fig) {
      clearTimeout(window._wheelT);
      report(pend.f, pend.c);
    }
    window._wheelPending = {f: fig, c: canvas};
    clearTimeout(window._wheelT);
    window._wheelT = setTimeout(() => { window._wheelPending = null; report(fig, canvas); }, 300);
  }, {passive: false});
  // STACK REORDER: drag rows; the stack order IS the z-order
  let stackDrag = null;
  document.addEventListener('dragstart', (e) => {
    const row = e.target.closest('.stack-row');
    if (!row) return;
    stackDrag = row;
    e.dataTransfer.effectAllowed = 'move';
  });
  const clearDropMarks = () => document.querySelectorAll('.stack-drop-onto, .stack-drop-above, .stack-drop-below')
      .forEach(r => r.classList.remove('stack-drop-onto', 'stack-drop-above', 'stack-drop-below'));
  const dropMode = (e, row) => {
    const r = row.getBoundingClientRect();
    const frac = (e.clientY - r.top) / r.height;
    return frac < 0.3 ? 'before' : (frac > 0.7 ? 'after' : 'onto');
  };
  document.addEventListener('dragover', (e) => {
    if (!stackDrag) return;
    const row = e.target.closest('.stack-row');
    clearDropMarks();
    if (row && row !== stackDrag) {
      e.preventDefault();
      const mode = dropMode(e, row);
      row.classList.add(mode === 'onto' ? 'stack-drop-onto'
                        : (mode === 'before' ? 'stack-drop-above' : 'stack-drop-below'));
    }
  });
  document.addEventListener('drop', (e) => {
    clearDropMarks();
    if (!stackDrag) return;
    const row = e.target.closest('.stack-row');
    const src = stackDrag;
    stackDrag = null;
    if (!row || row === src) return;
    e.preventDefault();
    const stack = row.closest('.acetate-stack');
    if (!stack) return;
    emitEvent('stack_reorder', {
      src: src.dataset.key, dst: row.dataset.key, mode: dropMode(e, row),
      series: stack.dataset.series, issue: stack.dataset.issue,
      scene: stack.dataset.scene, panel: stack.dataset.panel, cover: stack.dataset.cover,
      insert: stack.dataset.insert});
  });
  document.addEventListener('dragend', () => {
    clearDropMarks();
    stackDrag = null;
  });

  // ARROW KEYS nudge the selected acetate (Shift = coarse); Escape deselects
  document.addEventListener('keydown', (e) => {
    if (e.target.isContentEditable || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
      // walk the move-undo ring back (skipping acetates from torn-down views)
      let st;
      while ((st = window._roughUndo.pop())) {
        if (document.contains(st.fig)) break;
      }
      if (!st) return;
      e.preventDefault();
      st.fig.style.left = st.left; st.fig.style.bottom = st.bottom;
      if (st.height) st.fig.style.height = st.height;
      if (st.width) st.fig.style.width = st.width;
      if (st.fontSize) {
        st.fig.style.fontSize = st.fontSize;
        const c = st.fig.closest('.rough-canvas');
        if (c) st.fig.dataset.fs = parseFloat(st.fontSize) * 520
                                   / (c.getBoundingClientRect().height || 520);
      }
      if (st.tx !== undefined) st.fig.dataset.tx = st.tx;
      if (st.ty !== undefined) st.fig.dataset.ty = st.ty;
      st.fig.dataset.rot = st.rot || '';
      applyTransform(st.fig);
      requestAnimationFrame(window.roughDrawTails);
      report(st.fig, st.canvas);
      return;
    }
    // Escape lets go of ANY selection — including a row-only highlight
    // (an unposed or lifted figure) where no acetate holds _roughSel
    if (e.key === 'Escape') { deselect(); requestAnimationFrame(window.roughDrawTails); return; }
    const fig = window._roughSel;
    if (!fig) return;
    if (fig.dataset.lock) return;                      // pinned: it stays put
    if ((e.key === '[' || e.key === ']') && fig.dataset.scale !== 'font') {
      // [ and ] TILT the selected acetate (Shift = coarse)
      e.preventDefault();
      if (!window._nudgePending || window._nudgePending.f !== fig) {
        pushUndo(fig, fig.closest('.rough-canvas'));
      }
      const d = (e.key === ']' ? 1 : -1) * (e.shiftKey ? 15 : 5);
      let deg = (parseFloat(fig.dataset.rot) || 0) + d;
      fig.dataset.rot = Math.max(-180, Math.min(180, deg));
      applyTransform(fig);
      const canvas = fig.closest('.rough-canvas');
      window._nudgePending = {f: fig, c: canvas};
      clearTimeout(window._nudgeT);
      window._nudgeT = setTimeout(() => { window._nudgePending = null; report(fig, canvas); }, 400);
      return;
    }
    const step = e.shiftKey ? 5 : 1;
    let dx = 0, dy = 0;
    if (e.key === 'ArrowLeft') dx = -step;
    else if (e.key === 'ArrowRight') dx = step;
    else if (e.key === 'ArrowUp') dy = step;
    else if (e.key === 'ArrowDown') dy = -step;
    else return;
    const canvas = fig.closest('.rough-canvas');
    if (!canvas || canvas.dataset.locked) return;
    e.preventDefault();
    if (!window._nudgePending || window._nudgePending.f !== fig) pushUndo(fig, canvas);
    fig.style.left = (Math.max(-20, Math.min(120, (parseFloat(fig.style.left) || 50) + dx))) + '%';
    fig.style.bottom = (Math.max(-80, Math.min(95, (parseFloat(fig.style.bottom) || 0) + dy))) + '%';
    fig.style.top = 'auto';
    if (fig.dataset.kind === 'balloon') window.roughDrawTails();
    // persist once the nudging settles; a selection switch flushes it
    window._nudgePending = {f: fig, c: canvas};
    clearTimeout(window._nudgeT);
    window._nudgeT = setTimeout(() => { window._nudgePending = null; report(fig, canvas); }, 400);
  });

  // FILE DROPS: the app owns them.  A drop ON an upload box is handed
  // straight to that box's hidden input (Quasar's own dnd path never fires
  // here); a missed drop is swallowed so the browser never navigates away.
  document.addEventListener('dragover', (e) => {
    const t = e.dataTransfer && e.dataTransfer.types;
    if (!(t && Array.prototype.includes.call(t, 'Files'))) return;
    e.preventDefault();
    document.querySelectorAll('.drop-ready').forEach(z => z.classList.remove('drop-ready'));
    const zone = e.target.closest && e.target.closest('.q-uploader');
    if (zone) zone.classList.add('drop-ready');
  });
  document.addEventListener('dragleave', (e) => {
    const zone = e.target.closest && e.target.closest('.q-uploader');
    if (zone) zone.classList.remove('drop-ready');
  });
  document.addEventListener('drop', (e) => {
    if (!(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) return;
    e.preventDefault();
    document.querySelectorAll('.drop-ready').forEach(z => z.classList.remove('drop-ready'));
    const zone = e.target.closest && e.target.closest('.q-uploader');
    if (!zone) return;
    const input = zone.querySelector('input[type=file]');
    if (!input) return;
    const dt = new DataTransfer();
    for (const f of e.dataTransfer.files) dt.items.add(f);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', {bubbles: true}));
  });

  // PASTE AN IMAGE from the clipboard — lands like a drop, wherever you are
  document.addEventListener('paste', (e) => {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const it of items) {
      if (it.type && it.type.startsWith('image/')) {
        const f = it.getAsFile();
        if (!f) continue;
        e.preventDefault();
        const r = new FileReader();
        r.onload = () => emitEvent('clipboard_image', {data: r.result, mime: it.type});
        r.readAsDataURL(f);
        return;
      }
    }
  });

  // double-click a balloon or caption: edit the words IN PLACE
  document.addEventListener('dblclick', (e) => {
    const fig = e.target.closest('.rough-drag');
    if (!fig || !fig.dataset.kind || fig.dataset.kind === 'figure') return;
    const canvas = fig.closest('.rough-canvas');
    if (canvas && canvas.dataset.locked) return;   // the table is locked
    e.preventDefault();
    fig.contentEditable = 'true';
    fig.classList.add('rough-editing');
    fig.focus();
    try { document.execCommand('selectAll', false, null); } catch (err) {}
  });
  function commitEdit(fig) {
    if (fig.contentEditable !== 'true') return;
    fig.contentEditable = 'false';
    fig.classList.remove('rough-editing');
    const canvas = fig.closest('.rough-canvas');
    emitEvent('rough_text', {
      key: fig.dataset.key, series: canvas.dataset.series, issue: canvas.dataset.issue,
      scene: canvas.dataset.scene, panel: canvas.dataset.panel, cover: canvas.dataset.cover,
      insert: canvas.dataset.insert,
      text: fig.innerText.trim()});
  }
  document.addEventListener('focusout', (e) => {
    const f = e.target && e.target.closest ? e.target.closest('.rough-drag') : null;
    if (f) commitEdit(f);
  }, true);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.isContentEditable && e.target.closest('.rough-drag')) {
      e.preventDefault();
      e.target.blur();
    }
  });
}
</script>
"""


def _src(path: str) -> str:
    """Serve a table image via /data with an mtime cache-buster, so the rough
    always shows the CURRENT file (browsers cling to overwritten paths)."""
    try:
        v = int(os.path.getmtime(path))
    except OSError:
        return path
    p = path.replace(os.sep, '/')
    return f"/{p}?v={v}" if p.startswith('data/') else path


_AR_CACHE: dict = {}


def _img_ar(path: str) -> float:
    """An image's width/height ratio, cached by (path, mtime) — the rough
    redraws often and shouldn't reopen every acetate each time."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return 2 / 3
    v = _AR_CACHE.get(key)
    if v is None:
        try:
            from PIL import Image as _I
            with _I.open(path) as im:
                v = im.width / im.height
        except Exception:
            v = 2 / 3
        if len(_AR_CACHE) > 512:
            _AR_CACHE.clear()
        _AR_CACHE[key] = v
    return v


# ---------------------------------------------------------------------------
# BOARDS: anything composed on the light table.  A PANEL composes on top of
# its scene (style/setting/props live there); a COVER is its own scene — it
# owns style_id and setting_id directly, so it rides the table as both the
# subject AND the scene-role.
# ---------------------------------------------------------------------------
def is_cover(board) -> bool:
    return hasattr(board, 'cover_id')


def is_insert(board) -> bool:
    """A full-page insert (poster, ad, pin-up, the mailbag) — its own scene,
    like a cover: it owns style_id and setting_id and rides the table as
    both the subject and the scene-role."""
    return hasattr(board, 'insert_id')


def apply_stack_reorder(p, src_k: str, dst_k: str, mode: str = 'before') -> None:
    """THE STACK IS THE Z-ORDER.  Apply one drag of the acetate stack to the
    board in place: 'onto' nests into (or forms) a group, 'before'/'after'
    restack; groups move as blocks; dragging the last member out dissolves
    its group; undraggable members (the split plate) stay in their groups.
    Pure board-in/board-out — the caller persists."""
    fig_keys = [f"{r.character_id}/{r.variant_id}" for r in (p.character_references or [])]
    # the display defaults z to the cast index — the reorder baseline
    # must match or the first restack inverts the un-dragged stack
    cast_default_z = {k: i for i, k in enumerate(fig_keys)}
    fig_keys += [k for k in sorted(p.figure_images or {}) if k.startswith('element/')]

    def z(k):
        b = (p.figure_blocking or {}).get(k) or {}
        if 'z' in b:
            return b['z']
        return cast_default_z.get(k, 40)

    def disp(k):
        return (k.split('/', 1)[1] if k.startswith('element/') else k.split('/')[0]).replace('-', ' ')

    # non-figure members (the split plate) can't be dragged but must
    # never be stripped from their group by a restack
    extras = {n: [k for k in ks if k not in fig_keys]
              for n, ks in (p.layer_groups or {}).items()}
    groups = {n: sorted([k for k in ks if k in fig_keys], key=lambda k: -z(k))
              for n, ks in (p.layer_groups or {}).items()}
    groups = {n: ks for n, ks in groups.items() if ks}
    parent = {k: n for n, ks in groups.items() for k in ks}

    # top-level sequence: ('g', name) and ('l', key), by current z
    entries = [('g', n, max(z(k) for k in ks)) for n, ks in groups.items()]
    entries += [('l', k, z(k)) for k in fig_keys if k not in parent]
    entries.sort(key=lambda t: -t[2])
    seq = [(t, i) for t, i, _ in entries]

    def remove_src():
        nonlocal seq
        if src_k.startswith('group:'):
            name = src_k[6:]
            seq = [b for b in seq if b != ('g', name)]
            return ('g', name)
        if src_k in parent:
            groups[parent[src_k]].remove(src_k)
            if not groups[parent[src_k]]:
                gname = parent[src_k]
                groups.pop(gname)
                seq = [b for b in seq if b != ('g', gname)]
        else:
            seq = [b for b in seq if b != ('l', src_k)]
        return ('l', src_k)

    if mode == 'onto':
        kind_, name_ = remove_src()
        moving = groups.pop(name_) if kind_ == 'g' else [src_k]
        if kind_ == 'g':
            seq = [b for b in seq if b != ('g', name_)]
        if dst_k.startswith('group:'):
            tname = dst_k[6:]
        elif dst_k in parent and parent[dst_k] in groups:
            tname = parent[dst_k]
        else:
            tname = disp(dst_k)
            while tname in groups:
                tname += ' •'
            groups[tname] = [dst_k]
            seq = [('g', tname) if b == ('l', dst_k) else b for b in seq]
        if tname in groups:
            tgt = groups[tname]
            at = tgt.index(dst_k) + 1 if dst_k in tgt else 0
            for m in moving:
                if m not in tgt:
                    tgt.insert(at, m)
                    at += 1
            if ('g', tname) not in seq:
                seq.append(('g', tname))
    else:
        kind_, name_ = remove_src()
        block = ('g', name_) if kind_ == 'g' else ('l', src_k)
        offset = 0 if mode == 'before' else 1
        if kind_ == 'l' and not dst_k.startswith('group:') and dst_k in parent and parent[dst_k] in groups:
            # between members: inherit the target's group
            ms = groups[parent[dst_k]]
            ms.insert(ms.index(dst_k) + offset, src_k)
        else:
            anchor = ('g', dst_k[6:]) if dst_k.startswith('group:') else \
                     (('g', parent[dst_k]) if dst_k in parent else ('l', dst_k))
            idx = seq.index(anchor) if anchor in seq else len(seq)
            seq.insert(idx + offset, block)

    # persist: groups + z from the flattened display order, with the
    # undraggable members (the plate) merged back into their groups
    merged = {}
    for n in list(groups) + [n for n, ex in extras.items() if ex]:
        if n in merged:
            continue
        merged[n] = list(groups.get(n, [])) + \
            [k for k in extras.get(n, []) if k not in groups.get(n, [])]
    p.layer_groups = {n: ks for n, ks in merged.items() if ks}
    flat = []
    for t, i in seq:
        if t == 'g':
            flat += groups.get(i, [])
        else:
            flat.append(i)
    for k in fig_keys:
        if k not in flat:
            flat.append(k)
    n = len(flat)
    for i, k in enumerate(flat):
        cur = dict((p.figure_blocking or {}).get(k) or {})
        cur['z'] = n - i
        p.figure_blocking[k] = cur


def board_label(board) -> str:
    """How the board reads in receipts and job labels."""
    if is_cover(board):
        return f"the {board.location.value.replace('-', ' ')} cover"
    if is_insert(board):
        return f"the '{board.name}' {board.kind}"
    return f"panel {board.panel_number}"


_OPAQUE_CACHE: dict = {}


def _is_opaque(path: str) -> bool:
    """True when an acetate has no working transparency (no alpha channel,
    or a fully opaque backdrop) — cached by (path, mtime)."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return False
    v = _OPAQUE_CACHE.get(key)
    if v is None:
        try:
            from PIL import Image
            with Image.open(path) as im:
                if 'A' not in im.getbands():
                    v = True
                else:
                    a = im.getchannel('A')
                    w, h = a.size
                    corners = (a.getpixel((0, 0)), a.getpixel((w - 1, 0)),
                               a.getpixel((0, h - 1)), a.getpixel((w - 1, h - 1)))
                    v = min(corners) > 250
        except Exception:
            v = False
        if len(_OPAQUE_CACHE) > 512:
            _OPAQUE_CACHE.clear()
        _OPAQUE_CACHE[key] = v
    return v


def make_cutout_body(state, board, key: str, path: str, name: str) -> str:
    """Re-ink one acetate as a true cut-out: keep only the subject, erase the
    backdrop to full transparency, and point the board at the new file (the
    original stays put — it may be an asset's reference art)."""
    from uuid import uuid4
    from helpers.generator import invoke_edit_image_api, IMAGE_QUALITY
    from storage.filepath import obj_to_imagepath
    from PIL import Image
    storage = state.storage
    with Image.open(path) as im:
        w, h = im.size
    size = "1536x1024" if w > h else ("1024x1536" if h > w else "1024x1024")
    data = invoke_edit_image_api(
        f"""Reproduce this image EXACTLY — identical subject, identical style, identical
scale and position within the frame — but keep ONLY the {name}: erase the
background and any backdrop to FULL TRANSPARENCY.  A cut-out acetate.""",
        reference_images=[path], size=size, quality=IMAGE_QUALITY.MEDIUM,
        background="transparent", input_fidelity="high")
    figures_dir = os.path.join(os.path.dirname(
        obj_to_imagepath(obj=board, base_path=storage.base_path)), 'figures')
    os.makedirs(figures_dir, exist_ok=True)
    out = os.path.join(figures_dir, f"cutout--{uuid4().hex[:8]}.png")
    with open(out, 'wb') as fh:
        fh.write(data)
    fresh = storage.read_object(cls=type(board), primary_key=board.primary_key) or board
    if key in (fresh.figure_images or {}):
        fresh.figure_images[key] = out
        storage.update_object(fresh)
    return f"Cut {name} out onto transparent acetate: {out}"


def fresh_board(storage, board):
    """Re-pull the LIVE table state into the page's board object.  Drags and
    resizes persist out-of-band (no page rebuild), so every other write must
    sync first or it clobbers the move the author just made."""
    fresh = storage.read_object(cls=type(board), primary_key=board.primary_key)
    if fresh is not None:
        board.figure_blocking = fresh.figure_blocking
        board.figure_images = fresh.figure_images
        board.layer_groups = fresh.layer_groups
        board.image = fresh.image
    return board


def current_board(state):
    """The board (panel or cover) the user is looking at, else None."""
    from schema import Panel, Cover
    sel = state.selection or []
    if not sel:
        return None
    ids = {}
    for item in sel:
        k = item.kind.value
        if k == 'series':
            ids = {'series_id': item.id}
        elif k == 'issue':
            ids['issue_id'] = item.id
        elif k == 'scene':
            ids['scene_id'] = item.id
        elif k == 'panel':
            ids['panel_id'] = item.id
        elif k == 'cover':
            ids['cover_id'] = item.id
    last = sel[-1].kind.value
    if last == 'panel' and {'series_id', 'issue_id', 'scene_id', 'panel_id'} <= ids.keys():
        return state.storage.read_object(cls=Panel, primary_key={
            k: ids[k] for k in ('series_id', 'issue_id', 'scene_id', 'panel_id')})
    if last == 'cover' and {'series_id', 'issue_id', 'cover_id'} <= ids.keys():
        return state.storage.read_object(cls=Cover, primary_key={
            k: ids[k] for k in ('series_id', 'issue_id', 'cover_id')})
    return None


def handle_clipboard_image(state, args: dict):
    """A pasted image: on a board, offer take / table-reference / plate; on
    any other view, file it as a reference on the object being worked on."""
    import base64
    from io import BytesIO
    from uuid import uuid4
    data_url = (args or {}).get('data') or ''
    if ',' not in data_url:
        return
    raw = base64.b64decode(data_url.split(',', 1)[1])
    mime = (args or {}).get('mime') or 'image/png'
    name = f"pasted-{uuid4().hex[:6]}.png"
    board = current_board(state)
    if board is None:
        from types import SimpleNamespace
        from gui.messaging import attach_reference
        attach_reference(state, SimpleNamespace(name=name, content=BytesIO(raw), type=mime))
        return
    storage = state.storage
    with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 380px;'):
        ui.label('Pasted image').classes('caption-box caption-box-sm')
        ui.image(source=data_url).style('max-height: 180px;').props('fit=contain').classes('q-mt-sm')

        def as_take():
            dlg.close()
            locator = storage.upload_image(obj=board, name=name, data=BytesIO(raw), mime_type=mime)
            fresh_board(storage, board)
            board.image = locator
            storage.update_object(board)
            table_receipt(state, '📋 pasted an image in as a take — the table is locked to it')
            state.refresh_details()

        def as_reference():
            dlg.close()
            storage.upload_reference_image(board, name, BytesIO(raw), mime)
            table_receipt(state, '📋 pinned the pasted image to the table as a reference')
            state.refresh_details()

        def as_plate():
            dlg.close()
            locator = storage.upload_image(obj=board, name=name, data=BytesIO(raw), mime_type=mime)
            rework_take_on_table(state, board, locator)

        with ui.column().classes('w-full q-mt-sm').style('gap: 6px;'):
            ui.button('A take of this board', icon='filter_frames').props('unelevated dense no-caps') \
                .classes('w-full').on('click', lambda _: as_take())
            ui.button('The background layer (rework it here)', icon='layers').props('outline dense no-caps') \
                .classes('w-full').on('click', lambda _: as_plate())
            ui.button('A reference pinned to the table', icon='attachment').props('outline dense no-caps') \
                .classes('w-full').on('click', lambda _: as_reference())
    dlg.open()


def read_board(storage, a: dict):
    """Resolve a rough/stack event back to its board (panel, cover or insert)."""
    if a.get('cover'):
        from schema import Cover as _Cover
        return storage.read_object(cls=_Cover, primary_key={
            "series_id": a['series'], "issue_id": a['issue'], "cover_id": a['cover']})
    if a.get('insert'):
        from schema import Insert as _Insert
        return storage.read_object(cls=_Insert, primary_key={
            "series_id": a['series'], "issue_id": a['issue'], "insert_id": a['insert']})
    from schema import Panel as _Panel
    return storage.read_object(cls=_Panel, primary_key={
        "series_id": a['series'], "issue_id": a['issue'],
        "scene_id": a['scene'], "panel_id": a['panel']})


# ---------------------------------------------------------------------------
# LAYING ASSETS ON THE TABLE: one-click direct writes, shared by the table's
# own pickers AND the assets drawer (a drawer tile lays its asset right here
# when a panel is open — the drawer IS part of the table).
# ---------------------------------------------------------------------------
def table_receipt(state, text: str, undo=None, bench: str = 'the light table'):
    """A receipt panel in the chat history, spoken as the user — a paper
    slip stamped with the bench it came from.  When `undo` is given, the
    receipt carries an UNDO chip — destructive table actions always leave
    a way back."""
    try:
        from gui.avatars import comic_chat_message
        with state.history:
            with comic_chat_message(name='You', sent=True).classes('w-full'), \
                    ui.element('div').classes('receipt-slip'):
                if bench:
                    ui.label(bench).classes('receipt-slip__stamp')
                ui.markdown(text)
                if undo is not None:
                    btn = ui.button('Undo', icon='undo').props('outline dense size=sm').classes('q-mt-xs')

                    def _run_undo(_=None, btn=btn):
                        btn.disable()
                        try:
                            undo()
                            ui.notify('Put back the way it was.', type='positive')
                        except Exception as ex:
                            ui.notify(f'Could not undo: {ex}', type='warning')
                        state.refresh_details()
                    btn.on('click', _run_undo)
        state.history.scroll_to(percent=100)
    except Exception:
        pass


def pose_pending_key(board, character_id: str, variant_id: str) -> str:
    return f"{board.id}/{character_id}/{variant_id}"


def char_display_name(storage, series_id: str, character_id: str) -> str:
    """The character's NAME — a raw id must never reach a label."""
    from schema import CharacterModel
    try:
        c = storage.read_object(CharacterModel, {"series_id": series_id,
                                                 "character_id": character_id})
        if c is not None and c.name:
            return c.name
    except Exception:
        pass
    return character_id.replace('-', ' ').title()


def pose_figure_bg(state, board, character_id: str, variant_id: str,
                   pose_direction: str | None = None):
    """Queue a posed-acetate render for a figure on this board (panel or
    cover).  One pose per figure at a time: while it's on the drawing board
    the figure row shows a spinner and a second ask is refused — no more
    double renders from an impatient second click."""
    from agentic.tools.imaging import generate_figure_acetate_body
    from helpers.render_queue import enqueue_renders
    pending = getattr(state, '_poses_pending', None)
    if pending is None:
        pending = set()
        try:
            state._poses_pending = pending
        except Exception:
            pass
    pkey = pose_pending_key(board, character_id, variant_id)
    who = char_display_name(state.storage, board.series_id, character_id)
    if pkey in pending:
        ui.notify(f"{who} is already on the drawing board — "
                  f"the pose lands when it's ready.", type='warning')
        return
    pending.add(pkey)
    kw = ({"cover_id": board.cover_id} if is_cover(board)
          else {"insert_id": board.insert_id} if is_insert(board)
          else {"scene_id": board.scene_id, "panel_id": board.panel_id})

    def job():
        try:
            return generate_figure_acetate_body(
                state, board.series_id, board.issue_id,
                character_id=character_id, variant_id=variant_id,
                pose_direction=pose_direction, **kw)
        finally:
            pending.discard(pkey)
    enqueue_renders(state, [(
        f"posing {who} for {board_label(board)}", job,
    )], role="the Penciller")


def lay_figure_on_table(state, panel, character_id: str, variant_id: str,
                        name: str | None = None):
    fresh_board(state.storage, panel)
    refs = panel.character_references or []
    if not any(c.character_id == character_id and c.variant_id == variant_id for c in refs):
        panel.character_references = refs + [CharacterRef(
            series_id=panel.series_id, character_id=character_id, variant_id=variant_id)]
        state.storage.update_object(panel)
    table_receipt(state, f"🎭 laid **{name or character_id.replace('-', ' ')}** on the table "
                         f"— posing them for the panel…")
    pose_figure_bg(state, panel, character_id, variant_id)
    state.refresh_details()


def lay_background_on_table(state, scene, panel, setting):
    scene.setting_id = setting.setting_id
    state.storage.update_object(scene)
    # a new background replaces any split plate
    fresh_board(state.storage, panel)
    if (panel.figure_images or {}).pop('background/plate', None) is not None:
        for gname in list(panel.layer_groups or {}):
            panel.layer_groups[gname] = [k for k in panel.layer_groups[gname]
                                         if k != 'background/plate']
            if not panel.layer_groups[gname]:
                panel.layer_groups.pop(gname)
        state.storage.update_object(panel)
    table_receipt(state, f"🏔 laid the **{setting.name}** background on the table")
    state.refresh_details()


def lay_prop_on_table(state, scene, prop_asset):
    if any(p.name == prop_asset.name for p in (scene.props or [])):
        table_receipt(state, f"🎪 **{prop_asset.name}** is already on the table")
    else:
        scene.props = (scene.props or []) + [Prop(name=prop_asset.name,
                                                  description=prop_asset.description)]
        state.storage.update_object(scene)
        table_receipt(state, f"🎪 laid the **{prop_asset.name}** prop on the table")
    state.refresh_details()


def lay_prop_acetate(state, board, prop_asset, style_id: str | None = None) -> bool:
    """Lay a prop's reference art on the board as an element acetate — covers
    have no scene props, so the art itself goes on the table."""
    from agentic.tools.normalization import normalize_id
    imgs = prop_asset.images or {}
    img = imgs.get(style_id) or next((i for i in imgs.values() if i and os.path.exists(i)), None)
    if not (img and os.path.exists(img)):
        # SELF-HEALING: instead of scolding, ink the reference right now
        from agentic.tools.imaging import render_prop_reference_body
        from helpers.render_queue import enqueue_renders
        sid = style_id or 'vintage-four-color'
        table_receipt(state, f"🖌 **{prop_asset.name}** has no reference art yet — inking it "
                             f"in {sid}; it lands on the table by itself")

        def _lay_when_landed(_result, _b=board, _pa=prop_asset, _sid=sid):
            # the paid render LANDS where the author asked — the acetate
            # lays itself instead of demanding a second click
            try:
                fresh = state.storage.read_object(type(_pa), {"series_id": _pa.series_id,
                                                              "prop_id": _pa.prop_id})
                if fresh is not None:
                    lay_prop_acetate(state, _b, fresh, _sid)
            except Exception as ex:
                logger.debug(f"auto-lay after prop self-heal skipped: {ex}")
        enqueue_renders(state, [(
            f"prop reference — {prop_asset.name} in {sid}",
            lambda: render_prop_reference_body(state, prop_asset.series_id,
                                               prop_asset.prop_id, sid),
            _lay_when_landed,
        )], role='the Prop Maker')
        return False
    fresh_board(state.storage, board)
    slug = normalize_id(prop_asset.name)
    key = f'element/{slug}'
    n = 2
    while key in (board.figure_images or {}):
        key = f'element/{slug}-{n}'
        n += 1
    board.figure_images[key] = img
    board.figure_blocking[key] = {"x": 50, "y": 6, "h": 28, "z": 55}
    state.storage.update_object(board)
    table_receipt(state, f"🎪 laid **{prop_asset.name}** on the table as an acetate")
    state.refresh_details()
    return True


def wear_style_on_table(state, scene, style):
    """`scene` is whatever owns the style_id: a scene, a cover, or an issue."""
    scene.style_id = style.style_id
    state.storage.update_object(scene)
    table_receipt(state, f"🎨 swapped the style swatch — new work here prints in **{style.name}**")
    state.refresh_details()


def style_swatch(state, scene, shared_with: str | None = None):
    """THE STYLE SWATCH: a printer's color chip taped to the board — the
    style everything here prints in.  Click to swap it; takes, backgrounds
    and sheets rendered afterwards wear the new style.  `scene` is whatever
    owns the style_id: a scene, a cover, or an issue.  When the swatch is
    borrowed from a larger unit (a panel wears its scene's swatch), pass
    `shared_with` (e.g. 'the whole scene') so the swatch says so before a
    swap surprises the neighbors."""
    storage = state.storage
    cur = storage.read_object(cls=ComicStyle, primary_key={"style_id": scene.style_id}) \
        if getattr(scene, 'style_id', None) else None

    def _art(st):
        art = st.image.get('art') if isinstance(st.image, dict) else st.image
        return art if art and os.path.exists(art) else None

    def pick():
        with ui.dialog() as dlg, ui.card().classes('soft-card') \
                .style('min-width: 520px; max-width: 780px;'):
            ui.label('Swap the style swatch').classes('caption-box caption-box-sm')
            ui.label('Every take printed here wears the swatched style — '
                     'pick the one it should wear.').classes('text-sm q-mt-sm')
            if shared_with:
                ui.label(f'This swatch is taped to {shared_with} — swapping it '
                         f'restyles everything that wears it.').classes('text-xs text-gray-500')
            with ui.row().classes('w-full q-mt-sm').style('gap: 10px;'):
                for st in storage.read_all_objects(ComicStyle, order_by='name'):
                    art = _art(st)
                    current = getattr(scene, 'style_id', None) == st.style_id
                    with ui.card().classes('soft-card p-1' + (' style-swatch-current'
                                                              if current else ' cursor-pointer')) \
                            .style('width: 150px;') as card:
                        if art:
                            ui.image(source=_src(art)).style('height: 90px;').props('fit=cover')
                        ui.label(st.name.title() + (' — on the board' if current else '')) \
                            .classes('text-xs text-center w-full')
                    if not current:
                        card.on('click', lambda _, st=st: (dlg.close(),
                                                           wear_style_on_table(state, scene, st)))
        dlg.open()

    swatch = ui.element('div').classes('style-swatch cursor-pointer')
    with swatch:
        art = _art(cur) if cur is not None else None
        if art:
            ui.image(source=_src(art)).classes('style-swatch-art')
        else:
            ui.icon('palette').style('font-size: 16px;')
        ui.label(cur.name if cur is not None else 'pick a style').classes('style-swatch-name')
    swatch.tooltip('The style this prints in — click to swap the swatch'
                   + (f' ({shared_with} wears it)' if shared_with else ''))
    swatch.on('click', lambda _: pick())
    return swatch


def rework_take_on_table(state, board, img: str):
    """A take becomes the table's background layer, ready to split, heal
    and layer over — and the table unlocks (no take selected)."""
    fresh_board(state.storage, board)
    board.figure_images['background/plate'] = img
    board.image = None
    state.storage.update_object(board)
    table_receipt(state, "🛠 laid a take on the table as the background layer")
    state.refresh_details()


# TAKES: frame sizes per board shape — every frame the exact shape of its art.
TAKE_SHAPES = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (2, 3), FrameLayout.SQUARE: (3, 3)}
DROP_SHAPES = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (3, 3), FrameLayout.SQUARE: (3, 3)}


def tear_up_take(state, board, img: str):
    """Tear up one of the board's takes.  Into the wastebasket, not gone:
    dot-prefixed files vanish from the takes wall and the receipt's UNDO
    chip brings them back (unique names so tearing up a same-named take
    never clobbers an older wastebasket copy)."""
    from uuid import uuid4
    storage = state.storage
    fresh_board(storage, board)
    trash = os.path.join(os.path.dirname(img), f".trash--{uuid4().hex[:6]}--{os.path.basename(img)}")
    try:
        os.replace(img, trash)
    except OSError:
        ui.notify('Could not tear up that take.', type='warning')
        return
    was_featured = bool(board.image and (
        board.image == img or storage.find_image(obj=board, locator=board.image) == img))
    saved_locator = board.image
    if was_featured:
        board.image = None
        storage.update_object(board)

    def undo():
        # a newer same-named take may have landed meanwhile — never clobber
        # it; the restored take diverts to a fresh name (both stay visible)
        dest = img
        if os.path.exists(dest):
            stem, ext = os.path.splitext(os.path.basename(img))
            dest = os.path.join(os.path.dirname(img), f"{stem}--{uuid4().hex[:6]}{ext}")
        os.replace(trash, dest)
        if was_featured:
            b = storage.read_object(cls=type(board), primary_key=board.primary_key) or board
            b.image = saved_locator if dest == img else dest
            storage.update_object(b)
    table_receipt(state, '🗑 tore up a take — the receipt can bring it back', undo=undo)
    state.refresh_details()


def wastebasket_chip(state, board):
    """Torn-up takes and removed references outlive their chat receipts as
    dot-prefixed wastebasket files.  This quiet chip opens the basket and
    puts things back — nothing destructive is ever more than a click from
    recovery, even after a restart."""
    from uuid import uuid4
    from storage.filepath import obj_to_imagepath, obj_to_reference_path
    storage = state.storage
    img_dir = obj_to_imagepath(board, base_path=storage.base_path)
    dirs = [(img_dir, 'take'),
            (os.path.join(os.path.dirname(img_dir), 'figures'), 'acetate'),
            (obj_to_reference_path(board, base_path=storage.base_path), 'reference')]
    entries = []
    for d, kind in dirs:
        if d and os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.startswith('.trash--'):
                    entries.append((os.path.join(d, f), kind))
    if not entries:
        return

    def open_basket():
        with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 760px;'):
            ui.label('The wastebasket').classes('caption-box caption-box-sm')
            ui.label('Torn-up takes, replaced art and removed references — '
                     'put any of them back.').classes('text-sm q-mt-sm')
            with ui.row().classes('w-full q-mt-sm').style('gap: 10px;'):
                for path, kind in entries:
                    with ui.column().classes('items-center').style('width: 150px; gap: 4px;'):
                        ui.image(source=_src(path)).style('max-height: 100px; width: 100%;').props('fit=contain')
                        name = os.path.basename(path).split('--', 2)[-1]
                        ui.label(f"{kind} · {name[:20]}").classes('text-xs text-gray-500') \
                            .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;')

                        def put_back(path=path, kind=kind):
                            import shutil
                            base = os.path.basename(path).split('--', 2)[-1]
                            dest = os.path.join(os.path.dirname(path), base)
                            if kind == 'acetate' and os.path.exists(dest):
                                # the board references this exact path — swap
                                # the art back IN, wastebasketing the current
                                # version in turn (a uniquified orphan would
                                # be referenced by nothing)
                                counter = os.path.join(os.path.dirname(path),
                                                       f".trash--{uuid4().hex[:6]}--{base}")
                                shutil.copyfile(dest, counter)
                                os.replace(path, dest)
                            else:
                                if os.path.exists(dest):
                                    stem, ext = os.path.splitext(base)
                                    dest = os.path.join(os.path.dirname(path),
                                                        f"{stem}--{uuid4().hex[:6]}{ext}")
                                os.replace(path, dest)
                            table_receipt(state, f"♻️ put a {kind} back from the wastebasket")
                            dlg.close()
                            state.refresh_details()
                        ui.button('Put it back', icon='restore').props('outline dense size=sm no-caps') \
                            .on('click', lambda _, p=path, k=kind: put_back(p, k))

            def empty_it():
                for path, _k in entries:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                table_receipt(state, f"🗑 emptied the wastebasket — {len(entries)} piece{'s' if len(entries) != 1 else ''} gone for good")
                dlg.close()
                state.refresh_details()
            with ui.row().classes('w-full justify-end q-mt-sm'):
                eb = ui.button('Empty the wastebasket', icon='delete_forever', color='negative') \
                    .props('outline dense no-caps')

                def confirm_empty(_e, eb=eb):
                    # two clicks for the only action with no way back
                    if 'Really' in (eb.text or ''):
                        empty_it()
                    else:
                        eb.set_text('Really empty it? This is forever')
                eb.on('click', confirm_empty)
        dlg.open()

    ui.chip(f'wastebasket · {len(entries)}', icon='delete_outline').props('dense clickable outline') \
        .tooltip('Torn-up takes and removed references — restore them here') \
        .on('click', lambda _: open_basket())


def takes_row(state, board, featured: str | None):
    """Every render of this board on one wall; click a take to feature it
    (locking the table); the layers overlay lays it back down to rework."""
    from gui.elements import header, ruled_page, uploader_card
    storage = state.storage

    def set_image(locator: str):
        fresh_board(storage, board)
        board.image = locator
        storage.update_object(board)
        table_receipt(state, '📌 featured a take — the table is locked to its arrangement')
        state.refresh_details()

    def explode_take(img: str):
        """A take (or an imported image) goes BACK to layers: it becomes the
        plate and the split flow opens on it — recognize, lift, rework."""
        state._auto_split_board = board.id
        rework_take_on_table(state, board, img)

    takes = [img for img in storage.list_images(board) if os.path.exists(img)]
    with ui.row().classes('w-full items-center').style('gap: 10px;'):
        header("Takes", 4)
        wastebasket_chip(state, board)
    with ruled_page() as packer:
        for img in takes:
            with packer.place_cell([TAKE_SHAPES[board.aspect]], fudge=False):
                with ui.card().classes('soft-card p-2 mosaic-card relative panel-fill cursor-pointer') as take:
                    ui.image(source=img).props('fit=cover').classes('absolute inset-0 w-full h-full')
                    if img == featured:
                        ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10')
                    ui.button(icon='delete').props('flat round dense size=xs') \
                        .classes('absolute top-1 left-1 z-10 bg-white/70 dark:bg-black/50') \
                        .tooltip('Tear up this take') \
                        .on('click.stop', lambda _, img=img: tear_up_take(state, board, img))
                    ui.button(icon='layers').props('flat round dense size=xs') \
                        .classes('absolute bottom-1 right-1 z-10 bg-white/70 dark:bg-black/50') \
                        .tooltip('Rework this take on the table (becomes the background layer)') \
                        .on('click.stop', lambda _, img=img: rework_take_on_table(state, board, img))
                    ui.button(icon='splitscreen').props('flat round dense size=xs') \
                        .classes('absolute bottom-1 left-8 z-10 bg-white/70 dark:bg-black/50') \
                        .tooltip('EXPLODE into layers — it becomes the background and its '
                                 'figures and elements are recognized and lifted onto acetates') \
                        .on('click.stop', lambda _, img=img: explode_take(img))
                take.tooltip('The featured take — this is the print' if img == featured
                             else 'Feature this take as the print — the table locks to its arrangement')
                take.on('click', lambda _, img=img: set_image(img))

        def on_upload_take(e):
            locator = storage.upload_image(obj=board, name=e.name, data=e.content, mime_type=e.type)
            set_image(locator)

        uploader_card(state, on_upload=on_upload_take, packer=packer,
                      variants=[DROP_SHAPES[board.aspect]],
                      label='Drop image to add a take')


def light_table(state: APPState, panel, scene, setting,
                featured: str | None = None, actions=None,
                description_label: str = "The brief"):
    """
    actions: optional list of (icon, tooltip, handler) riding THE PRINT.
    A selected take LOCKS the table (the print corresponds to this exact
    arrangement); unlocking deselects the take so the table can be reworked.
    """
    storage = state.storage
    series_id = panel.series_id
    locked = featured is not None
    cover_mode = is_cover(panel)   # a cover is a board like any other
    insert_mode = is_insert(panel)  # so is a full-page insert
    board_attrs = ({'data-cover': panel.cover_id} if cover_mode
                   else {'data-insert': panel.insert_id} if insert_mode
                   else {'data-scene': panel.scene_id, 'data-panel': panel.panel_id})

    # BLOCKING: the drag/scale script ships in main.py's page head; here we
    # wire the event once per client — the handler resolves the panel from
    # the event, so it survives view changes.
    if not getattr(state, '_rough_block_wired', False):
        state._rough_block_wired = True

        def _on_block(e):
            a = e.args
            p = read_board(state.storage, a)
            if p is None:
                return
            cur = dict((p.figure_blocking or {}).get(a['key']) or {})
            cur.update({"x": round(a['x'], 1), "y": round(a['y'], 1)})
            if a.get('h'):
                cur["h"] = round(a['h'], 1)
            if a.get('fs'):
                cur["fs"] = round(a['fs'], 1)
            if a.get('tx') or a.get('ty'):
                cur["tx"] = round(a.get('tx', 0), 1)
                cur["ty"] = round(a.get('ty', 0), 1)
            p.figure_blocking[a['key']] = cur
            state.storage.update_object(p)
        ui.on('rough_block', _on_block)

        def _on_text(e):
            a = e.args
            p = read_board(state.storage, a)
            if p is None or not a.get('text'):
                return
            parts = a['key'].split('/')
            if parts[0] == 'letterblock' and len(parts) == 2 and hasattr(p, 'description'):
                # editing a letter block writes it back into the page's words
                from helpers.compositor import letter_blocks
                blocks = letter_blocks(p.description, cap=999)
                i = int(parts[1])
                if i < len(blocks):
                    blocks[i] = a['text']
                    p.description = '\n\n'.join(blocks)
                    state.storage.update_object(p)
                return
            if not hasattr(p, 'dialogue'):
                return
            if parts[0] == 'balloon' and len(parts) == 2:
                i = int(parts[1])
                if i < len(p.dialogue):
                    p.dialogue[i].text = a['text']
            elif parts[0] == 'caption' and len(parts) == 3:
                pos, i = parts[1], int(parts[2])
                matching = [n for n in p.narration if n.position.value == pos]
                if i < len(matching):
                    matching[i].text = a['text']
            state.storage.update_object(p)
        ui.on('rough_text', _on_text)

        def _on_reorder(e):
            a = e.args
            p = read_board(state.storage, a)
            if p is None:
                return
            apply_stack_reorder(p, a['src'], a['dst'], a.get('mode', 'before'))
            state.storage.update_object(p)
            state.refresh_details()
        ui.on('stack_reorder', _on_reorder)

    # ---- gather the acetates -------------------------------------------
    background = None
    bg_style_missing = False   # the setting has no master inked in THIS style
    split_plate = (panel.figure_images or {}).get("background/plate")
    if split_plate and os.path.exists(split_plate):
        background = split_plate
    elif setting is not None:
        style_id = scene.style_id if scene is not None else None
        from helpers.masters import master_for
        background, _exact = master_for(setting, style_id, panel.aspect)
        # not exact = borrowed style or orientation — the honest re-ink
        # offer stands, and re-inking writes ITS OWN key (no clobber)
        bg_style_missing = not _exact

    _char_names = {c.character_id: c.name for c in storage.read_all_objects(
        CharacterModel, primary_key={"series_id": series_id})}
    figures = []
    for i, ref in enumerate(panel.character_references or []):
        key = f"{ref.character_id}/{ref.variant_id}"
        posed = (panel.figure_images or {}).get(key)
        posed = posed if posed and os.path.exists(posed) else None
        sheet = storage.find_variant_image(series_id=series_id, character_id=ref.character_id,
                                           variant_id=ref.variant_id)
        sheet = sheet if sheet and os.path.exists(sheet) else None
        blocking = dict((panel.figure_blocking or {}).get(key) or {})
        blocking.setdefault("x", (18, 50, 82)[i % 3])
        blocking.setdefault("y", 0)
        blocking.setdefault("h", 78 if posed else 52)
        blocking.setdefault("z", i)
        figures.append({"ref": ref, "key": key, "img": posed or sheet,
                        "posed": posed is not None,
                        "on": bool(blocking.get("on", 1)), "blocking": blocking})

    for key, path in sorted((panel.figure_images or {}).items()):
        if not key.startswith("element/") or not (path and os.path.exists(path)):
            continue
        blocking = dict((panel.figure_blocking or {}).get(key) or {})
        blocking.setdefault("x", 50)
        blocking.setdefault("y", 0)
        blocking.setdefault("h", 45)
        blocking.setdefault("z", 40)
        figures.append({"ref": None, "key": key, "img": path, "posed": True,
                        "on": bool(blocking.get("on", 1)), "blocking": blocking,
                        "name": key.split("/", 1)[1].replace("-", " ")})

    props = [{"name": p.name, "on": True}
             for p in (getattr(scene, 'props', None) or [])]

    references = [{"img": u, "on": True} for u in storage.list_uploads(panel)
                  if u and os.path.exists(u)]

    def _key_on(key, default=1):
        return bool(((panel.figure_blocking or {}).get(key) or {}).get('on', default))

    # LETTERS live on panels AND covers (taglines, a balloon spoken right off
    # the cover) — any board with dialogue/narration fields gets the full
    # letters experience.
    supports_letters = hasattr(panel, 'dialogue')
    board_dialogue = getattr(panel, 'dialogue', None) or []
    board_narration = getattr(panel, 'narration', None) or []
    # A TEXT INSERT'S LETTERS: the mailbag's letters (blank-line-separated
    # blocks of its description) ride the table as letter-block acetates
    from helpers.compositor import letter_blocks
    board_blocks = (letter_blocks(panel.description)
                    if insert_mode and not locked and getattr(panel, 'kind', None) == 'mailbag'
                    else [])
    has_letters = bool(board_narration or board_dialogue or board_blocks)
    letter_keys = [f'balloon/{i}' for i in range(len(board_dialogue[:4]))]
    for _pos in ('top', 'bottom'):
        _caps = [n for n in board_narration if n.position.value == _pos]
        letter_keys += [f'caption/{_pos}/{i}' for i in range(len(_caps[:2]))]
    letter_keys += [f'letterblock/{i}' for i in range(len(board_blocks))]
    # the master eye rules its letters recursively; it reads as ON when any is
    letters = {"on": has_letters and (not letter_keys or any(_key_on(k) for k in letter_keys)),
               "keys": letter_keys}
    bg_layer = {"on": background is not None and _key_on('background'), "key": "background"}

    aspect = _ASPECT[panel.aspect.value]
    # the rough and the print display in the board's orientation; portrait
    # boards cap their height so the table never towers off the page
    _ar = {'landscape': 1.5, 'portrait': 2 / 3, 'square': 1.0}[panel.aspect.value]
    canvas_style = (f'aspect-ratio: {aspect}; max-height: 72vh; '
                    f'max-width: calc(72vh * {_ar:.4f});')

    # ---- THE ROUGH: the live mock --------------------------------------
    @ui.refreshable
    def rough():
        # drags persist out-of-band: repaint from the LIVE table state
        fresh_board(storage, panel)
        canvas = ui.element('div').classes('rough-canvas').style(canvas_style)
        canvas._props['data-series'] = series_id
        canvas._props['data-issue'] = panel.issue_id
        for k, v in board_attrs.items():
            canvas._props[k] = v
        if locked:
            canvas._props['data-locked'] = '1'
        with canvas:
            if bg_layer["on"] and background:
                ui.image(source=_src(background)).props('fit=cover') \
                    .classes('absolute inset-0 w-full h-full').style('z-index: 1;')
            elif locked and featured and not any(f["on"] and f["img"] for f in figures):
                # A LOCKED, EMPTY TABLE still shows its truth: the featured
                # print sits ghosted on the glass — this is what the board
                # prints; unlock to lay it back down as layers
                ui.image(source=_src(featured)).props('fit=contain') \
                    .classes('absolute inset-0 w-full h-full rough-ghost-print').style('z-index: 1;')
                ui.label('the featured print — the table is locked to it') \
                    .classes('rough-ghost-print__note')
            else:
                with ui.column().classes('absolute inset-0 items-center justify-center') \
                        .style('z-index: 1; gap: 8px;'):
                    ui.label('bare board — no background on the table').classes('text-xs text-gray-500')
                    if not locked:
                        with ui.row().style('gap: 8px;'):
                            if setting is not None and bg_style_missing:
                                ui.button(f'Ink the {setting.name.title()} master', icon='brush') \
                                    .props('outline dense size=sm') \
                                    .on('click', lambda _: ink_master_here())
                            ui.button('Lay a background', icon='landscape').props('outline dense size=sm') \
                                .on('click', lambda _: pick_background())
                            ui.button('Cast a figure', icon='person_add').props('outline dense size=sm') \
                                .on('click', lambda _: pick_figure())

            canvas_ar = {'landscape': 1.5, 'portrait': 2 / 3, 'square': 1.0}[panel.aspect.value]

            def img_k(path):
                return _img_ar(path) / canvas_ar  # width%% per height%%

            live_blk = panel.figure_blocking or {}
            visible = [f for f in figures if f["on"] and f["img"]]
            for f in sorted(visible, key=lambda g: {**g["blocking"], **(live_blk.get(g["key"]) or {})}.get("z", 0)):
                b = {**f["blocking"], **(live_blk.get(f["key"]) or {})}
                k = img_k(f["img"])
                cls = 'rough-figure rough-drag' + (' rough-figure-posed' if f["posed"] else '')
                if b.get('lock'):
                    cls += ' rough-locked'
                flip = ' scaleX(-1)' if b.get('flip') else ''
                rot = f' rotate({float(b["rot"]):g}deg)' if b.get('rot') else ''
                fig = ui.image(source=_src(f["img"])).props('fit=contain').classes(cls) \
                    .style(f'left: {b["x"]}%; bottom: {b["y"]}%; height: {b["h"]}%; '
                           f'width: {b["h"] * k}%; '
                           f'transform: translateX(-50%){flip}{rot}; '
                           f'z-index: {max(1, 10 + int(b.get("z", 0)))};')
                fig._props['data-key'] = f["key"]
                fig._props['data-war'] = f'{k:.4f}'
                if b.get('flip'):
                    fig._props['data-flip'] = '1'
                if b.get('lock'):
                    fig._props['data-lock'] = '1'
                if b.get('rot'):
                    fig._props['data-rot'] = f'{float(b["rot"]):g}'

            # UNPOSED SILHOUETTES: a cast figure with no acetate yet still
            # stands on the rough — a dashed stand-in where they'll be,
            # and clicking it poses them
            if not locked:
                unposed = [f for f in figures
                           if f["on"] and not f["img"] and f.get("ref") is not None]
                for i, f in enumerate(unposed):
                    b = {**f["blocking"], **(live_blk.get(f["key"]) or {})}
                    x = b.get('x', 22 + (i * 24) % 72)
                    y = b.get('y', 4)
                    h = b.get('h', 52)
                    nm = (_char_names.get(f["ref"].character_id)
                          or f["ref"].character_id.replace('-', ' ')).title()
                    sil = ui.element('div').classes('rough-silhouette') \
                        .style(f'left: {x}%; bottom: {y}%; height: {h}%; '
                               f'width: {h * 0.42}%; transform: translateX(-50%); z-index: 9;')
                    with sil:
                        ui.icon('accessibility_new').classes('rough-silhouette__icon')
                        ui.label(nm).classes('rough-silhouette__name')
                    sil.tooltip(f'{nm} is cast but not posed yet — click to pose them')
                    sil.on('click', lambda _, r=f["ref"]: pose_dialog(r.character_id, r.variant_id))

            live_props = [p["name"] for p in props if p["on"]]
            if live_props:
                with ui.row().classes('absolute').style('bottom: 4px; left: 6px; z-index: 65; gap: 4px;'):
                    for name in live_props:
                        ui.label(name).classes('rough-prop')

            pinned = [r for r in references if r["on"]]
            for i, r in enumerate(pinned[:4]):
                ui.image(source=_src(r["img"])).classes('rough-pin') \
                    .style(f'top: {4 + i * 6}%; right: {3 + (i % 2) * 4}%; '
                           f'transform: rotate({(-6, 5, -3, 7)[i % 4]}deg); z-index: 71;')

            if letters["on"] and has_letters:
                saved = panel.figure_blocking or {}

                def letter(key, el_classes, text, dx, dy, kind, tail=None, emphasis=None):
                    b = saved.get(key) or {}
                    if not b.get('on', 1):
                        return None
                    x, y = b.get('x', dx), b.get('y', dy)
                    fs = b.get('fs', 11)
                    cls = el_classes + ' rough-drag'
                    if b.get('lock'):
                        cls += ' rough-locked'
                    if emphasis:
                        cls += f" rough-balloon--{emphasis.replace(' ', '-')}"
                    lbl = ui.label(text).classes(cls).style(
                        f'left: {x}%; bottom: {y}%; top: auto; font-size: {fs}px; z-index: 70;')
                    lbl._props['data-key'] = key
                    lbl._props['data-scale'] = 'font'
                    lbl._props['data-fs'] = f'{fs:g}'
                    lbl._props['data-kind'] = kind
                    if b.get('lock'):
                        lbl._props['data-lock'] = '1'
                    if kind == 'balloon':
                        # the tail's endpoint: aimed at the speaker by default
                        lbl._props['data-tx'] = str(b.get('tx', x))
                        lbl._props['data-ty'] = str(b.get('ty', max(y - 14, 2)))
                    return lbl

                tops = [n for n in board_narration if n.position.value == 'top'][:2]
                for i, n in enumerate(tops):
                    letter(f'caption/top/{i}', 'rough-narration', n.text, 2, 88 - i * 12, 'caption')
                for i, d in enumerate(board_dialogue[:4]):
                    # the balloon hangs near its speaker when they're on the table
                    fig = next((f for f in visible
                                if f.get("ref") and f["ref"].character_id == d.character_id), None)
                    dx = fig["blocking"]["x"] if fig else (25 + 22 * i)
                    bl = letter(f'balloon/{i}', 'rough-balloon', d.text,
                                dx, 72 - (i % 2) * 14, 'balloon', tail='left',
                                emphasis=d.emphasis.value)
                    if bl is not None:
                        bl._props['title'] = (f"{_char_names.get(d.character_id, d.character_id)} "
                                              f"speaks — double-click to edit, drag to place")
                for i, n in enumerate([n for n in board_narration if n.position.value == 'bottom'][:1]):
                    letter(f'caption/bottom/{i}', 'rough-narration', n.text, 2, 4, 'caption')
                # the mailbag's letters: one draggable block per letter,
                # blocked here and honored by the composite
                step = 84 / max(len(board_blocks), 1)
                for i, btext in enumerate(board_blocks):
                    lb = letter(f'letterblock/{i}', 'rough-narration rough-letterblock', btext,
                                8, max(88 - i * step, 4), 'caption')
                    if lb is not None:
                        lb._props['title'] = ('a letter block — drag to place it on the page, '
                                              '⌘-wheel to size, double-click to edit')

    # ---- POSE: describe the pose first, then render in the background ----
    def pose_figure(character_id: str, variant_id: str, pose_direction: str | None = None):
        pose_figure_bg(state, panel, character_id, variant_id, pose_direction)
        # rebuild so the figure row shows its posing… spinner right away
        state.refresh_details()

    async def split_flow(layer_key: str, source_path: str):
        import asyncio
        from agentic.tools.imaging import recognize_layer_entities, split_layer_body, series_cast_roster
        from helpers.render_queue import enqueue_renders
        # ALWAYS show the thinking: a persistent busy card while the vision
        # pass reads the layer (a toast fades long before the ~10s it takes),
        # and the drawing-board chip counts it too
        pending = getattr(state, '_render_pending', None)
        if pending is None:
            pending = []
            state._render_pending = pending
        busy_label = f"reading the '{layer_key}' layer"
        pending.append(busy_label)
        with ui.dialog().props('persistent') as busy, \
                ui.card().classes('soft-card').style('min-width: 340px;'):
            with ui.row().classes('items-center').style('gap: 12px;'):
                ui.spinner('dots', size='2em', color='primary')
                ui.label('Reading the layer — recognizing its elements…').classes('text-sm')
        busy.open()
        try:
            roster = series_cast_roster(storage, series_id)
            entities = await asyncio.to_thread(recognize_layer_entities, source_path, 8, roster)
        finally:
            busy.close()
            try:
                pending.remove(busy_label)
            except ValueError:
                pass
        if not entities:
            ui.notify('No liftable elements recognized on that layer.', type='warning')
            return
        cast_names = {c['character_id']: (c.get('name') or c['character_id']) for c in roster}
        with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px;'):
            ui.label('Split this layer').classes('caption-box caption-box-sm')
            ui.label('Pick what to lift onto its own acetate.  The layer is repainted '
                     'with them removed — revealing what was beneath.').classes('text-sm q-mt-sm')
            picks = []
            for e in entities:
                note = f" — beneath: {e['beneath']}" if e.get('beneath') else ''
                with ui.row().classes('items-center flex-nowrap w-full').style('gap: 6px;'):
                    cb = ui.checkbox(f"{e['name']}{note}", value=True)
                    who = cast_names.get(e.get('character_id'))
                    if who:
                        ui.chip(f"= {who}", icon='badge').props('dense outline color=primary') \
                            .tooltip("Recognized as a cast member — lands as their figure acetate, "
                                     "linked to their reference sheets")
                picks.append((e, cb))
            extra = ui.input(placeholder='…something else on this layer').classes('w-full').props('outlined dense')

            def go():
                chosen = [e for e, cb in picks if cb.value]
                if (extra.value or '').strip():
                    chosen.append({'name': extra.value.strip(), 'box': {}})
                if not chosen:
                    ui.notify('Pick at least one element.', type='warning')
                    return
                dlg.close()
                ui.notify(f"Splitting {len(chosen)} element(s) — {len(chosen) + 1} renders, "
                          f"the acetates land shortly.", type='info')
                kw = ({"cover_id": panel.cover_id} if cover_mode
                      else {"insert_id": panel.insert_id} if insert_mode
                      else {"scene_id": panel.scene_id, "panel_id": panel.panel_id})
                enqueue_renders(state, [(
                    f"splitting {len(chosen)} element(s) off '{layer_key}'",
                    lambda: split_layer_body(state, series_id, panel.issue_id,
                                             layer=layer_key, entities=chosen, **kw),
                )], role='the Background Artist')
            with ui.row().classes('w-full justify-end'):
                ui.button(f'Lift the selected', icon='content_cut').props('unelevated dense') \
                    .on('click', lambda _: go())
        dlg.open()

    def pose_dialog(character_id: str, variant_id: str):
        name = _char_names.get(character_id) or character_id.replace('-', ' ').title()
        with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 460px;'):
            ui.label(f"Pose {name}").classes('caption-box caption-box-sm')
            hint = getattr(panel, 'beat', None) or panel.description or ''
            direction = ui.textarea(
                placeholder=f"Describe the pose — e.g. from the script: “{hint[:120]}…”" if hint
                else 'Describe the pose, expression and action…').classes('w-full').props('outlined autofocus')
            with ui.row().classes('w-full justify-end').style('gap: 8px;'):
                ui.button('Let the script decide').props('flat dense') \
                    .on('click', lambda _: (dlg.close(), pose_figure(character_id, variant_id)))

                def go():
                    text = (direction.value or '').strip()
                    dlg.close()
                    pose_figure(character_id, variant_id, text or None)
                ui.button('Pose', icon='accessibility_new').props('unelevated dense').on('click', lambda _: go())
        dlg.open()

    # ---- one acetate row on the table -----------------------------------
    def eye(layer: dict):
        btn = ui.button(icon='visibility' if layer["on"] else 'visibility_off') \
            .props('flat round dense size=sm')

        def toggle():
            fresh_board(storage, panel)
            layer["on"] = not layer["on"]
            # a layer with "keys" is a group of layers: the eye rules them ALL
            keys = ([layer["key"]] if layer.get("key") else []) + list(layer.get("keys") or [])
            for k in keys:
                cur = dict((panel.figure_blocking or {}).get(k) or {})
                cur["on"] = 1 if layer["on"] else 0
                panel.figure_blocking[k] = cur
            if keys:
                storage.update_object(panel)
            btn.props(f'icon={"visibility" if layer["on"] else "visibility_off"}')
            if layer.get("keys"):
                state.refresh_details()   # member rows' eyes follow the group
            else:
                rough.refresh()
        btn.on('click', toggle)
        btn.tooltip('Lift this acetate off the table' if layer["on"] else 'Lay it back down')

    def padlock(layer: dict):
        """THE PIN: a pinned acetate (or group) stays put — no drags, no
        wheel, no nudges — until unpinned.  Locks live in the blocking."""
        keys = ([layer["key"]] if layer.get("key") else []) + list(layer.get("keys") or [])
        if not keys:
            return
        blk = panel.figure_blocking or {}
        pinned = all((blk.get(k) or {}).get('lock') for k in keys)
        btn = ui.button(icon='push_pin').props('flat round dense size=xs' +
                                               ('' if pinned else ' color=grey-5'))

        def toggle(pinned=pinned):
            fresh_board(storage, panel)
            now = not pinned
            for k in keys:
                cur = dict((panel.figure_blocking or {}).get(k) or {})
                cur['lock'] = 1 if now else 0
                panel.figure_blocking[k] = cur
            storage.update_object(panel)
            state.refresh_details()
        btn.on('click', toggle)
        btn.tooltip('Unpin — let it move again' if pinned
                    else 'Pin this acetate down — no drags, no resizes')

    def layer_row(icon: str, label: str, layer: dict, thumb: str | None = None,
                  edit_message: str | None = None, on_heal=None, heal_tip: str = ''):
        with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
            eye(layer)
            padlock(layer)
            if thumb:
                ui.image(source=_src(thumb)).classes('light-thumb')
            else:
                ui.icon(icon).classes('text-lg').style('width: 40px; text-align: center;')
            ui.label(label).classes('text-sm').style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
            if edit_message or on_heal:
                ui.space()
            if edit_message:
                ui.button(icon='edit').props('flat round dense size=xs') \
                    .tooltip('Rewrite with the coauthor') \
                    .on('click', lambda _, m=edit_message: post_user_message(state, m))
            if on_heal:
                ui.button(icon='healing').props('flat round dense size=xs') \
                    .tooltip(heal_tip or 'Take this acetate to the healing bench') \
                    .on('click', lambda _: on_heal())

    # ---- INK: hand the rough to the coauthor -----------------------------
    def ink():
        parts = []
        if bg_layer["on"] and setting is not None:
            parts.append(f"the '{setting.name}' master background as the setting")
        elif not bg_layer["on"]:
            parts.append("no setting background")
        on_figs = [f for f in figures if f["on"]]
        if on_figs:
            fresh = storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel

            def depth(h):
                return "near/large" if h >= 88 else ("far/small" if h <= 55 else "mid-ground")

            def blk(f):
                return {**f["blocking"], **((fresh.figure_blocking or {}).get(f["key"]) or {})}

            def fig_name(f):
                if not f["ref"]:
                    return f["name"]
                return f"{_char_names.get(f['ref'].character_id, f['ref'].character_id)} ({f['ref'].variant_id})"

            parts.append("figures: " + ", ".join(
                f"{fig_name(f)} at {round(blk(f)['x'])}% from left, "
                f"{depth(blk(f)['h'])}" for f in on_figs))
        else:
            parts.append("no characters in frame")
        live_props = [p["name"] for p in props if p["on"]]
        if live_props:
            parts.append("foreground props: " + ", ".join(live_props))
        pinned = [r for r in references if r["on"]]
        if pinned:
            parts.append(f"{len(pinned)} pinned reference image(s)")
        from helpers.compositor import is_placeholder
        real_letters = [t for t in ([n.text for n in board_narration] +
                                    [d.text for d in board_dialogue])
                        if t and not is_placeholder(t)]
        if letters["on"] and has_letters and real_letters:
            fresh_blk = (storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel).figure_blocking or {}
            placed = []
            for i, d in enumerate(board_dialogue[:4]):
                b = fresh_blk.get(f'balloon/{i}') or {}
                # unwritten placeholder balloons never reach the inker's brief
                if not b.get('on', 1) or is_placeholder(d.text):
                    continue
                desc = f"{d.character_id}'s {d.emphasis.value} balloon at {round(b.get('x', 50))}%"
                if b.get('tx') is not None:
                    desc += f" (tail aimed at {round(b['tx'])}%, {round(b.get('ty', 0))}% up)"
                placed.append(desc)
            parts.append("letter it AS BLOCKED on the table"
                         + (f" — {'; '.join(placed)}" if placed else ""))
        elif supports_letters:
            parts.append("leave it unlettered")
        noun = ("cover" if cover_mode
                else f"'{panel.name}' insert page" if insert_mode else "panel")
        post_user_message(state, f"Ink this rough into a new take of this {noun} — compose it with " +
                          "; ".join(parts) + ".")

    with ui.row().classes('w-full flex-nowrap light-columns').style('gap: 12px; align-items: stretch;'):
        stack_col = ui.column().classes('w-1/3 acetate-stack').style('gap: 4px; min-width: 220px;')
        stack_col._props['data-series'] = series_id
        stack_col._props['data-issue'] = panel.issue_id
        for k, v in board_attrs.items():
            stack_col._props[k] = v
        if locked:
            stack_col.classes('table-locked')
        with stack_col:
            if locked:
                with ui.row().classes('light-layer table-unlock w-full items-center flex-nowrap').style('gap: 6px;'):
                    ui.icon('lock').classes('text-lg').style('width: 40px; text-align: center;')
                    ui.label('The selected take is printed from this table') \
                        .classes('text-xs').style('overflow: hidden;')
                    ui.space()

                    def unlock():
                        fresh_board(storage, panel)
                        panel.image = None
                        storage.update_object(panel)
                        _receipt('🔓 unlocked the table — no take is selected while you rework it')
                        state.refresh_details()
                    ui.button('Unlock', icon='lock_open').props('outline dense size=sm') \
                        .on('click', lambda _: unlock())
            # the hand-skills placard teaches the gestures at the moment of
            # first selection — the standing hint stays short
            ui.label('top of the stack prints last — drag rows to restack; '
                     'pick a row or an acetate and the other lights up').classes('text-xs text-gray-500 italic')
            if has_letters:
                layer_row('chat_bubble',
                          'Letters — the page\'s letter blocks' if insert_mode
                          else 'Letters — balloons & captions', letters,
                          edit_message='I would like to work on the words of this page.'
                                       if insert_mode else
                                       'I would like to edit the narration and dialogue of this '
                                       + ('cover.' if cover_mode else 'panel.'))

                def letter_eye(key):
                    b = dict((panel.figure_blocking or {}).get(key) or {})
                    is_on = bool(b.get('on', 1))
                    btn = ui.button(icon='visibility' if is_on else 'visibility_off') \
                        .props('flat round dense size=xs')

                    def toggle(key=key, btn=btn):
                        fresh_board(storage, panel)
                        b = dict((panel.figure_blocking or {}).get(key) or {})
                        b['on'] = 0 if b.get('on', 1) else 1
                        panel.figure_blocking[key] = b
                        storage.update_object(panel)
                        btn.props(f"icon={'visibility' if b['on'] else 'visibility_off'}")
                        rough.refresh()
                    btn.on('click', toggle)

                from schema.dialog import DialogueEmphasis

                def remap_letter_blocking(prefix, removed_idx):
                    # keep blocking aligned when a letter is deleted mid-list
                    keys = sorted((k for k in (panel.figure_blocking or {}) if k.startswith(prefix)),
                                  key=lambda k: int(k.rsplit('/', 1)[1]))
                    vals = {k: panel.figure_blocking[k] for k in keys}
                    for k in keys:
                        panel.figure_blocking.pop(k, None)
                    for k, v in vals.items():
                        i = int(k.rsplit('/', 1)[1])
                        if i == removed_idx:
                            continue
                        panel.figure_blocking[f"{prefix}{i - 1 if i > removed_idx else i}"] = v

                def reassign_balloon(i, speaker):
                    panel.dialogue[i].character_id = speaker
                    storage.update_object(panel)
                    _receipt(f"🎙 handed a balloon to **{speaker.replace('-', ' ')}**")
                    state.refresh_details()

                cast_ids = list(dict.fromkeys(
                    [r.character_id for r in (panel.character_references or [])] +
                    [c.character_id for c in (getattr(scene, 'cast', None) or [])]))

                # THE MAILBAG'S LETTER ROWS: one row per letter block, with
                # its eye — the block's words live in the page description
                for i, btext in enumerate(board_blocks):
                    with ui.row().classes('light-layer w-full items-center flex-nowrap') \
                            .style('gap: 4px; margin-left: 14px; width: calc(100% - 14px);'):
                        letter_eye(f'letterblock/{i}')
                        ui.icon('drafts').classes('text-sm')
                        ui.label(btext.splitlines()[0][:34]).classes('text-xs') \
                            .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                        ui.space()

                for i, d in enumerate(board_dialogue[:4]):
                    with ui.row().classes('light-layer w-full items-center flex-nowrap') \
                            .style('gap: 4px; margin-left: 14px; width: calc(100% - 14px);'):
                        letter_eye(f'balloon/{i}')
                        ui.icon('chat_bubble').classes('text-sm')
                        others = [s for s in cast_ids if s != d.character_id]
                        if others:
                            # hand the balloon to another speaker in one click
                            spk = ui.button(d.character_id.replace('-', ' ')) \
                                .props('flat dense no-caps size=sm') \
                                .tooltip('Who speaks — click to hand this balloon to someone else')
                            with spk:
                                with ui.menu():
                                    for s in others:
                                        ui.menu_item(s.replace('-', ' '),
                                                     on_click=lambda _, s=s, i=i: reassign_balloon(i, s))
                        else:
                            ui.label(d.character_id.replace('-', ' ')).classes('text-xs text-bold')
                        ui.label(d.text[:22]) \
                            .classes('text-xs').style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                        ui.space()
                        sel = ui.select([e.value for e in DialogueEmphasis], value=d.emphasis.value) \
                            .props('dense borderless options-dense')

                        def restyle(e, i=i):
                            fresh_board(storage, panel)
                            panel.dialogue[i].emphasis = DialogueEmphasis(e.value)
                            storage.update_object(panel)
                            rough.refresh()
                        sel.on_value_change(restyle)

                        def drop_balloon(i=i):
                            fresh_board(storage, panel)
                            saved_dialogue = list(panel.dialogue)
                            saved_letters = {k: dict(v) for k, v in (panel.figure_blocking or {}).items()
                                             if k.startswith('balloon/') or k.startswith('caption/')}
                            panel.dialogue = [x for j, x in enumerate(panel.dialogue) if j != i]
                            remap_letter_blocking('balloon/', i)
                            storage.update_object(panel)

                            def undo():
                                # restore ONLY the letter blocking — figure
                                # moves made since the removal stay put
                                p = _fresh()
                                p.dialogue = saved_dialogue
                                merged = {k: v for k, v in (p.figure_blocking or {}).items()
                                          if not (k.startswith('balloon/') or k.startswith('caption/'))}
                                merged.update(saved_letters)
                                p.figure_blocking = merged
                                storage.update_object(p)
                            _receipt('✂️ removed a balloon', undo=undo)
                            state.refresh_details()
                        ui.button(icon='close').props('flat round dense size=xs') \
                            .tooltip('Remove this balloon').on('click', lambda _, i=i: drop_balloon(i))

                for pos in ('top', 'bottom'):
                    caps = [n for n in board_narration if n.position.value == pos]
                    for i, n in enumerate(caps[:2]):
                        with ui.row().classes('light-layer w-full items-center flex-nowrap') \
                                .style('gap: 4px; margin-left: 14px; width: calc(100% - 14px);'):
                            letter_eye(f'caption/{pos}/{i}')
                            ui.icon('notes').classes('text-sm')
                            ui.label(f"narrator: {n.text[:26]}").classes('text-xs') \
                                .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                            ui.space()

                            def drop_caption(n=n, pos=pos, i=i):
                                fresh_board(storage, panel)
                                saved_narration = list(panel.narration)
                                saved_letters = {k: dict(v) for k, v in (panel.figure_blocking or {}).items()
                                                 if k.startswith('balloon/') or k.startswith('caption/')}
                                panel.narration = [x for x in panel.narration if x is not n]
                                # keep caption blocking aligned, same as balloons
                                remap_letter_blocking(f'caption/{pos}/', i)
                                storage.update_object(panel)

                                def undo():
                                    # letter blocking only — see drop_balloon
                                    p = _fresh()
                                    p.narration = saved_narration
                                    merged = {k: v for k, v in (p.figure_blocking or {}).items()
                                              if not (k.startswith('balloon/') or k.startswith('caption/'))}
                                    merged.update(saved_letters)
                                    p.figure_blocking = merged
                                    storage.update_object(p)
                                _receipt('✂️ removed a narrator box', undo=undo)
                                state.refresh_details()
                            ui.button(icon='close').props('flat round dense size=xs') \
                                .tooltip('Remove this narrator box').on('click', lambda _, n=n: drop_caption(n))
            for p in props:
                layer_row('category', f"Foreground — {p['name']}", p)
            # THE STACK IS THE Z-ORDER: drag rows to restack (top prints
            # last); split products sit nested under their group.
            def mirror_btn(f):
                def flip(f=f):
                    fresh_board(storage, panel)
                    b = dict((panel.figure_blocking or {}).get(f["key"]) or {})
                    b['flip'] = 0 if b.get('flip') else 1
                    f["blocking"]['flip'] = b['flip']
                    panel.figure_blocking[f["key"]] = {**f["blocking"], **b}
                    storage.update_object(panel)
                    rough.refresh()
                ui.button(icon='swap_horiz').props('flat round dense size=xs') \
                    .classes('row-tool') \
                    .tooltip('Mirror left/right — the renderer often gets facing wrong') \
                    .on('click', lambda _, f=f: flip(f))

            def figure_row(f, indent=False):
                def cutout_btn(key, path, nm):
                    # an acetate with an opaque backdrop can't composite —
                    # offer the one-click cut-out right on its row
                    if not (path and _is_opaque(path)):
                        return

                    def make_cutout(key=key, path=path, nm=nm):
                        from helpers.render_queue import enqueue_renders
                        _receipt(f"✂️ cutting **{nm}** out of its backdrop — "
                                 f"the transparent acetate lands shortly")
                        enqueue_renders(state, [(
                            f"cut-out — {nm}",
                            lambda: make_cutout_body(state, panel, key, path, nm),
                        )], role='the Inker')
                    ui.button(icon='opacity').props('flat round dense size=xs color=orange') \
                        .classes('row-tool') \
                        .tooltip('Opaque backdrop — cut it out to TRUE transparency') \
                        .on('click', lambda _, k=key, p=path, n=nm: make_cutout(k, p, n))

                row = ui.row().classes('light-layer stack-row w-full items-center flex-nowrap') \
                    .style('gap: 6px;' + (' margin-left: 14px; width: calc(100% - 14px);' if indent else ''))
                row.props('draggable=true')
                row._props['data-key'] = f["key"]
                with row:
                    ui.icon('drag_indicator').classes('text-sm text-gray-400')
                    eye(f)
                    padlock(f)
                    if f["ref"] is None:
                        ui.image(source=_src(f["img"])).classes('light-thumb')
                        name_label = ui.label(f["name"].title()).classes('text-sm cursor-pointer') \
                            .tooltip('Rename this layer')

                        def _move_key(old_key, new_key):
                            # a layer's name IS its key: move image, blocking
                            # and group membership together
                            panel.figure_images[new_key] = panel.figure_images.pop(old_key)
                            if old_key in (panel.figure_blocking or {}):
                                panel.figure_blocking[new_key] = panel.figure_blocking.pop(old_key)
                            for g in list(panel.layer_groups or {}):
                                panel.layer_groups[g] = [new_key if k == old_key else k
                                                         for k in panel.layer_groups[g]]

                        def rename_element(key=f["key"], nm=f["name"]):
                            with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 360px;'):
                                ui.label('Rename this layer').classes('caption-box caption-box-sm')
                                inp = ui.input(value=nm).classes('w-full q-mt-sm') \
                                    .props('outlined dense autofocus')

                                def go():
                                    import re as _re
                                    fresh_board(storage, panel)
                                    new = (inp.value or '').strip()
                                    slug = _re.sub(r'[^a-z0-9]+', '-', new.lower()).strip('-')[:40]
                                    if not slug:
                                        ui.notify('Give the layer a name.', type='warning')
                                        return
                                    new_key = f'element/{slug}'
                                    if new_key == key:
                                        dlg.close()
                                        return
                                    if new_key in (panel.figure_images or {}):
                                        ui.notify('Another layer already has that name.', type='warning')
                                        return
                                    _move_key(key, new_key)
                                    storage.update_object(panel)
                                    _receipt(f"🏷 renamed the **{nm}** layer to **{new}**")
                                    dlg.close()
                                    state.refresh_details()
                                inp.on('keydown.enter', lambda _: go())
                                with ui.row().classes('w-full justify-end'):
                                    ui.button('Rename', icon='drive_file_rename_outline') \
                                        .props('unelevated dense').on('click', lambda _: go())
                            dlg.open()
                        name_label.on('click', lambda _, k=f["key"], n=f["name"]: rename_element(k, n))

                        def identify_element(key=f["key"], nm=f["name"]):
                            # link the cut-out to the asset it depicts: it
                            # becomes that character's posed acetate
                            with ui.dialog() as dlg, ui.card().classes('soft-card') \
                                    .style('min-width: 480px; max-width: 720px;'):
                                ui.label('Who is this?').classes('caption-box caption-box-sm')
                                ui.label('Link this cut-out to a cast member — it becomes their posed '
                                         'acetate, tied to their reference sheets.').classes('text-sm q-mt-sm')
                                with ui.row().classes('w-full q-mt-sm').style('gap: 8px;'):
                                    for ch in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
                                        for v in storage.read_all_objects(CharacterVariant, primary_key={
                                                "series_id": series_id, "character_id": ch.character_id}):
                                            img = storage.find_variant_image(
                                                series_id=series_id, character_id=ch.character_id, variant_id=v.id)
                                            with ui.card().classes('soft-card p-1 cursor-pointer') \
                                                    .style('width: 130px;') as card:
                                                if img and os.path.exists(img):
                                                    ui.image(source=img).style('height: 70px;').props('fit=contain')
                                                vname = getattr(v, 'name', None) or v.id
                                                ui.label(f"{ch.name.title()} · {vname}") \
                                                    .classes('text-xs text-center w-full')

                                            def link(ch=ch, v=v, key=key, nm=nm):
                                                fresh_board(storage, panel)
                                                fig_key = f"{ch.character_id}/{v.id}"
                                                replaced = fig_key in (panel.figure_images or {})
                                                _move_key(key, fig_key)
                                                if not any(c.character_id == ch.character_id and c.variant_id == v.id
                                                           for c in (panel.character_references or [])):
                                                    panel.character_references = (panel.character_references or []) + [
                                                        CharacterRef(series_id=series_id,
                                                                     character_id=ch.character_id, variant_id=v.id)]
                                                storage.update_object(panel)
                                                _receipt(f"🪪 identified **{nm}** as **{ch.name}** — the cut-out "
                                                         f"is now their acetate"
                                                         + (" (it replaces their previous one)" if replaced else ""))
                                                dlg.close()
                                                state.refresh_details()
                                            card.on('click', lambda _, ch=ch, v=v: link(ch, v))
                            dlg.open()
                        ui.button(icon='person_search').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Who is this?  Link this cut-out to a cast member') \
                            .on('click', lambda _, k=f["key"], n=f["name"]: identify_element(k, n))

                        def heal_element(path=f["img"], nm=f["name"]):
                            from gui.selection import SelectionItem, SelectedKind
                            itm = SelectionItem(name=f"Edit {nm}", id=path, kind=SelectedKind.IMAGE_EDITOR)
                            state.change_selection(new=[*state.selection, itm])
                        ui.button(icon='healing').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Take this element to the healing bench') \
                            .on('click', lambda _, p=f["img"], n=f["name"]: heal_element(p, n))
                        ui.button(icon='content_cut').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Split this element into ITS elements') \
                            .on('click', lambda _, k=f["key"], p=f["img"]: split_flow(k, p))

                        def dup_element(key=f["key"], path=f["img"], nm=f["name"]):
                            import shutil
                            fresh_board(storage, panel)
                            import re as _re
                            from uuid import uuid4
                            slug = _re.sub(r'[^a-z0-9]+', '-', nm.lower()).strip('-')[:36] or 'element'
                            n = 2
                            while f'element/{slug}-{n}' in (panel.figure_images or {}):
                                n += 1
                            new_key = f'element/{slug}-{n}'
                            new_path = os.path.join(os.path.dirname(path),
                                                    f'element--{slug}-{n}--{uuid4().hex[:8]}.png')
                            shutil.copyfile(path, new_path)
                            panel.figure_images[new_key] = new_path
                            b = dict((panel.figure_blocking or {}).get(key) or {})
                            b['x'] = min(120.0, float(b.get('x', 50)) + 8)   # land beside the original
                            panel.figure_blocking[new_key] = b
                            for g, ks in (panel.layer_groups or {}).items():
                                if key in ks:   # a copy joins its original's group
                                    ks.insert(ks.index(key), new_key)
                                    break
                            storage.update_object(panel)
                            _receipt(f"👯 duplicated the **{nm}** layer")
                            state.refresh_details()
                        ui.button(icon='content_copy').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Duplicate — another copy of this element on its own acetate') \
                            .on('click', lambda _, k=f["key"], p=f["img"], n=f["name"]: dup_element(k, p, n))
                        mirror_btn(f)
                        cutout_btn(f["key"], f["img"], f["name"])
                        ui.space()

                        def drop_element(key=f["key"], nm=f["name"]):
                            fresh_board(storage, panel)
                            saved_img = (panel.figure_images or {}).get(key)
                            saved_blk = (panel.figure_blocking or {}).get(key)
                            saved_groups = {g: list(ks) for g, ks in (panel.layer_groups or {}).items()}
                            panel.figure_images.pop(key, None)
                            panel.figure_blocking.pop(key, None)
                            for gname in list((panel.layer_groups or {})):
                                panel.layer_groups[gname] = [k for k in panel.layer_groups[gname] if k != key]
                                if not panel.layer_groups[gname]:
                                    panel.layer_groups.pop(gname)
                            storage.update_object(panel)

                            def undo():
                                p = _fresh()
                                if saved_img:
                                    p.figure_images[key] = saved_img
                                if saved_blk is not None:
                                    p.figure_blocking[key] = saved_blk
                                p.layer_groups = saved_groups
                                storage.update_object(p)
                            _receipt(f"✂️ removed **{nm}** from the table", undo=undo)
                            state.refresh_details()
                        ui.button(icon='close').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Remove this element from the table') \
                            .on('click', lambda _, k=f["key"], n=f["name"]: drop_element(k, n))
                        return

                    def pick_variant(ref=f["ref"]):
                        # click the acetate to swap which variant they wear
                        from gui.selection import SelectionItem, SelectedKind
                        itm = SelectionItem(name=_char_names.get(ref.character_id, ref.character_id),
                                            id=f"{series_id}/{ref.character_id}/{ref.variant_id}",
                                            kind=SelectedKind.CHARACTER_REFERENCE)
                        state.change_selection(new=[*state.selection, itm])

                    if f["img"]:
                        ui.image(source=_src(f["img"])).classes('light-thumb cursor-pointer') \
                            .tooltip('Swap their look (wardrobe variant)') \
                            .on('click', lambda _, ref=f["ref"]: pick_variant(ref))
                    else:
                        ui.icon('person').classes('text-lg').style('width: 40px; text-align: center;')
                    name_lbl = (_char_names.get(f["ref"].character_id)
                                or f["ref"].character_id.replace('-', ' ')).title()
                    # does this look have a sheet inked in THIS board's style?
                    _board_style = getattr(scene, 'style_id', None) if scene is not None \
                        else getattr(panel, 'style_id', None)
                    _sheet_missing = False
                    if _board_style:
                        from schema import CharacterVariant as _CV
                        _v = storage.read_object(_CV, {"series_id": series_id,
                            "character_id": f["ref"].character_id,
                            "variant_id": f["ref"].variant_id})
                        _keyed = (_v.images or {}).get(_board_style) if _v is not None else None
                        _sheet_missing = _v is not None and not (_keyed and os.path.exists(_keyed))
                    posing = pose_pending_key(panel, f["ref"].character_id, f["ref"].variant_id) \
                        in (getattr(state, '_poses_pending', None) or set())
                    ui.label(name_lbl + (' — posing…' if posing
                                         else ('' if f["posed"] else ' — unposed'))).classes('text-sm')
                    if posing:
                        # THE POSE IS ON THE DRAWING BOARD — say so, in place
                        ui.spinner('dots', size='1.2em', color='primary') \
                            .tooltip("On the drawing board — the acetate lands here when it's ready")
                    else:
                        ui.button(icon='accessibility_new').props('flat round dense size=xs') \
                            .tooltip('Pose this figure — describe the pose' if not f["posed"] else 'Re-pose — describe the new pose') \
                            .on('click', lambda _, r=f["ref"]: pose_dialog(r.character_id, r.variant_id))
                        if _sheet_missing and not locked:
                            def ink_sheet_here(r=f["ref"], sid=_board_style, nm=name_lbl):
                                from gui.messaging import post_user_message
                                post_user_message(state,
                                    f"Ink {nm}'s reference sheet in the {sid} style "
                                    f"(create_styled_image_for_character_variant for "
                                    f"character {r.character_id}, variant {r.variant_id}, "
                                    f"style {sid}).")
                            ui.button(icon='brush').props('flat round dense size=xs') \
                                .classes('row-tool') \
                                .tooltip(f"No sheet in this board's style yet — poses borrow "
                                         f"another style's sheet.  Ink {name_lbl}'s sheet in "
                                         f"this style.") \
                                .on('click', lambda _, fn=ink_sheet_here: fn())
                    mirror_btn(f)
                    if f["img"]:
                        cutout_btn(f["key"], f["img"], name_lbl)
                    if f["posed"]:
                        ui.button(icon='content_cut').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Split: lift props/wardrobe off this figure, revealing the character beneath') \
                            .on('click', lambda _, k=f["key"], p=f["img"]: split_flow(k, p))

                        def edit_acetate(path=f["img"], name=name_lbl):
                            from gui.selection import SelectionItem, SelectedKind
                            itm = SelectionItem(name=f"Edit {name} acetate", id=path,
                                                kind=SelectedKind.IMAGE_EDITOR)
                            state.change_selection(new=[*state.selection, itm])
                        ui.button(icon='healing').props('flat round dense size=xs') \
                            .classes('row-tool') \
                            .tooltip('Correct this acetate — fill in, fill out, replace details') \
                            .on('click', lambda _, p=f["img"], n=name_lbl: edit_acetate(p, n))
                    ui.space()

                    def uncast(ref=f["ref"]):
                        fresh_board(storage, panel)
                        panel.character_references = [
                            c for c in panel.character_references
                            if not (c.character_id == ref.character_id and c.variant_id == ref.variant_id)]
                        storage.update_object(panel)

                        def undo():
                            p = _fresh()
                            if not any(c.character_id == ref.character_id and c.variant_id == ref.variant_id
                                       for c in (p.character_references or [])):
                                p.character_references = (p.character_references or []) + [ref]
                                storage.update_object(p)
                        _receipt(f"✂️ removed **{_char_names.get(ref.character_id, ref.character_id)}** "
                                 f"from this panel", undo=undo)
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .mark('uncast').classes('row-tool') \
                        .tooltip('Take this figure off the table') \
                        .on('click', lambda _, ref=f["ref"]: uncast(ref))

            def flatten_group(gname):
                from uuid import uuid4
                fresh_board(storage, panel)
                from helpers.compositor import DIMS, base_canvas, paste_acetates
                # capture everything the flatten touches, for the undo chip
                saved_imgs = dict(panel.figure_images or {})
                saved_blk = {k: dict(v) for k, v in (panel.figure_blocking or {}).items()}
                saved_groups = {g: list(ks) for g, ks in (panel.layer_groups or {}).items()}
                saved_refs = list(panel.character_references or [])
                keys = list((panel.layer_groups or {}).get(gname, []))
                has_plate = 'background/plate' in keys
                fresh = storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel
                fkeys = {f["key"]: f for f in figures}
                live = [fkeys[k] for k in keys if k in fkeys
                        and ((fresh.figure_blocking or {}).get(k) or {}).get('on', 1)
                        and fkeys[k]["img"]]
                W, H = DIMS[panel.aspect.value]
                if has_plate:
                    plate_path = (panel.figure_images or {}).get('background/plate')
                    base = base_canvas(panel.aspect.value,
                                       plate_path if (plate_path and os.path.exists(plate_path)) else None)
                else:
                    base = base_canvas(panel.aspect.value, None, transparent=True)
                boxes = paste_acetates(base, panel.aspect.value,
                                       [(m["img"], {**m["blocking"],
                                                    **((fresh.figure_blocking or {}).get(m["key"]) or {})})
                                        for m in live])
                from storage.filepath import obj_to_imagepath
                figures_dir = os.path.join(os.path.dirname(obj_to_imagepath(obj=panel, base_path=storage.base_path)), 'figures')
                os.makedirs(figures_dir, exist_ok=True)
                # remove the members that were baked in (or discarded if hidden)
                for k in keys:
                    if k.startswith('element/') or k == 'background/plate':
                        panel.figure_images.pop(k, None)
                        panel.figure_blocking.pop(k, None)
                    elif '/' in k and not k.startswith('background'):
                        cid, vid = k.split('/', 1)
                        panel.character_references = [
                            c for c in panel.character_references
                            if not (c.character_id == cid and c.variant_id == vid)]
                        panel.figure_blocking.pop(k, None)
                panel.layer_groups.pop(gname, None)
                if has_plate:
                    out = os.path.join(figures_dir, f'plate--{uuid4().hex[:8]}.png')
                    base.save(out, 'PNG')
                    panel.figure_images['background/plate'] = out
                elif boxes:
                    L = max(0, min(b[0] for b in boxes)); T = max(0, min(b[1] for b in boxes))
                    R = min(W, max(b[2] for b in boxes)); B = min(H, max(b[3] for b in boxes))
                    crop = base.crop((int(L), int(T), int(R), int(B)))
                    import re as _re
                    slug = _re.sub(r'[^a-z0-9]+', '-', gname.lower()).strip('-')[:40] or 'flat'
                    out = os.path.join(figures_dir, f'element--{slug}--{uuid4().hex[:8]}.png')
                    crop.save(out, 'PNG')
                    key = f'element/{slug}'
                    panel.figure_images[key] = out
                    panel.figure_blocking[key] = {
                        'x': round((L + R) / 2 / W * 100, 1),
                        'y': round(100 - B / H * 100, 1),
                        'h': round((B - T) / H * 100, 1),
                        'z': max((m["blocking"].get('z', 0) for m in live), default=0)}
                storage.update_object(panel)

                def undo():
                    p = _fresh()
                    p.figure_images = saved_imgs
                    p.figure_blocking = saved_blk
                    p.layer_groups = saved_groups
                    p.character_references = saved_refs
                    storage.update_object(p)
                _receipt(f"🗜 combined the **{gname}** group into one acetate", undo=undo)
                state.refresh_details()

            fig_by_key = {f["key"]: f for f in figures}
            grouped_keys = set()
            display = []
            for gname, ks in (panel.layer_groups or {}).items():
                members = [fig_by_key[k] for k in ks if k in fig_by_key]
                if members:
                    display.append(('group', gname, members))
                    grouped_keys.update(m["key"] for m in members)
            for f in figures:
                if f["key"] not in grouped_keys:
                    display.append(('fig', None, [f]))
            display.sort(key=lambda it: -max(m["blocking"].get("z", 0) for m in it[2]))

            for kind_, gname, members in display:
                if kind_ == 'fig':
                    figure_row(members[0])
                    continue
                grow = ui.row().classes('light-layer stack-row w-full items-center flex-nowrap').style('gap: 6px;')
                grow.props('draggable=true')
                grow._props['data-key'] = f'group:{gname}'
                with grow:
                    ui.icon('drag_indicator').classes('text-sm text-gray-400')
                    has_plate_member = 'background/plate' in ((panel.layer_groups or {}).get(gname) or [])
                    all_on = any(m["on"] for m in members) or (has_plate_member and bg_layer["on"])
                    gbtn = ui.button(icon='visibility' if all_on else 'visibility_off') \
                        .props('flat round dense size=sm') \
                        .tooltip('Lift the whole group — every acetate in it')

                    def toggle_group(gname=gname, members=members, was_on=all_on):
                        fresh_board(storage, panel)
                        # the group eye rules EVERY member recursively — the
                        # split plate included
                        now = not was_on
                        for m in members:
                            m["on"] = now
                            cur = dict((panel.figure_blocking or {}).get(m["key"]) or {})
                            cur["on"] = 1 if now else 0
                            panel.figure_blocking[m["key"]] = cur
                        if 'background/plate' in ((panel.layer_groups or {}).get(gname) or []):
                            cur = dict((panel.figure_blocking or {}).get('background') or {})
                            cur["on"] = 1 if now else 0
                            panel.figure_blocking['background'] = cur
                        storage.update_object(panel)
                        state.refresh_details()   # member rows' eyes follow the group
                    gbtn.on('click', lambda _, g=gname, m=members, w=all_on: toggle_group(g, m, w))
                    padlock({"keys": [m["key"] for m in members]})
                    ui.icon('folder_open').classes('text-lg').style('width: 40px; text-align: center;')
                    glabel = ui.label(gname.title()).classes('text-sm text-bold cursor-pointer') \
                        .tooltip('Rename this group')

                    def rename_group(gname=gname):
                        with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 360px;'):
                            ui.label('Rename this group').classes('caption-box caption-box-sm')
                            inp = ui.input(value=gname).classes('w-full q-mt-sm') \
                                .props('outlined dense autofocus')

                            def go():
                                new = (inp.value or '').strip()
                                if not new or new == gname:
                                    dlg.close()
                                    return
                                if new in (panel.layer_groups or {}):
                                    ui.notify('Another group already has that name.', type='warning')
                                    return
                                panel.layer_groups = {(new if k == gname else k): v
                                                      for k, v in (panel.layer_groups or {}).items()}
                                storage.update_object(panel)
                                _receipt(f"🏷 renamed the **{gname}** group to **{new}**")
                                dlg.close()
                                state.refresh_details()
                            inp.on('keydown.enter', lambda _: go())
                            with ui.row().classes('w-full justify-end'):
                                ui.button('Rename', icon='drive_file_rename_outline') \
                                    .props('unelevated dense').on('click', lambda _: go())
                        dlg.open()
                    glabel.on('click', lambda _, g=gname: rename_group(g))
                    ui.space()

                    ui.button(icon='layers').props('flat round dense size=xs') \
                        .classes('row-tool') \
                        .tooltip('Combine this group into one acetate (hidden members are discarded)') \
                        .on('click', lambda _, g=gname: flatten_group(g))

                    def ungroup(gname=gname):
                        saved_members = list((panel.layer_groups or {}).get(gname) or [])
                        panel.layer_groups.pop(gname, None)
                        storage.update_object(panel)

                        def undo():
                            p = _fresh()
                            p.layer_groups[gname] = saved_members
                            storage.update_object(p)
                        _receipt(f"📂 ungrouped **{gname}**", undo=undo)
                        state.refresh_details()
                    ui.button(icon='folder_off').props('flat round dense size=xs') \
                        .classes('row-tool') \
                        .tooltip('Ungroup (the layers stay)') \
                        .on('click', lambda _, g=gname: ungroup(g))
                for m in sorted(members, key=lambda g: -g["blocking"].get("z", 0)):
                    figure_row(m, indent=True)
            for r in references:
                with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
                    eye(r)
                    ui.image(source=_src(r["img"])).classes('light-thumb')
                    ui.label(f"Reference — {os.path.basename(r['img'])}").classes('text-sm') \
                        .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                    ui.space()

                    def drop_reference(path=r["img"]):
                        # into the wastebasket, not gone: a dot-prefixed file
                        # disappears from listings and comes back on undo
                        from uuid import uuid4
                        trash = os.path.join(os.path.dirname(path),
                                             f".trash--{uuid4().hex[:6]}--{os.path.basename(path)}")
                        try:
                            os.replace(path, trash)
                        except OSError:
                            return

                        def undo():
                            # never clobber a newer same-named reference
                            dest = path
                            if os.path.exists(dest):
                                stem, ext = os.path.splitext(os.path.basename(path))
                                dest = os.path.join(os.path.dirname(path),
                                                    f"{stem}--{uuid4().hex[:6]}{ext}")
                            os.replace(trash, dest)
                        _receipt(f"✂️ took the reference **{os.path.basename(path)}** off the table", undo=undo)
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .tooltip('Take this reference off the table') \
                        .on('click', lambda _, p=r["img"]: drop_reference(p))

            def heal_background():
                from gui.selection import SelectionItem, SelectedKind
                nm = setting.name if setting is not None else 'the split background'
                itm = SelectionItem(name=f"Edit {nm} background", id=background,
                                    kind=SelectedKind.IMAGE_EDITOR)
                state.change_selection(new=[*state.selection, itm])

            def ink_master_here():
                style_id2 = getattr(scene, 'style_id', None) or 'vintage-four-color'
                from agentic.tools.imaging import generate_setting_background_body
                from helpers.render_queue import enqueue_renders
                _receipt(f"🖌 inking the **{setting.name}** master in {style_id2} — "
                         f"it lands on the table when it's done")
                enqueue_renders(state, [(
                    f"master background — {setting.name} in {style_id2} ({panel.aspect.value})",
                    lambda: generate_setting_background_body(state, series_id,
                                                             setting.setting_id, style_id2,
                                                             panel.aspect),
                )], role='the Background Artist')

            bg_label = f"Background — {setting.name if setting else 'no setting yet'}"
            if split_plate and background == split_plate:
                bg_label += " (split from the take)"
            elif setting is not None and bg_style_missing:
                if background is None:
                    bg_label += " — not inked in this style yet"
                else:
                    # borrowed: right style/wrong orientation, or another
                    # style entirely — either way the honest re-ink writes
                    # this board's OWN key and clobbers nothing
                    _sid = getattr(scene, 'style_id', None) or ''
                    _same_style = any((k == _sid or k.startswith(_sid + '/')) and v == background
                                      for k, v in (setting.images or {}).items()) if _sid else False
                    bg_label += (f" — borrowed; re-ink for this {panel.aspect.value} board"
                                 if _same_style else " (borrowed from another style)")
            with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
                eye(bg_layer)
                if background:
                    ui.image(source=_src(background)).classes('light-thumb cursor-pointer') \
                        .tooltip('Swap the background — pick another setting') \
                        .on('click', lambda _: pick_background())
                else:
                    ui.icon('landscape').classes('text-lg').style('width: 40px; text-align: center;')
                ui.label(bg_label).classes('text-sm').style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                if setting is not None and bg_style_missing:
                    if not background:
                        ui.space()
                    ui.button(icon='brush').props('flat round dense size=xs') \
                        .tooltip(f"Ink the {setting.name} master background in this board's style") \
                        .on('click', lambda _: ink_master_here())
                if background:
                    ui.space()
                    ui.button(icon='content_cut').props('flat round dense size=xs') \
                        .tooltip('Split this background into its elements (recognize, lift, repaint beneath)') \
                        .on('click', lambda _, p=background: split_flow('background', p))
                    ui.button(icon='healing').props('flat round dense size=xs') \
                        .tooltip('Heal or extend this background on the healing bench') \
                        .on('click', lambda _: heal_background())

            # LAY A NEW ACETATE: figures, props and backgrounds lay down in
            # ONE CLICK from a picker; letters go through the coauthor (they
            # need writing).
            def _receipt(text: str, undo=None):
                table_receipt(state, text, undo=undo)

            def _fresh():
                return storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel

            def _default_variant(cid):
                for r in (panel.character_references or []):
                    if r.character_id == cid:
                        return r.variant_id
                for r in (getattr(scene, 'cast', None) or []):
                    if r.character_id == cid:
                        return r.variant_id
                vs = list(storage.read_all_objects(CharacterVariant, primary_key={
                    "series_id": series_id, "character_id": cid}))
                return vs[0].variant_id if vs else 'default'

            def conjure_prop(name: str, description: str):
                """Create a prop asset and queue its reference art in this
                board's style; on covers the finished art lands on the table."""
                from agentic.tools.normalization import normalize_id
                from helpers.render_queue import enqueue_renders
                # REUSE, don't duplicate: a same-named prop already in the
                # shop is the asset the author means
                prop = next((p for p in storage.read_all_objects(
                                 PropAsset, primary_key={"series_id": series_id})
                             if normalize_id(p.name) == normalize_id(name)), None)
                if prop is None:
                    prop = PropAsset(prop_id=normalize_id(name), series_id=series_id,
                                     name=name, description=description or name)
                    storage.create_object(data=prop)
                if not cover_mode and scene is not None \
                        and not any(p.name == name for p in (scene.props or [])):
                    scene.props = (scene.props or []) + [Prop(name=name, description=description or name)]
                    storage.update_object(scene)
                style_id = getattr(scene, 'style_id', None) or 'vintage-four-color'

                def job(prop_id=prop.prop_id, style_id=style_id):
                    from agentic.tools.imaging import render_prop_reference_body
                    note = render_prop_reference_body(state, series_id, prop_id, style_id)
                    if cover_mode or insert_mode:
                        # the finished art lands straight on the board
                        fb = storage.read_object(cls=type(panel), primary_key=panel.primary_key)
                        pa2 = storage.read_object(cls=PropAsset, primary_key={
                            "series_id": series_id, "prop_id": prop_id})
                        img2 = ((pa2.images or {}).get(style_id)) if pa2 is not None else None
                        if fb is not None and img2 and os.path.exists(img2):
                            from agentic.tools.normalization import normalize_id as _nid
                            k = f'element/{_nid(pa2.name)}'
                            if k not in (fb.figure_images or {}):
                                fb.figure_images[k] = img2
                                fb.figure_blocking[k] = {"x": 50, "y": 6, "h": 28, "z": 55}
                                storage.update_object(fb)
                    return note
                enqueue_renders(state, [(f"prop reference — {name} in {style_id}", job)],
                                role='the Prop Maker')

            async def build_table_flow():
                """THE BRIEF BECOMES THE TABLE: break the written description
                into acetates — setting laid, figures posed as directed,
                elements conjured — with an approval pass first."""
                import asyncio
                from agentic.tools.imaging import breakdown_brief
                # a panel's brief is its BEAT + description — the action
                # usually lives in the beat, the visuals in the description
                beat = (getattr(panel, 'beat', '') or '').strip()
                brief = f"{beat}\n\n{(panel.description or '').strip()}".strip()
                if not brief:
                    ui.notify('Write the script or visual description first — the table is built from the brief.',
                              type='warning')
                    return
                # the click answers IMMEDIATELY, before the slow read starts
                ui.notify('📖 Reading the brief — breaking it into acetates…', type='info')
                pending = getattr(state, '_render_pending', None)
                if pending is None:
                    pending = []
                    state._render_pending = pending
                busy_label = 'breaking the brief into acetates'
                pending.append(busy_label)
                with ui.dialog().props('persistent') as busy, \
                        ui.card().classes('soft-card').style('min-width: 360px;'):
                    with ui.row().classes('items-center').style('gap: 12px;'):
                        ui.spinner('dots', size='2em', color='primary')
                        ui.label('Reading the brief — breaking it into acetates…').classes('text-sm')
                busy.open()
                try:
                    plan = await asyncio.to_thread(breakdown_brief, state, series_id, brief, cover_mode)
                finally:
                    busy.close()
                    try:
                        pending.remove(busy_label)
                    except ValueError:
                        pass
                if not plan or not (plan['figures'] or plan['elements']
                                    or plan['setting_id'] or plan['new_setting']):
                    ui.notify('The brief did not break down into acetates — add more visual detail.',
                              type='warning')
                    return

                cast_names = {c.character_id: c.name for c in storage.read_all_objects(
                    CharacterModel, primary_key={"series_id": series_id})}
                with ui.dialog() as dlg, ui.card().classes('soft-card') \
                        .style('min-width: 520px; max-width: 760px;'):
                    ui.label('Build the table from the brief').classes('caption-box caption-box-sm')
                    ui.label('Pick what to lay: figures go to the Penciller with the pose the brief '
                             'directs, elements are conjured as props, and everything lands here.') \
                        .classes('text-sm q-mt-sm')
                    checks = []
                    if plan['setting_id']:
                        s_obj = storage.read_object(cls=Setting, primary_key={
                            "series_id": series_id, "setting_id": plan['setting_id']})
                        if s_obj is not None:
                            checks.append(('setting', s_obj,
                                           ui.checkbox(f"Background — {s_obj.name}", value=True)))
                    elif plan['new_setting']:
                        ns = plan['new_setting']
                        checks.append(('new_setting', ns,
                                       ui.checkbox(f"NEW setting — {ns.get('name', 'unnamed')}", value=True)))
                    for f in plan['figures']:
                        nm2 = (cast_names.get(f['character_id']) or f['character_id']).title()
                        checks.append(('figure', f,
                                       ui.checkbox(f"Pose {nm2} — {str(f.get('pose', ''))[:70]}", value=True)))
                    for e in plan['elements']:
                        checks.append(('element', e,
                                       ui.checkbox(f"Conjure {e['name']} — {str(e.get('description', ''))[:60]}",
                                                   value=True)))
                    if cover_mode and plan['wants_masthead']:
                        checks.append(('masthead', None,
                                       ui.checkbox('Lay the series title masthead', value=True)))

                    def go():
                        dlg.close()
                        fresh_board(storage, panel)
                        laid = []
                        for kind2, item, cb in checks:
                            if not cb.value:
                                continue
                            if kind2 == 'setting':
                                lay_background_on_table(state, scene, panel, item)
                                laid.append(f"the {item.name} background")
                            elif kind2 == 'new_setting':
                                from agentic.tools.normalization import normalize_id as _nid
                                from agentic.tools.imaging import generate_setting_background_body
                                from helpers.render_queue import enqueue_renders
                                new_s = Setting(setting_id=_nid(item.get('name', 'set')), series_id=series_id,
                                                name=item.get('name', 'New Set'),
                                                description=item.get('description') or item.get('name', ''),
                                                interior=bool(item.get('interior')), props=[], images={})
                                storage.create_object(data=new_s)
                                lay_background_on_table(state, scene, panel, new_s)
                                style_id = getattr(scene, 'style_id', None) or 'vintage-four-color'
                                enqueue_renders(state, [(
                                    f"master background — {new_s.name} in {style_id} ({panel.aspect.value})",
                                    lambda sid2=new_s.setting_id, st2=style_id:
                                        generate_setting_background_body(state, series_id, sid2, st2,
                                                                         panel.aspect),
                                )], role='the Background Artist')
                                laid.append(f"the new {new_s.name} set")
                            elif kind2 == 'figure':
                                cid = item['character_id']
                                vid = _default_variant(cid)
                                if not any(c.character_id == cid and c.variant_id == vid
                                           for c in (panel.character_references or [])):
                                    panel.character_references = (panel.character_references or []) + [
                                        CharacterRef(series_id=series_id, character_id=cid, variant_id=vid)]
                                    storage.update_object(panel)
                                pose_figure_bg(state, panel, cid, vid, item.get('pose') or None)
                                laid.append(f"{cid.replace('-', ' ')} (posing)")
                            elif kind2 == 'element':
                                conjure_prop(item['name'], item.get('description') or '')
                                laid.append(f"{item['name']} (conjuring)")
                            elif kind2 == 'masthead':
                                lay_title()
                                laid.append('the masthead')
                        if laid:
                            _receipt('🛠 building the table from the brief — ' + ', '.join(laid))
                        state.refresh_details()
                    with ui.row().classes('w-full justify-end q-mt-sm'):
                        ui.button('Build the table', icon='auto_awesome').props('unelevated dense') \
                            .on('click', lambda _: go())
                dlg.open()

            def pick_figure():
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 720px;'):
                    ui.label('Lay a figure on the table').classes('caption-box caption-box-sm')
                    already = {(c.character_id, c.variant_id) for c in (panel.character_references or [])}
                    with ui.row().classes('w-full').style('gap: 8px;'):
                        for ch in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
                            for v in storage.read_all_objects(CharacterVariant, primary_key={"series_id": series_id, "character_id": ch.character_id}):
                                if (ch.character_id, v.id) in already:
                                    continue
                                img = storage.find_variant_image(series_id=series_id, character_id=ch.character_id, variant_id=v.id)
                                with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 130px;') as card:
                                    if img and os.path.exists(img):
                                        ui.image(source=img).style('height: 70px;').props('fit=contain')
                                    vname = getattr(v, 'name', None) or v.id
                                    ui.label(f"{ch.name.title()} · {vname}").classes('text-xs text-center w-full')

                                def lay(ch=ch, v=v):
                                    dlg.close()
                                    lay_figure_on_table(state, panel, ch.character_id, v.id, ch.name)
                                card.on('click', lambda _, ch=ch, v=v: lay(ch, v))
                dlg.open()

            def pick_background():
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 720px;'):
                    ui.label('Lay a background on the table').classes('caption-box caption-box-sm')
                    with ui.row().classes('w-full').style('gap: 8px;'):
                        for s in storage.read_all_objects(Setting, primary_key={"series_id": series_id}, order_by="name"):
                            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
                            with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 150px;') as card:
                                if img:
                                    ui.image(source=img).style('height: 80px;').props('fit=cover')
                                ui.label(s.name.title()).classes('text-xs text-center w-full')

                            def lay(s=s):
                                dlg.close()
                                lay_background_on_table(state, scene, panel, s)
                            card.on('click', lambda _, s=s: lay(s))

                    # BUILD A NEW SET right from the board: name it, sketch
                    # it, and its master background goes straight to the
                    # drawing board in this board's style
                    ui.label('…or build a new set').classes('caption-box caption-box-sm q-mt-md')
                    s_nm = ui.input(placeholder='Name the setting — e.g. The Hall of Mirrors') \
                        .props('outlined dense').classes('w-full')
                    s_desc = ui.textarea(placeholder='Describe it: architecture, light, mood, era…') \
                        .props('outlined dense rows=2').classes('w-full')
                    s_int = ui.switch('interior', value=False).props('dense')

                    def build_set():
                        from agentic.tools.normalization import normalize_id as _nid
                        name = (s_nm.value or '').strip()
                        if not name:
                            ui.notify('Name the setting first.', type='warning')
                            return
                        new_s = Setting(setting_id=_nid(name), series_id=series_id, name=name,
                                        description=(s_desc.value or '').strip() or name,
                                        interior=bool(s_int.value), props=[], images={})
                        storage.create_object(data=new_s)
                        dlg.close()
                        lay_background_on_table(state, scene, panel, new_s)
                        style_id = getattr(scene, 'style_id', None) or 'vintage-four-color'
                        from agentic.tools.imaging import generate_setting_background_body
                        from helpers.render_queue import enqueue_renders
                        enqueue_renders(state, [(
                            f"master background — {name} in {style_id} ({panel.aspect.value})",
                            lambda: generate_setting_background_body(state, series_id,
                                                                     new_s.setting_id, style_id,
                                                                     panel.aspect),
                        )], role='the Background Artist')
                    ui.button('Build the set & ink its master', icon='construction') \
                        .props('unelevated dense no-caps').classes('q-mt-sm') \
                        .on('click', lambda _: build_set())
                dlg.open()

            def pick_prop():
                from agentic.tools.normalization import normalize_id
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 720px;'):
                    ui.label('Lay a prop on the table').classes('caption-box caption-box-sm')
                    already = {p.name for p in (getattr(scene, 'props', None) or [])}
                    with ui.row().classes('w-full q-mt-sm').style('gap: 8px;'):
                        for pa in storage.read_all_objects(PropAsset, primary_key={"series_id": series_id}, order_by="name"):
                            if not cover_mode and pa.name in already:
                                continue
                            img = next((i for i in (pa.images or {}).values() if i and os.path.exists(i)), None)
                            with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 130px;') as card:
                                if img:
                                    ui.image(source=img).style('height: 70px;').props('fit=contain')
                                ui.label(pa.name.title()).classes('text-xs text-center w-full')

                            def lay(pa=pa):
                                dlg.close()
                                if cover_mode or insert_mode:
                                    # covers and inserts have no scene props:
                                    # the art itself lands as an acetate
                                    lay_prop_acetate(state, panel, pa, getattr(scene, 'style_id', None))
                                else:
                                    # the prop joins the scene's record (the
                                    # render prompt reads it) AND its art
                                    # lands as a blockable acetate
                                    lay_prop_on_table(state, scene, pa)
                                    lay_prop_acetate(state, panel, pa, getattr(scene, 'style_id', None))
                            card.on('click', lambda _, pa=pa: lay(pa))

                    # CONJURE A NEW PROP from a prompt, right on the board —
                    # the asset is created, its reference art goes to the
                    # drawing board in this board's style
                    ui.label('…or conjure a new prop').classes('caption-box caption-box-sm q-mt-md')
                    nm = ui.input(placeholder='Name it — e.g. cracked crystal ball') \
                        .props('outlined dense').classes('w-full')
                    desc = ui.textarea(placeholder='Describe it: size, materials, colors, wear…') \
                        .props('outlined dense rows=2').classes('w-full')

                    def conjure():
                        name = (nm.value or '').strip()
                        if not name:
                            ui.notify('Name the prop first.', type='warning')
                            return
                        dlg.close()
                        conjure_prop(name, (desc.value or '').strip())
                        _receipt(f"🎪 conjured the **{name}** prop — its reference art "
                                 f"is on the drawing board…")
                        state.refresh_details()
                    ui.button('Conjure & ink its reference', icon='auto_fix_high') \
                        .props('unelevated dense no-caps').classes('q-mt-sm') \
                        .on('click', lambda _: conjure())
                dlg.open()

            with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 2px;'):
                ui.label('lay a new acetate:').classes('text-xs text-gray-500')
                ui.button(icon='auto_awesome').props('flat round dense size=sm') \
                    .tooltip('BUILD THE TABLE FROM THE BRIEF — the description becomes acetates: '
                             'setting laid, figures posed as written, elements conjured') \
                    .on('click', lambda _: build_table_flow())
                ui.button(icon='person_add').props('flat round dense size=sm') \
                    .tooltip('A figure — one click from the cast').on('click', lambda _: pick_figure())
                ui.button(icon='category').props('flat round dense size=sm') \
                    .tooltip('A prop — from the prop shop, or conjure a brand-new one') \
                    .on('click', lambda _: pick_prop())
                ui.button(icon='landscape').props('flat round dense size=sm') \
                    .tooltip('A background — one click from the settings').on('click', lambda _: pick_background())
                if cover_mode or insert_mode:
                    # THE MASTHEAD: lay the series title art as an acetate —
                    # art-only covers (and posters, and ads) wear the title
                    # as a composited overlay
                    def lay_title():
                        fresh_board(storage, panel)
                        from schema import Series as _Series
                        ser = storage.read_object(cls=_Series, primary_key={"series_id": series_id})
                        arts = (getattr(ser, 'title_images', {}) or {}) if ser else {}
                        art = arts.get(getattr(scene, 'style_id', None)) or next(
                            (i for i in arts.values() if i and os.path.exists(i)), None)
                        if not (art and os.path.exists(art)):
                            ui.notify("No title art yet — letter the series masthead first "
                                      "(it lives on the series page).", type='warning')
                            return
                        panel.figure_images['element/series-title'] = art
                        panel.figure_blocking['element/series-title'] = {"x": 50, "y": 68, "h": 24, "z": 60}
                        storage.update_object(panel)
                        _receipt('🏷 laid the series title masthead on the table')
                        state.refresh_details()
                    ui.button(icon='title').props('flat round dense size=sm') \
                        .tooltip(f'The series title masthead — lay it on this '
                                 f'{"cover" if cover_mode else "page"} as an acetate') \
                        .on('click', lambda _: lay_title())

                    # THE PUBLISHER'S MARK: the little logo every cover wears
                    def lay_publisher_mark():
                        fresh_board(storage, panel)
                        from schema import Publisher, Series as _Series
                        ser = storage.read_object(cls=_Series, primary_key={"series_id": series_id})
                        pub = storage.read_object(cls=Publisher, primary_key={
                            "publisher_id": ser.publisher_id}) \
                            if (ser is not None and ser.publisher_id) else None
                        art = pub.image if (pub is not None and pub.image
                                            and os.path.exists(pub.image)) else None
                        if art is None:
                            ui.notify("No publisher logo yet — generate one on the "
                                      "publisher page first.", type='warning')
                            return
                        panel.figure_images['element/publisher-mark'] = art
                        panel.figure_blocking['element/publisher-mark'] = {"x": 10, "y": 82, "h": 12, "z": 61}
                        storage.update_object(panel)
                        _receipt(f"🔖 laid the publisher's mark on {board_label(panel)}")
                        state.refresh_details()
                    ui.button(icon='workspace_premium').props('flat round dense size=sm') \
                        .tooltip(f'The publisher\'s mark — lay the logo on this '
                                 f'{"cover" if cover_mode else "page"} as an acetate') \
                        .on('click', lambda _: lay_publisher_mark())
                def new_letters():
                    from schema.dialog import Dialogue, Narration, DialogueEmphasis, NarrationPosition
                    with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 380px;'):
                        ui.label('New letters').classes('caption-box caption-box-sm')

                        def new_balloon(speaker: str):
                            fresh_board(storage, panel)
                            panel.dialogue = list(panel.dialogue or []) + [
                                Dialogue(character_id=speaker, text='Say something…',
                                         emphasis=DialogueEmphasis.CHAT)]
                            storage.update_object(panel)
                            _receipt(f"💬 laid a balloon for **{speaker}** — double-click it to write")
                            dlg.close()
                            state.refresh_details()

                        def new_caption():
                            fresh_board(storage, panel)
                            panel.narration = list(panel.narration or []) + [
                                Narration(text='Narration…', position=NarrationPosition.TOP)]
                            storage.update_object(panel)
                            _receipt("💬 laid a narrator box — double-click it to write")
                            dlg.close()
                            state.refresh_details()

                        speakers = [r.character_id for r in (panel.character_references or [])]
                        if not speakers:
                            speakers = [c.character_id for c in (getattr(scene, 'cast', None) or [])]
                        if speakers:
                            ui.label('A balloon — who speaks?').classes('text-sm q-mt-sm')
                            with ui.row().style('gap: 4px;'):
                                for s in dict.fromkeys(speakers):
                                    ui.chip(s.replace('-', ' ')).props('dense clickable outline') \
                                        .on('click', lambda _, s=s: new_balloon(s))
                        ui.button('A narrator box', icon='notes').props('outline dense') \
                            .classes('q-mt-sm').on('click', lambda _: new_caption())
                        ui.label('Then double-click the letters on the rough to write in place; '
                                 'the Letterer inks them when you ink the rough.') \
                            .classes('text-xs text-gray-500 q-mt-sm')
                    dlg.open()

                if supports_letters:   # panels AND covers letter on the table
                    ui.button(icon='chat_bubble').props('flat round dense size=sm') \
                        .tooltip('Letters — lay a balloon or narrator box on the table') \
                        .on('click', lambda _: new_letters())

            # or just drop an image straight onto the table as a reference
            with ui.row().classes('light-layer w-full items-center justify-center relative overflow-hidden').style('min-height: 34px;'):
                def on_drop_reference(e):
                    storage.upload_reference_image(panel, e.name, e.content, e.type)
                    state.refresh_details()
                ui.upload(on_upload=on_drop_reference, auto_upload=True, max_files=1) \
                    .classes('absolute inset-0 opacity-0 cursor-pointer z-10')
                ui.label('…or drop a reference image on the table').classes('text-xs text-gray-500')

            def flatten_bytes() -> bytes:
                import io
                from helpers.compositor import base_canvas, paste_acetates, collect_letters, paste_letters
                fresh = storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel
                base = base_canvas(panel.aspect.value,
                                   background if (bg_layer["on"] and background) else None)
                live = [f for f in figures if f["on"] and f["img"]]
                paste_acetates(base, panel.aspect.value,
                               [(f["img"], {**f["blocking"],
                                            **((fresh.figure_blocking or {}).get(f["key"]) or {})})
                                for f in live])
                # letters print last, comic-craft order (placeholders never do)
                if letters["on"]:
                    paste_letters(base, panel.aspect.value, collect_letters(fresh))
                buf = io.BytesIO()
                base.save(buf, 'PNG')
                return buf.getvalue()

            def flatten_dialog():
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 420px;'):
                    ui.label('Flatten the table').classes('caption-box caption-box-sm')
                    ui.label('Composite the visible acetates into one image and save it as…') \
                        .classes('text-sm q-mt-sm')

                    def as_take():
                        fresh_board(storage, panel)
                        data = flatten_bytes()
                        locator = storage.upload_binary_image(obj=panel, data=data)
                        panel.image = locator
                        storage.update_object(panel)
                        _receipt('🗜 flattened the table into a new take')
                        dlg.close()
                        state.refresh_details()

                    def as_reference():
                        import io as _io
                        data = flatten_bytes()
                        bid = panel.cover_id if cover_mode else panel.insert_id if insert_mode else panel.panel_id
                        storage.upload_reference_image(panel, f"flattened-{bid[:6]}.png",
                                                       _io.BytesIO(data), 'image/png')
                        _receipt('🗜 flattened the table onto a reference acetate')
                        dlg.close()
                        state.refresh_details()

                    def as_master():
                        data = flatten_bytes()
                        locator = storage.upload_binary_image(obj=setting, data=data)
                        from helpers.masters import master_key
                        setting.images[master_key(scene.style_id, panel.aspect)] = locator
                        storage.update_object(setting)
                        _receipt(f"🗜 flattened the table into a new master background for **{setting.name}**")
                        dlg.close()
                        state.refresh_details()

                    with ui.column().classes('w-full q-mt-sm').style('gap: 6px;'):
                        ui.button(f'A new take of {board_label(panel)}', icon='filter_frames').props('unelevated dense') \
                            .classes('w-full').on('click', lambda _: as_take())
                        ui.button(f'A reference on {board_label(panel)}', icon='attachment').props('outline dense') \
                            .classes('w-full').on('click', lambda _: as_reference())
                        if setting is not None and scene is not None and scene.style_id:
                            ui.button(f"The master background for {setting.name.title()}", icon='landscape') \
                                .props('outline dense').classes('w-full').on('click', lambda _: as_master())
                dlg.open()

            # THE INK BAR RIDES ALONG: pinned to the bottom of the pane so
            # the main action never scrolls out of reach
            with ui.row().classes('q-mt-sm ink-bar').style('gap: 8px;'):
                ui.button('Ink this rough', icon='brush').props('unelevated dense') \
                    .on('click', lambda _: ink())
                ui.button('Flatten', icon='layers').props('outline dense') \
                    .tooltip('Composite the visible acetates into one image and save it as a new asset') \
                    .on('click', lambda _: flatten_dialog())
        with ui.column().style('flex: 1 1 0; min-width: 0;'):
            with ui.row().classes('w-full items-center flex-nowrap').style('gap: 4px;'):
                ui.label('THE ROUGH').classes('comic-label-sm')

                # THE STYLE SWATCH: taped to the board like a printer's color
                # chip — the style every take printed here wears (locked
                # tables keep their arrangement; unlock to reshape/restyle)
                if scene is not None:
                    sw = style_swatch(state, scene,
                                      shared_with=None if (cover_mode or insert_mode)
                                      else 'the whole scene')
                    if locked:
                        sw.classes('table-locked')
                ui.space()
                # the frame's SHAPE, switched right on the rough — panels
                # come in landscape/portrait/square; covers only landscape
                # or portrait
                from schema import FrameLayout as _FL

                def reshape(shape):
                    fresh_board(storage, panel)
                    panel.aspect = shape
                    storage.update_object(panel)
                    state.refresh_details()
                shapes = [('crop_landscape', _FL.LANDSCAPE, 'Landscape frame'),
                          ('crop_portrait', _FL.PORTRAIT, 'Portrait frame')]
                if not cover_mode and not insert_mode:
                    shapes.append(('crop_square', _FL.SQUARE, 'Square frame'))
                if insert_mode:
                    shapes = []   # a full page is portrait, always
                for icon, shape, tip in shapes:
                    b = ui.button(icon=icon).props('flat round dense size=sm')
                    if panel.aspect == shape:
                        b.props('color=primary')
                    if locked and panel.aspect != shape:
                        b.props('disable')
                        b.tooltip(f'{tip} — unlock the table to reshape')
                    else:
                        b.tooltip(tip)
                        b.on('click', lambda _, s=shape: reshape(s))
            rough()
            # THE BRIEF: the same margin notes under every rough — panel,
            # cover, or insert page — the words the render is drawn from
            from gui.elements import markdown_field_editor
            markdown_field_editor(state, description_label, panel.description, header_size=3)
        # an EXPLODED take auto-opens the split flow on its fresh plate
        if getattr(state, '_auto_split_board', None) == panel.id and split_plate:
            state._auto_split_board = None
            ui.timer(0.6, lambda: split_flow('background', split_plate), once=True)

        if featured is not None:
            with ui.column().style('flex: 1 1 0; min-width: 0;'):
                ui.label('THE PRINT').classes('comic-label-sm')
                with ui.element('div').classes('rough-canvas').style(canvas_style):
                    ui.image(source=_src(featured)).props('fit=cover') \
                        .classes('absolute inset-0 w-full h-full')
                    if actions:
                        with ui.row().classes('absolute top-1 right-1 z-10 items-center').style('gap: 4px;'):
                            for icon, tip, handler in actions:
                                ui.button(icon=icon).props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip(tip).on('click.stop', handler)
