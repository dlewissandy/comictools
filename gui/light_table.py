"""
THE LIGHT TABLE: compose a panel's take from acetate layers, stacked in
comic-craft order — letters over foreground over figures over background.
The right side shows THE ROUGH: a live penciller's mock assembled from the
parts.  Toggle a layer's eye to lift its acetate off the table; slide a
figure left/center/right to block the shot; then INK the rough — the
composition goes to the coauthor to render as a real take.
"""
import os

from loguru import logger
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
    // A POINTERUP WE NEVER SAW: if NO button is held yet we still think we are
    // dragging/resizing, the release landed on something outside the canvas
    // that swallowed the event.  Stop now — persist where it ended — so a mere
    // hover over anything outside the lightbox never moves or resizes an acetate.
    if ((drag || resize || tailDrag) && e.buttons === 0) {
      if (drag) { drag.fig.style.zIndex = drag.z; if (drag.live) report(drag.fig, drag.canvas); }
      else if (resize) report(resize.fig, resize.canvas);
      else if (tailDrag) report(tailDrag.fig, tailDrag.canvas);
      drag = resize = tailDrag = null;
      return;
    }
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
      artboard: canvas.dataset.artboard, scope: canvas.dataset.scope,
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
      insert: stack.dataset.insert,
      artboard: stack.dataset.artboard, scope: stack.dataset.scope});
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
  // find the uploader for a drop: the closest one, OR one nested inside the
  // card the drop landed on (a caption overlay steals `closest`, so we look
  // INSIDE the card too — every 'drop image to create' card now catches it)
  const uploaderFor = (target) => {
    if (!target || !target.closest) return null;
    let zone = target.closest('.q-uploader');
    if (zone) return zone;
    const host = target.closest('.q-card, .mosaic-card, .create-drop, .table-drop-zone, .insert-drop-sheet');
    return host ? host.querySelector('.q-uploader') : null;
  };
  // the visible outline goes on the element the user sees: the uploader
  // when it's the face of the zone, the host row when the uploader hides
  const dropFaceFor = (target) => {
    const zone = uploaderFor(target);
    if (!zone) return null;
    const host = zone.closest('.table-drop-zone');
    return host || zone;
  };
  document.addEventListener('dragover', (e) => {
    const t = e.dataTransfer && e.dataTransfer.types;
    if (!(t && Array.prototype.includes.call(t, 'Files'))) return;
    e.preventDefault();
    document.querySelectorAll('.drop-ready').forEach(z => z.classList.remove('drop-ready'));
    const face = dropFaceFor(e.target);
    if (face) face.classList.add('drop-ready');
  });
  document.addEventListener('dragleave', (e) => {
    const face = dropFaceFor(e.target);
    if (face) face.classList.remove('drop-ready');
  });
  document.addEventListener('drop', (e) => {
    if (!(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) return;
    e.preventDefault();
    document.querySelectorAll('.drop-ready').forEach(z => z.classList.remove('drop-ready'));
    const zone = uploaderFor(e.target);
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

  // ROBUST DROP-TO-CREATE: a create card (.create-drop-zone) reads its
  // dropped/browsed image with a FileReader and EMITS it — the proven path
  // the clipboard paste uses — because the q-uploader overlay never
  // delivered files (no click, no drop) in this app.
  const emitAssetDrop = (zone, file) => {
    if (!file || !(file.type||'').startsWith('image/')) return;
    const r = new FileReader();
    r.onload = () => emitEvent('asset_drop', {
      kind: zone.dataset.kind, series: zone.dataset.series,
      character: zone.dataset.character || '', variant: zone.dataset.variant || '',
      name: file.name, data: r.result});
    r.readAsDataURL(file);
  };
  document.addEventListener('dragover', (e) => {
    const zone = e.target.closest && e.target.closest('.create-drop-zone');
    if (zone && e.dataTransfer) { e.preventDefault(); zone.classList.add('drop-ready'); }
  });
  document.addEventListener('dragleave', (e) => {
    const zone = e.target.closest && e.target.closest('.create-drop-zone');
    if (zone) zone.classList.remove('drop-ready');
  });
  document.addEventListener('drop', (e) => {
    const zone = e.target.closest && e.target.closest('.create-drop-zone');
    if (!zone) return;
    zone.classList.remove('drop-ready');
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (!f) return;
    e.preventDefault();
    emitAssetDrop(zone, f);
  }, true);
  document.addEventListener('click', (e) => {
    if (e.target.closest && e.target.closest('.caption-btn, .create-caption-btn, button')) return;
    const zone = e.target.closest && e.target.closest('.create-drop-zone');
    if (zone) { const inp = zone.querySelector('.create-drop-input'); if (inp) inp.click(); return; }
    // a q-uploader only browses from its own tiny header button — clicking
    // anywhere on a drop card or the table's drop row must open the picker
    const drop = e.target.closest && e.target.closest('.drop-card, .table-drop-zone');
    if (drop) { const inp = drop.querySelector('.q-uploader input[type=file]'); if (inp) inp.click(); }
  });
  document.addEventListener('change', (e) => {
    const inp = e.target;
    if (inp && inp.classList && inp.classList.contains('create-drop-input') && inp.files && inp.files[0]) {
      const zone = inp.closest('.create-drop-zone');
      if (zone) emitAssetDrop(zone, inp.files[0]);
      inp.value = '';
    }
  });

  // double-click a balloon or caption: edit the words IN PLACE
  document.addEventListener('dblclick', (e) => {
    const fig = e.target.closest('.rough-drag');
    if (!fig || !fig.dataset.kind || fig.dataset.kind === 'figure') return;
    const canvas = fig.closest('.rough-canvas');
    if (canvas && canvas.dataset.locked) return;   // the table is locked
    // trade dress prints from the ISSUE's metadata — editing the stamp in
    // place would be discarded at the next paint, so the dblclick asks the
    // Editor to change the source of truth instead
    if ((fig.dataset.key || '').startsWith('dress/')) {
      e.preventDefault();
      emitEvent('dress_ask', {key: fig.dataset.key});
      return;
    }
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


def is_artboard(board) -> bool:
    """A mark — a series masthead or a house logo — composing on the bench."""
    return hasattr(board, 'board_kind')


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
    if is_artboard(board):
        return f"the {board.name} mark"
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
        # THE WORDS TOO: balloons/captions/the brief also persist out-of-band
        # (dblclick-edit on the rough) — a stale copy here would write the
        # OLD words back over what the author just typed
        for attr in ('dialogue', 'narration', 'description'):
            if hasattr(fresh, attr):
                setattr(board, attr, getattr(fresh, attr))
    return board


def current_board(state):
    """The board the user is looking at — panel, cover, insert or a mark
    (masthead/logo art board) — else None."""
    from schema import Panel, Cover, Insert, ArtBoard
    sel = state.selection or []
    if not sel:
        return None
    ids = {}
    for item in sel:
        k = item.kind.value
        if k == 'series':
            ids = {'series_id': item.id}
        elif k == 'publisher':
            ids = {'publisher_id': item.id}
        elif k == 'issue':
            ids['issue_id'] = item.id
        elif k == 'scene':
            ids['scene_id'] = item.id
        elif k == 'panel':
            ids['panel_id'] = item.id
        elif k == 'cover':
            ids['cover_id'] = item.id
        elif k == 'insert':
            ids['insert_id'] = item.id
        elif k == 'artboard':
            ids['board_id'] = item.id
    last = sel[-1].kind.value
    if last == 'panel' and {'series_id', 'issue_id', 'scene_id', 'panel_id'} <= ids.keys():
        return state.storage.read_object(cls=Panel, primary_key={
            k: ids[k] for k in ('series_id', 'issue_id', 'scene_id', 'panel_id')})
    if last == 'cover' and {'series_id', 'issue_id', 'cover_id'} <= ids.keys():
        return state.storage.read_object(cls=Cover, primary_key={
            k: ids[k] for k in ('series_id', 'issue_id', 'cover_id')})
    if last == 'insert' and {'series_id', 'issue_id', 'insert_id'} <= ids.keys():
        return state.storage.read_object(cls=Insert, primary_key={
            k: ids[k] for k in ('series_id', 'issue_id', 'insert_id')})
    if last == 'artboard' and 'board_id' in ids:
        # a mark's scope is whoever owns it: the series (masthead) or the
        # house (logo) standing just before it on the trail
        scope = ids.get('series_id') or ids.get('publisher_id')
        if scope:
            return state.storage.read_object(cls=ArtBoard, primary_key={
                'scope_id': scope, 'board_id': ids['board_id']})
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
    from gui.elements import studio_dialog
    with studio_dialog('Pasted image', min_w=380) as dlg:
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
    """Resolve a rough/stack event back to its board (panel, cover, insert
    or an art board — a masthead/logo mark)."""
    if a.get('artboard'):
        from schema import ArtBoard as _AB
        return storage.read_object(cls=_AB, primary_key={
            "scope_id": a['scope'], "board_id": a['artboard']})
    if a.get('cover'):
        from schema import Cover as _Cover
        return storage.read_object(cls=_Cover, primary_key={
            "series_id": a['series'], "issue_id": a['issue'], "cover_id": a['cover']})
    if a.get('insert'):
        from schema import Insert as _Insert
        return storage.read_object(cls=_Insert, primary_key={
            "series_id": a['series'], "issue_id": a['issue'], "insert_id": a['insert']})
    # a malformed event (a board kind whose ids never rode the payload)
    # must land as a no-op, never a KeyError that eats the drag
    if not (a.get('scene') and a.get('panel')):
        return None
    from schema import Panel as _Panel
    return storage.read_object(cls=_Panel, primary_key={
        "series_id": a['series'], "issue_id": a['issue'],
        "scene_id": a['scene'], "panel_id": a['panel']})


# ---------------------------------------------------------------------------
# LAYING ASSETS ON THE TABLE: one-click direct writes, shared by the table's
# own pickers AND the assets drawer (a drawer tile lays its asset right here
# when a panel is open — the drawer IS part of the table).
# ---------------------------------------------------------------------------

def shape_picker(state, storage, panel, *, receipt):
    """THE ONE SHAPE PICKER (the author's ruling): the same control in the
    open book's tile menu and on the panel's own page.  Its boxes are
    GENERATED from the flow's law (size_mult × the 6-wide page) — the menu
    can never drift from what the stitcher lays (that's how 6×6 arrives).

    Pick a box → the panel HOLDS that exact shape+size, the book reflows.
    AUTO → released; the flow may flex the shape to fill the page.
    The lit box is what the page PRINTS; when auto flexed the panel, the
    words say both truths.  A reshape that leaves the selected proof the
    wrong shape UNSELECTS it (repack_page enforces this) — the author
    decides: re-proof, or re-feature a take."""
    from schema import FrameLayout, Page as _Page
    import helpers.stitcher as _st

    laid = _st.laid_aspect(storage, panel).value
    held = bool(getattr(panel, 'shape_locked', False))
    size = (getattr(panel, 'size', None) or '1x')

    def _repack_and_receipt():
        for pm in storage.read_all_objects(_Page, {
                "series_id": panel.series_id, "issue_id": panel.issue_id}):
            if pm.cells and any(r.panel_id == panel.panel_id
                                for row in pm.rows for r in row):
                _st.repack_page(storage, pm)
                storage.update_object(pm)
                for nm in _st.LAST_UNPROOFED:
                    receipt(f"🫙 **{nm}** lost its proof — the frame changed "
                            f"shape; re-proof it or feature another take")

    def _pick(aspect_name: str, mult: int):
        fresh_board(storage, panel)
        panel.aspect = FrameLayout(aspect_name)
        panel.size = f"{mult}x"
        panel.shape_locked = True
        storage.update_object(panel)
        _repack_and_receipt()
        receipt(f"🔒 held the frame at {aspect_name} {mult}x — the book reflowed around it")
        state.refresh_details()

    def _auto():
        fresh_board(storage, panel)
        panel.shape_locked = False
        storage.update_object(panel)
        _repack_and_receipt()
        receipt("🔓 released the frame — the flow shapes it to fill the page")
        state.refresh_details()

    if held:
        line = f"Shape — held at {panel.aspect.value} {size}"
    elif laid != panel.aspect.value:
        line = f"Shape — auto · laid {laid} (asked {panel.aspect.value})"
    else:
        line = f"Shape — auto · {panel.aspect.value} {size}"
    ui.label(line).classes('comic-label-sm').style('padding: 8px 10px 2px;')

    _BASE = {"square": (2, 2), "landscape": (3, 2), "portrait": (2, 3)}
    boxes = []
    for aspect_name, (bw, bh) in _BASE.items():
        for mult in (1, 2, 3):
            if _st.size_mult(f"{mult}x", _st.AR.get(aspect_name, 1.5)) != mult:
                continue          # the law says no (e.g. landscape 3x is 9 wide)
            boxes.append((aspect_name, mult, bw * mult, bh * mult))
    with ui.element('div').style(
            'display: grid; grid-template-columns: repeat(4, 46px); '
            'gap: 6px; padding: 6px 10px 10px; justify-items: center; '
            'align-items: center;'):
        for aspect_name, mult, gw, gh in boxes:
            lit = ((panel.aspect.value if held else laid) == aspect_name
                   and size == f"{mult}x")
            box = ui.element('div').style(
                f'width: {gw / 6 * 40:.0f}px; height: {gh / 6 * 40:.0f}px; '
                f'border: 2px solid '
                f'{"#c0392b" if lit else "rgba(130,130,130,.55)"}; '
                f'border-radius: 3px; cursor: pointer; '
                f'background: {"rgba(192,57,43,.18)" if lit else "transparent"};')
            box.tooltip(f'{aspect_name} {mult}x  ({gw}×{gh}) — pick it and the panel HOLDS this shape')
            box.on('click', lambda _, a=aspect_name, m=mult: _pick(a, m))
    ui.menu_item('Auto — let the flow shape it', on_click=lambda *_: _auto()) \
        .props('dense')


def snapshot_board(storage, board, note: str):
    """PRE-MUTATION INSURANCE: the board's record goes to the wastebasket
    before a destructive change (cleared table, dropped letters, uncast
    figure, rewritten brief) — 'swap it back' is always a door."""
    try:
        from storage.filepath import obj_to_filepath
        from storage.trash import soft_backup
        fp = obj_to_filepath(board, base_path=storage.base_path)
        if os.path.exists(fp):
            soft_backup(str(storage.base_path), fp, note=note)
    except Exception as ex:
        logger.debug(f"board snapshot skipped: {ex}")

def table_receipt(state, text: str, bench: str = 'the light table'):
    """A receipt slip in the one thread — the paper trail of GUI verbs.
    (Receipts are quiet toasts; the wastebasket and the torn-up pile
    are the ways back.)"""
    try:
        from gui.thread import thread_aside
        thread_aside(state, text, bench=bench)
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
    kw = ({"board_id": board.board_id} if is_artboard(board)
          else {"cover_id": board.cover_id} if is_cover(board)
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


def element_pending_key(board, key: str) -> str:
    return f"{board.id}/{key}"


def pose_element_bg(state, board, key: str, pose_direction: str | None = None,
                    name: str | None = None, style_id: str | None = None):
    """Queue a posed-acetate re-render for a prop/element on this board — the
    prop twin of pose_figure_bg.  One pose per element at a time: the row shows a
    spinner and a second click is refused while it's on the drawing board."""
    from agentic.tools.imaging import pose_element_acetate_body
    from helpers.render_queue import enqueue_renders
    pending = getattr(state, '_poses_pending', None)
    if pending is None:
        pending = set()
        try:
            state._poses_pending = pending
        except Exception:
            pass
    pkey = element_pending_key(board, key)
    disp = name or (key.split('/', 1)[1].replace('-', ' ') if key.startswith('element/') else key)
    if pkey in pending:
        ui.notify(f"{disp} is already on the drawing board — "
                  f"the pose lands when it's ready.", type='warning')
        return
    pending.add(pkey)
    kw = ({"board_id": board.board_id} if is_artboard(board)
          else {"cover_id": board.cover_id} if is_cover(board)
          else {"insert_id": board.insert_id} if is_insert(board)
          else {"scene_id": board.scene_id, "panel_id": board.panel_id})

    def job():
        try:
            return pose_element_acetate_body(
                state, board.series_id, board.issue_id, key=key,
                pose_direction=pose_direction, style_id=style_id, **kw)
        finally:
            pending.discard(pkey)
    enqueue_renders(state, [(
        f"posing {disp} for {board_label(board)}", job,
    )], role="the Penciller")


def dress_setting_bg(state, board, direction: str | None = None, style_id: str | None = None):
    """Queue a DRESS re-render of the board's background — the setting twin of
    pose_element_bg.  One dressing at a time: the row shows a spinner and a
    second click is refused while it's on the drawing board."""
    from agentic.tools.imaging import dress_setting_acetate_body
    from helpers.render_queue import enqueue_renders
    pending = getattr(state, '_poses_pending', None)
    if pending is None:
        pending = set()
        try:
            state._poses_pending = pending
        except Exception:
            pass
    pkey = element_pending_key(board, 'background/plate')
    if pkey in pending:
        ui.notify("the setting is already on the drawing board — "
                  "the dressing lands when it's ready.", type='warning')
        return
    pending.add(pkey)
    kw = ({"board_id": board.board_id} if is_artboard(board)
          else {"cover_id": board.cover_id} if is_cover(board)
          else {"insert_id": board.insert_id} if is_insert(board)
          else {"scene_id": board.scene_id, "panel_id": board.panel_id})

    def job():
        try:
            return dress_setting_acetate_body(
                state, board.series_id, board.issue_id,
                direction=direction, style_id=style_id, **kw)
        finally:
            pending.discard(pkey)
    enqueue_renders(state, [(
        f"dressing the setting for {board_label(board)}", job,
    )], role="the Background Artist")


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


def _lay_plate(state, panel, img):
    """Write a background/plate LAYER onto the board — full-frame by default
    (x centered, sitting on the floor, full height), lowest in the stack.  The
    author moves, scales, dresses or removes it like any other acetate."""
    b = state.storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel
    b.figure_images['background/plate'] = img
    b.figure_blocking['background/plate'] = {"x": 50, "y": 0, "h": 100, "z": -9}
    # a freshly laid background starts visible — clear any stale on/off flag
    b.figure_blocking.pop('background', None)
    # a fresh plate leaves no split-group behind
    for gname in list(b.layer_groups or {}):
        if 'background/plate' in (b.layer_groups[gname] or []):
            b.layer_groups.pop(gname)
    state.storage.update_object(b)


def lay_background_on_table(state, scene, panel, setting, shot=None):
    """Lay a setting's master on the board as the background LAYER — a deliberate
    act, full-frame by default, never auto-stamped.  If the master isn't inked in
    this board's style yet, ink it and let it land on the table by itself."""
    scene.setting_id = setting.setting_id
    if scene is not None and hasattr(scene, 'setting_shot_id'):
        scene.setting_shot_id = shot.shot_id if shot is not None else None
    state.storage.update_object(scene)
    fresh_board(state.storage, panel)

    from helpers.masters import scene_background
    style_id = (getattr(scene, 'style_id', None) if scene is not None
                else getattr(panel, 'style_id', None)) or 'vintage-four-color'
    shot_id = getattr(scene, 'setting_shot_id', None)
    master, _exact = scene_background(setting, style_id, panel.aspect, shot_id)
    _what = f"{setting.name} · {shot.name}" if shot is not None else setting.name

    if master and os.path.exists(master):
        _lay_plate(state, panel, master)
        table_receipt(state, f"🏔 laid the **{_what}** background on the table "
                             f"(full frame — drag or scale it, or dress it)")
        state.refresh_details()
        return

    # not inked in this style yet — ink it, then lay it when it lands
    from agentic.tools.imaging import generate_setting_background_body
    from helpers.render_queue import enqueue_renders
    table_receipt(state, f"🖌 inking the **{setting.name}** master in {style_id} — "
                         f"it lays itself on the table when it lands")

    def _land(_result, _pk=panel.primary_key, _sid=setting.setting_id,
              _series=setting.series_id, _style=style_id, _aspect=panel.aspect, _shot=shot_id):
        from schema import Setting as _Setting
        s = state.storage.read_object(cls=_Setting, primary_key={"series_id": _series, "setting_id": _sid})
        if s is None:
            return
        m, _ = scene_background(s, _style, _aspect, _shot)
        if m and os.path.exists(m):
            p = state.storage.read_object(cls=type(panel), primary_key=_pk)
            if p is not None:
                _lay_plate(state, p, m)
    enqueue_renders(state, [(
        f"master background — {setting.name} in {style_id} ({panel.aspect.value})",
        lambda: generate_setting_background_body(state, setting.series_id, setting.setting_id,
                                                 style_id, panel.aspect),
        _land,
    )], role='the Background Artist')
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
    # on a cover/insert/mark table the owner IS the board — sync its live
    # blocking first or this full-object write clobbers the author's drags
    if hasattr(scene, 'figure_blocking'):
        fresh_board(state.storage, scene)
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
        from gui.elements import studio_dialog
        with studio_dialog('Swap the style swatch', min_w=520, max_w=780,
                           scroll=True) as dlg:
            ui.label('Every take printed here wears the swatched style — '
                     'pick the one it should wear.').classes('text-sm')
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


# TAKES: every frame the exact shape of ITS art — measured from the image,
# never assumed from the board (a board flipped to landscape after portrait
# renders would otherwise crop every old take into the wrong orientation).
TAKE_SHAPES = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (2, 3), FrameLayout.SQUARE: (3, 3)}
DROP_SHAPES = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (3, 3), FrameLayout.SQUARE: (3, 3)}


def take_shape(img: str, board_aspect) -> tuple[int, int]:
    """The frame a take deserves: its OWN orientation, read off the file.
    Falls back to the board's shape only when the image can't be read."""
    try:
        from PIL import Image as _Image
        with _Image.open(img) as im:
            r = im.width / max(im.height, 1)
    except Exception:
        return TAKE_SHAPES[board_aspect]
    if r > 1.15:
        return TAKE_SHAPES[FrameLayout.LANDSCAPE]
    if r < 0.87:
        return TAKE_SHAPES[FrameLayout.PORTRAIT]
    return TAKE_SHAPES[FrameLayout.SQUARE]


def tear_up_take(state, board, img: str):
    """Tear up one of the board's takes.  Into the torn-up pile, not gone:
    dot-prefixed files vanish from the takes wall and the torn-up-pile
    chip above the takes brings them back (unique names so tearing up a
    same-named take never clobbers an older copy)."""
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
    if was_featured:
        board.image = None
        storage.update_object(board)

    table_receipt(state, '🗑 tore up a take — it waits in the torn-up pile above the takes')
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
        from gui.elements import studio_dialog
        with studio_dialog('The wastebasket', min_w=480, max_w=760) as dlg:
            ui.label('THE TORN-UP PILE of this board — '
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
                async def confirm_empty(_e):
                    from gui.elements import confirm_dialog
                    if await confirm_dialog(
                            'EMPTY THE TORN-UP PILE?',
                            f"{len(entries)} torn-up piece{'s' if len(entries) != 1 else ''} "
                            f"burn for good — this is the one door with no way back.",
                            go_label='Burn them', go_icon='delete_forever'):
                        empty_it()
                ui.button('Empty the pile', icon='delete_forever', color='negative') \
                    .props('outline dense no-caps').on('click', confirm_empty)
        dlg.open()

    ui.chip(f'torn-up pile · {len(entries)}', icon='delete_outline').props('dense clickable outline') \
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
        if is_artboard(board):
            # THE MARK GOES HOME: featuring writes through — a masthead to
            # its series' title art, a logo onto its house
            try:
                if board.board_kind == 'masthead':
                    from schema import Series as _Series
                    ser = storage.read_object(cls=_Series,
                                               primary_key={"series_id": board.scope_id})
                    if ser is not None and board.style_id:
                        ser.title_images = dict(ser.title_images or {})
                        ser.title_images[board.style_id] = locator
                        storage.update_object(ser)
                elif board.board_kind == 'logo':
                    from schema import Publisher as _Pub
                    pub = storage.read_object(cls=_Pub,
                                              primary_key={"publisher_id": board.scope_id})
                    if pub is not None:
                        pub.image = locator
                        storage.update_object(pub)
                table_receipt(state, f"📌 the {board.board_kind} is featured — "
                                     f"it now hangs where it belongs", bench='the mark bench')
            except Exception as ex:
                logger.warning(f"mark write-through failed: {ex}")
        else:
            table_receipt(state, '📌 featured a take — the table is locked to its arrangement')
        state.refresh_details()

    def explode_take(img: str):
        """A take (or an imported image) goes BACK to layers: it becomes the
        plate and the split flow opens on it — recognize, lift, rework."""
        state._auto_split_board = board.id
        rework_take_on_table(state, board, img)

    def _rehome(path):
        """A locator recorded against another root (a stale 'data/…' from
        before the houses) re-roots onto THIS storage's mount."""
        if not path or os.path.exists(path):
            return path
        if path.startswith("data/"):
            cand = os.path.join(str(storage.base_path), path.split("data/", 1)[1])
            if os.path.exists(cand):
                return cand
        return path

    takes = [img for img in storage.list_images(board) if os.path.exists(img)]
    take_style: dict[str, str] = {}
    if is_artboard(board):
        for _t in takes:
            if board.style_id:
                take_style[_t] = board.style_id
        # THE MARK'S WHOLE HISTORY HANGS HERE: the mark is ONE asset, so
        # takes filed under sibling style-boards or the owner's legacy
        # homes (publisher images for a logo, series title art for a
        # masthead) all hang on this one wall
        from schema import ArtBoard as _AB, Series as _Ser, Publisher as _Pub
        extra: list[str] = []
        for sib in storage.read_all_objects(_AB, primary_key={"scope_id": board.scope_id}):
            if sib.board_id != board.board_id and sib.board_kind == board.board_kind:
                for _t in storage.list_images(sib):
                    extra.append(_t)
                    if sib.style_id:
                        take_style[_t] = sib.style_id
        if board.board_kind == 'logo':
            _owner = storage.read_object(cls=_Pub, primary_key={"publisher_id": board.scope_id})
            if _owner is not None:
                extra += storage.list_images(_owner)
                extra.append(_owner.image)
        else:
            _owner = storage.read_object(cls=_Ser, primary_key={"series_id": board.scope_id})
            if _owner is not None:
                extra += storage.list_images(_owner)
                extra += list((_owner.title_images or {}).values())
        for img in extra:
            img = _rehome(img)
            if img and os.path.exists(img) and img not in takes:
                takes.append(img)
    with ui.row().classes('w-full items-center').style('gap: 10px;'):
        header("Takes", 4)
        wastebasket_chip(state, board)
    with ruled_page() as packer:
        for img in takes:
            with packer.place_cell([take_shape(img, board.aspect)], fudge=False):
                with ui.card().classes('soft-card p-2 mosaic-card relative panel-fill cursor-pointer') as take:
                    ui.image(source=img).props('fit=cover').classes('absolute inset-0 w-full h-full')
                    if img == featured:
                        ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10')
                    if is_artboard(board):
                        _sty = take_style.get(img)
                        ui.label((_sty or 'earlier work').replace('-', ' ')) \
                            .classes('caption-box caption-box-sm') \
                            .style('position: absolute; bottom: 4px; left: 4px; '
                                   'z-index: 10; font-size: .6rem; opacity: .85;')
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

                    def heal_take(img=img):
                        # PATCH UP THE TAKE: repaint a spot or extend the paper on
                        # the healing bench — the edited versions land back here as
                        # takes (the bench edits within the board's images)
                        from gui.selection import SelectionItem as _SI, SelectedKind as _SK
                        state.change_selection(new=[*state.selection, _SI(
                            name="Edit this take", id=img, kind=_SK.IMAGE_EDITOR)])
                    ui.button(icon='healing').props('flat round dense size=xs') \
                        .classes('absolute bottom-1 left-1 z-10 bg-white/70 dark:bg-black/50') \
                        .tooltip('Patch it up — repaint a spot or extend the paper on the healing bench') \
                        .on('click.stop', lambda _, img=img: heal_take(img))
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
    artboard_mode = is_artboard(panel)  # and so is a mark (masthead/logo)
    board_attrs = ({'data-cover': panel.cover_id} if cover_mode
                   else {'data-insert': panel.insert_id} if insert_mode
                   else {'data-artboard': panel.board_id, 'data-scope': panel.scope_id}
                   if artboard_mode
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
            # the tilt persists too — and rot: 0 CLEARS it (the JS undo
            # reports zero to untilt, so the else arm matters)
            if a.get('rot'):
                cur["rot"] = round(a['rot'])
            else:
                cur.pop("rot", None)
            p.figure_blocking[a['key']] = cur
            state.storage.update_object(p)
            # SYNC THE SERVER MODEL: the drag/resize moved the DOM directly, but
            # the element's server-side style still holds the OLD position — so a
            # later re-patch (e.g. when you scroll) would snap it back.  Update
            # the live element to match; the DOM already shows this, so it is
            # invisible, but now nothing reverts it.  (No full rebuild, so the
            # image never re-fades and the selection is kept.)
            el = getattr(state, '_rough_els', {}).get(a['key'])
            if el is not None:
                try:
                    bits = {"left": f"{round(a['x'], 1)}%",
                            "bottom": f"{round(a['y'], 1)}%", "top": "auto"}
                    if a.get('h'):
                        k = float(el._props.get('data-war') or 1) or 1
                        bits["height"] = f"{round(a['h'], 1)}%"
                        bits["width"] = f"{round(a['h'] * k, 2)}%"
                    if a.get('rot'):
                        _fl = ' scaleX(-1)' if el._props.get('data-flip') else ''
                        bits["transform"] = f"translateX(-50%){_fl} rotate({round(a['rot'])}deg)"
                    el.style('; '.join(f'{kk}: {vv}' for kk, vv in bits.items()))
                except Exception:
                    pass
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

        def _on_dress_ask(e):
            # dblclick on a trade-dress stamp: the dress prints from the
            # ISSUE's metadata, so the ask lands in the conversation where
            # the Editor can change the source of truth
            piece = (e.args or {}).get('key', '')
            asks = {'dress/credits': "Update this issue's credits: ",
                    'dress/issue': "Update this issue's number: ",
                    'dress/price': "Update this issue's price: "}
            state.user_input.value = asks.get(piece, "Update this issue's trade dress: ")
            try:
                state.user_input.run_method('focus')
            except Exception:
                pass
            ui.notify('The dress prints from the issue itself — say the new value '
                      'and I will set it there.', type='info', position='bottom',
                      timeout=4000)
        ui.on('dress_ask', _on_dress_ask)

    # ---- gather the acetates -------------------------------------------
    # THE SETTING IS A LAYER, NOT AN AUTOMATIC BACKDROP.  It shows only when the
    # author LAID it (pick_background writes background/plate) — it is never
    # auto-derived from scene.setting_id, so nothing lands on the table unasked.
    background = None
    split_plate = (panel.figure_images or {}).get("background/plate")
    if split_plate and os.path.exists(split_plate):
        background = split_plate

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

    # A prop is added to a panel deliberately, per panel, like any other
    # element — never auto-stamped from the scene onto every light table.
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

    references = [{"img": u, "on": True} for u in storage.list_uploads(panel)
                  if u and os.path.exists(u)]

    def _key_on(key, default=1):
        return bool(((panel.figure_blocking or {}).get(key) or {}).get('on', default))

    # THE SETTING RIDES THE SAME RAIL: the background is a layer exactly like a
    # figure or prop, so placing/moving/scaling it goes through the ONE code
    # path (the acetate render + drag).  It sits at the bottom of the stack and
    # starts full-frame; its on/off flag lives under 'background' (the eye), its
    # position/scale under 'background/plate' (dragged like any other key).
    if background:
        _bgblk = dict((panel.figure_blocking or {}).get('background/plate') or {})
        _bgblk.setdefault("x", 50)
        _bgblk.setdefault("y", 0)
        _bgblk.setdefault("h", 100)
        _bgblk.setdefault("z", -9)
        figures.append({"ref": None, "key": "background/plate", "img": background,
                        "posed": True, "on": _key_on('background'),
                        "blocking": _bgblk, "name": "background"})

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
    # THE TRADE DRESS: covers wear credits, issue № and price; a panel can
    # carry attribution.  Text snapshots refresh from the issue each paint.
    from helpers.trade_dress import (COVER_PIECES, PANEL_PIECES, DRESS_PIECES,
                                     DRESS_DEFAULTS, dress_text, refresh_dress_text)
    if cover_mode and getattr(getattr(panel, 'location', None), 'value', '') in ('front', 'back'):
        dress_pieces = list(COVER_PIECES)
    elif cover_mode:
        dress_pieces = []          # inside covers are ad/mailbag surfaces —
                                   # price and credits belong to the front
    elif insert_mode or artboard_mode:
        dress_pieces = []          # a mark IS lettering — it wears no dress
    else:
        dress_pieces = list(PANEL_PIECES)
    dress_issue = None
    if dress_pieces:
        from schema import Issue as _Issue
        dress_issue = storage.read_object(cls=_Issue, primary_key={
            "series_id": series_id, "issue_id": panel.issue_id})
        try:
            refresh_dress_text(storage, panel, dress_issue)
        except Exception as _ex:
            logger.debug(f"dress refresh skipped: {_ex}")
    letter_keys += [k for k in dress_pieces if (panel.figure_blocking or {}).get(k)]
    if dress_pieces:
        has_letters = True     # the rail always OFFERS the dress — a bare
                               # cover must still be able to stamp its first piece
    # the master eye rules its letters recursively; it reads as ON when any is
    letters = {"on": has_letters and (not letter_keys or any(_key_on(k) for k in letter_keys)),
               "keys": letter_keys}
    bg_layer = {"on": background is not None and _key_on('background'), "key": "background"}

    # THE TABLE MATCHES THE PAGE: show the shape the LAYOUT gave this panel (the
    # flow may have flexed an unlocked panel off its beat-shape), not just the
    # panel's own aspect — so the light table never disagrees with the book.
    from helpers.stitcher import laid_aspect as _laid_aspect
    _disp_aspect = (_laid_aspect(storage, panel).value
                    if hasattr(panel, 'panel_id') else panel.aspect.value)
    aspect = _ASPECT[_disp_aspect]
    # the rough and the print display in the board's orientation; portrait
    # boards cap their height so the table never towers off the page
    _ar = {'landscape': 1.5, 'portrait': 2 / 3, 'square': 1.0}[_disp_aspect]
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
            # the background is a layer now — it renders in the acetate loop
            # below (one code path), not as a fixed full-frame image here.
            if locked and featured and not any(f["on"] and f["img"] for f in figures):
                # A LOCKED, EMPTY TABLE still shows its truth: the featured
                # print sits ghosted on the glass — this is what the board
                # prints; unlock to lay it back down as layers
                ui.image(source=_src(featured)).props('fit=contain') \
                    .classes('absolute inset-0 w-full h-full rough-ghost-print').style('z-index: 1;')
                ui.label('the featured print — the table is locked to it') \
                    .classes('rough-ghost-print__note')
            elif not any(f["on"] and f["img"] for f in figures):
                with ui.column().classes('absolute inset-0 items-center justify-center') \
                        .style('z-index: 1; gap: 8px;'):
                    ui.label('bare board — nothing on the table').classes('text-xs text-gray-500')
                    if not locked:
                        with ui.row().style('gap: 8px;'):
                            ui.button('Lay a background', icon='landscape').props('outline dense size=sm') \
                                .on('click', lambda _: pick_background())
                            ui.button('Cast a figure', icon='person_add').props('outline dense size=sm') \
                                .on('click', lambda _: pick_figure())

            canvas_ar = {'landscape': 1.5, 'portrait': 2 / 3, 'square': 1.0}[_disp_aspect]

            def img_k(path):
                return _img_ar(path) / canvas_ar  # width%% per height%%

            live_blk = panel.figure_blocking or {}
            # key -> the LIVE element, so a drag/resize can sync the server-side
            # style out of band (see _on_block) — otherwise a later re-patch
            # snaps the acetate back to its old, server-held position.
            state._rough_els = {}
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
                state._rough_els[f["key"]] = fig

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
                # THE TRADE DRESS on the glass: credit band and corner badges,
                # draggable like any letter — the print stamps them the same
                for _dk in dress_pieces:
                    _b = saved.get(_dk)
                    if not _b or not (_b.get('text') or '').strip():
                        continue
                    _d = DRESS_DEFAULTS[_dk]
                    _cls = ('rough-narration rough-dress'
                            + (' rough-dress--badge' if DRESS_PIECES[_dk][1] == 'badge' else ''))
                    _lb = letter(_dk, _cls, _b['text'], _d['x'], _d['y'], 'caption')
                    if _lb is not None:
                        _lb._props['title'] = (f"{DRESS_PIECES[_dk][0]} — trade dress from the "
                                               f"issue's masthead data; drag to place")

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
        from gui.elements import studio_dialog
        with studio_dialog('Split this layer', min_w=480) as dlg:
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
                kw = ({"board_id": panel.board_id} if artboard_mode
                      else {"cover_id": panel.cover_id} if cover_mode
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

    # ONE DIALOG for posing a figure, posing a prop, OR dressing the setting.
    # They are the SAME act — describe what you want in words — so they share
    # the same code; only the title, the placeholder, and the button differ.
    def acetate_direction_dialog(title, placeholder, on_go, *,
                                 go_label='Pose', go_icon='accessibility_new', on_script=None):
        # THE CONVERSATION IS THE MODAL (the author's ruling): a prompt that
        # only wants words is not a dialog box.  The framed ask lands in the
        # conversation box, focused; Enter runs the work DIRECTLY (a one-shot
        # intercept — no agent round-trip) and the thread carries the words.
        # An empty direction lets the script decide, exactly as before.
        prefix = f"{title}: "
        state.user_input.value = prefix

        def _run(direction, on_go=on_go, on_script=on_script):
            if direction is None and on_script is not None:
                on_script()
            else:
                on_go(direction)
        state._input_intercept = (prefix, _run, None)
        try:
            state.user_input.run_method('focus')
        except Exception:
            pass
        ui.notify(placeholder[:120] + ('  (Enter alone lets the script decide.)'
                                       if on_script is not None else ''),
                  type='info', position='bottom', timeout=4000)

    def pose_dialog(character_id: str, variant_id: str):
        name = _char_names.get(character_id) or character_id.replace('-', ' ').title()
        hint = getattr(panel, 'beat', None) or panel.description or ''
        acetate_direction_dialog(
            f"Pose {name}",
            (f"Describe the pose — e.g. from the script: “{hint[:120]}…”" if hint
             else 'Describe the pose, expression and action…'),
            lambda t: pose_figure(character_id, variant_id, t),
            go_label='Pose', go_icon='accessibility_new',
            on_script=lambda: pose_figure(character_id, variant_id))

    def pose_element(key: str, name: str, pose_direction: str | None = None):
        _style = getattr(scene, 'style_id', None) if scene is not None \
            else getattr(panel, 'style_id', None)
        pose_element_bg(state, panel, key, pose_direction, name=name, style_id=_style)
        # rebuild so the element row shows its posing… spinner right away
        state.refresh_details()

    def pose_element_dialog(key: str, name: str):
        acetate_direction_dialog(
            f"Pose {name.title()}",
            'Describe the orientation or state — e.g. “drawn and raised”, '
            '“open on the lectern”, “seen 3/4 from below”, “lit and glowing”…',
            lambda t: pose_element(key, name, t),
            go_label='Pose', go_icon='3d_rotation')

    def dress_setting(direction: str | None = None):
        _style = getattr(scene, 'style_id', None) if scene is not None \
            else getattr(panel, 'style_id', None)
        dress_setting_bg(state, panel, direction, style_id=_style)
        # rebuild so the background row shows its dressing… spinner right away
        state.refresh_details()

    def dress_dialog():
        nm = (setting.name if setting else 'the setting')
        acetate_direction_dialog(
            f"Dress {nm.title() if setting else nm}",
            'Describe the light, time of day, weather or angle — '
            'e.g. “early morning, slight fog, bird’s-eye view”…',
            lambda t: dress_setting(t),
            go_label='Dress', go_icon='videocam')

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

    # ---- THE MINIMUM BAR: is the brief detailed enough to stage? ----------
    async def _brief_gate(brief_text: str, is_cover: bool, action: str, collab_msg: str) -> bool:
        """Weigh whether the written brief carries enough to STAGE the panel —
        pose the cast, dress the setting, set the shot.  If it does, return True
        and let <action> proceed.  If it's too thin, speak up: offer to flesh it
        out together (posts to the coauthor) — but the author can always
        override.  Returns True to proceed, False if they chose to collaborate
        or backed out.  The judge fails OPEN, so it never hard-blocks."""
        import asyncio
        from agentic.tools.imaging import assess_brief
        with ui.dialog().props('persistent') as busy, \
                ui.card().classes('soft-card').style('min-width: 300px;'):
            with ui.row().classes('items-center').style('gap: 12px;'):
                ui.spinner('dots', size='1.6em', color='primary')
                ui.label('Weighing the brief…').classes('text-sm')
        busy.open()
        try:
            verdict = await asyncio.to_thread(assess_brief, state, series_id, brief_text, is_cover)
        finally:
            busy.close()
        if not verdict or verdict.get('ready', True):
            return True
        gaps = verdict.get('gaps') or []
        note = verdict.get('note') or ''
        from gui.elements import studio_dialog
        with studio_dialog(f'This brief may be too thin to {action}', min_w=420, max_w=560) as dlg:
            ui.label('There may not be enough here to stage the panel well — to pose the '
                     'cast, dress the setting, and set the shot. We can fill it in together, '
                     f'or {action} it anyway.').classes('text-sm q-mt-sm')
            if gaps:
                with ui.column().classes('q-mt-sm').style('gap: 3px;'):
                    for g in gaps:
                        with ui.row().classes('items-start flex-nowrap').style('gap: 6px;'):
                            ui.icon('chevron_right').style('font-size: 1rem; margin-top: 1px; color: #c08a2b;')
                            ui.label(g).classes('text-sm')
            if note:
                ui.label(note).classes('text-sm text-gray-500 q-mt-sm').style('font-style: italic;')
            with ui.row().classes('w-full items-center q-mt-md').style('gap: 8px;'):
                ui.button('Flesh it out together', icon='forum').props('unelevated dense no-caps') \
                    .on('click', lambda _: dlg.submit('collab'))
                ui.button(f'{action.title()} it anyway', icon='bolt').props('flat dense no-caps') \
                    .on('click', lambda _: dlg.submit('override'))
                ui.space()
                ui.button('Not now', icon='close').props('flat dense no-caps') \
                    .on('click', lambda _: dlg.submit('cancel'))
        choice = await dlg
        if choice == 'override':
            return True
        if choice == 'collab':
            msg = collab_msg + (('  Specifically, what is missing: ' + '; '.join(gaps) + '.') if gaps else '')
            post_user_message(state, msg)
        return False

    # ---- PROOF: render a NEW take of THIS board, DIRECTLY -----------------
    async def proof_flow():
        """THE PROOF renders a new take of this exact board through the render
        queue — the SAME way everything else the table makes is rendered — NOT
        by asking the coauthor, whose tool context may not even hold this panel.
        render_panel_impl (and the cover body) compose the take from the board
        when it's roughed, or from the brief when the board is bare — one code
        path, deterministic, no selection to get wrong."""
        has_rough = any(f.get("on") and f.get("img") for f in figures) \
            or bool(bg_layer.get("on") and setting is not None)
        noun = ("cover" if cover_mode
                else f"'{panel.name}' insert page" if insert_mode
                else panel.board_kind if artboard_mode else "panel")
        if not has_rough:
            # BARE BOARD → a from-brief proof: make sure the brief can carry it.
            brief = f"{(getattr(panel, 'beat', '') or '').strip()}\n\n{(panel.description or '').strip()}".strip()
            if not brief:
                ui.notify('No rough is laid and the brief is empty — write the brief first, '
                          'then proof it.', type='warning')
                return
            collab = (f"There is no rough laid for this {noun}, and its brief is thin to "
                      f"proof from. Let's build it out together first.")
            if not await _brief_gate(brief, cover_mode, 'proof', collab):
                return

        import types
        from helpers.render_queue import enqueue_renders
        from agentic.tools.imaging import render_panel_impl, _generate_cover_image_body

        if artboard_mode:
            from agentic.tools.imaging import render_artboard_body

            def _job(_scope=panel.scope_id, _bid=panel.board_id):
                return render_artboard_body(state, _scope, _bid)
        elif cover_mode:
            def _job(_sid=panel.series_id, _iid=panel.issue_id, _cid=panel.cover_id):
                return _generate_cover_image_body(types.SimpleNamespace(context=state), _sid, _iid, _cid)
        elif insert_mode:
            # a full page proofs like everything else: through the QUEUE,
            # one board line, HOLD/STOP — never a conversational detour
            def _job(_sid=panel.series_id, _iid=panel.issue_id, _nid=panel.insert_id):
                from agentic.tools.imaging import generate_insert_art_body
                return generate_insert_art_body(state, _sid, _iid, _nid)
        else:
            def _job(_sid=panel.series_id, _iid=panel.issue_id,
                     _scid=panel.scene_id, _pid=panel.panel_id):
                return render_panel_impl(state, _sid, _iid, _scid, _pid)

        enqueue_renders(state, [(
            f"proofing this {noun} — a new take",
            _job,
            lambda _r: state.refresh_details(),
        )], role='the Inker')

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

                    # THE EDIT DOOR RIDES THE LOCK (author report: a dropped
                    # image landed them in a locked room with no obvious way
                    # into the layers) — one click lays the print on the
                    # table as the background layer, unlocked and editable
                    ui.button('Edit in layers', icon='layers').props('unelevated dense size=sm') \
                        .tooltip('Lay this print on the table as the background '
                                 'layer — unlock it and edit in layers') \
                        .on('click', lambda _: rework_take_on_table(state, panel, featured))

                    def unlock():
                        fresh_board(storage, panel)
                        panel.image = None
                        storage.update_object(panel)
                        _receipt('🔓 unlocked the table — no take is selected while you rework it')
                        state.refresh_details()
                    ui.button('Unlock', icon='lock_open').props('outline dense size=sm') \
                        .tooltip('Deselect the take — the table opens bare; '
                                 'the take stays on the wall') \
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
                    fresh_board(storage, panel)
                    panel.dialogue[i].character_id = speaker
                    storage.update_object(panel)
                    _receipt(f"🎙 handed a balloon to **{speaker.replace('-', ' ')}**")
                    state.refresh_details()

                cast_ids = list(dict.fromkeys(
                    [r.character_id for r in (panel.character_references or [])] +
                    [c.character_id for c in (getattr(scene, 'cast', None) or [])]))

                # THE TRADE DRESS ROWS: what the printed book wears —
                # credits, issue №, price (covers) or attribution (panels).
                # Toggling ON stamps the piece with the issue's own metadata.
                for _dk in dress_pieces:
                    _label, _kind = DRESS_PIECES[_dk]
                    _b = (panel.figure_blocking or {}).get(_dk)
                    _text = dress_text(dress_issue, _dk)
                    with ui.row().classes('light-layer w-full items-center flex-nowrap') \
                            .style('gap: 4px; margin-left: 14px; width: calc(100% - 14px);'):
                        if _b:
                            letter_eye(_dk)
                        else:
                            def _wear(_dk=_dk, _text=_text):
                                if not _text:
                                    ui.notify("The issue's masthead data doesn't have that "
                                              "yet — fill it on the issue's colophon first.",
                                              type='info')
                                    return
                                fresh_board(storage, panel)
                                panel.figure_blocking = dict(panel.figure_blocking or {})
                                panel.figure_blocking[_dk] = {"on": 1, "text": _text,
                                                              **DRESS_DEFAULTS[_dk]}
                                storage.update_object(panel)
                                _receipt(f"🏷 the board wears its {DRESS_PIECES[_dk][0].lower()} now")
                                state.refresh_details()
                            ui.button(icon='approval').props('flat round dense size=xs') \
                                .tooltip(f'Stamp the {_label.lower()} onto the board') \
                                .on('click', lambda _, k=_dk: _wear(k, dress_text(dress_issue, k)))
                        ui.icon('workspace_premium' if _kind == 'badge' else 'badge') \
                            .classes('text-sm')
                        ui.label(_label).classes('text-xs text-bold')
                        ui.label((_b or {}).get('text') or _text or '— not in the masthead data yet') \
                            .classes('text-xs' + ('' if (_b or _text) else ' text-gray-500')) \
                            .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                        ui.space()

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
                            snapshot_board(storage, panel, "the letters before a balloon was removed")
                            panel.dialogue = [x for j, x in enumerate(panel.dialogue) if j != i]
                            remap_letter_blocking('balloon/', i)
                            storage.update_object(panel)

                            _receipt('✂️ removed a balloon')
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
                                snapshot_board(storage, panel, "the letters before a caption was removed")
                                panel.narration = [x for x in panel.narration if x is not n]
                                # keep caption blocking aligned, same as balloons
                                remap_letter_blocking(f'caption/{pos}/', i)
                                storage.update_object(panel)

                                _receipt('✂️ removed a narrator box')
                                state.refresh_details()
                            ui.button(icon='close').props('flat round dense size=xs') \
                                .tooltip('Remove this narrator box').on('click', lambda _, n=n: drop_caption(n))
            # NOTHING auto-lists here: a prop reaches the table only when the
            # person deliberately places it (or the agent builds a rough board).
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
                            # THE CONVERSATION IS THE MODAL: the new name is
                            # typed in the box; Enter renames directly
                            prefix = f"Rename the {nm} layer to: "

                            def _do(new, key=key, nm=nm):
                                import re as _re
                                if not new:
                                    ui.notify('Give the layer a name.', type='warning')
                                    return
                                fresh_board(storage, panel)
                                slug = _re.sub(r'[^a-z0-9]+', '-', new.lower()).strip('-')[:40]
                                new_key = f'element/{slug}'
                                if not slug or new_key == key:
                                    return
                                if new_key in (panel.figure_images or {}):
                                    ui.notify('Another layer already has that name.', type='warning')
                                    return
                                _move_key(key, new_key)
                                storage.update_object(panel)
                                _receipt(f"🏷 renamed the **{nm}** layer to **{new}**")
                                state.refresh_details()
                            state.user_input.value = prefix
                            state._input_intercept = (prefix, _do, None)
                            try:
                                state.user_input.run_method('focus')
                            except Exception:
                                pass
                        name_label.on('click', lambda _, k=f["key"], n=f["name"]: rename_element(k, n))

                        def identify_element(key=f["key"], nm=f["name"]):
                            # link the cut-out to the asset it depicts: it
                            # becomes that character's posed acetate
                            from gui.elements import studio_dialog
                            with studio_dialog('Who is this?', min_w=480, max_w=720) as dlg:
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

                        # POSE THIS PROP: re-render the object in a new
                        # orientation or state — the prop twin of posing a figure
                        _el_posing = element_pending_key(panel, f["key"]) in \
                            (getattr(state, '_poses_pending', None) or set())
                        if _el_posing:
                            ui.spinner('dots', size='1.2em', color='primary') \
                                .tooltip("On the drawing board — the acetate lands here when it's ready")
                        else:
                            ui.button(icon='3d_rotation').props('flat round dense size=xs') \
                                .classes('row-tool') \
                                .tooltip('Pose this prop — re-render it in a new orientation or state') \
                                .on('click', lambda _, k=f["key"], n=f["name"]: pose_element_dialog(k, n))

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
                            snapshot_board(storage, panel, "the table before an element was removed")
                            panel.figure_images.pop(key, None)
                            panel.figure_blocking.pop(key, None)
                            for gname in list((panel.layer_groups or {})):
                                panel.layer_groups[gname] = [k for k in panel.layer_groups[gname] if k != key]
                                if not panel.layer_groups[gname]:
                                    panel.layer_groups.pop(gname)
                            storage.update_object(panel)

                            _receipt(f"✂️ removed **{nm}** from the table")
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
                        snapshot_board(storage, panel, "the cast before a figure was uncast")
                        panel.character_references = [
                            c for c in panel.character_references
                            if not (c.character_id == ref.character_id and c.variant_id == ref.variant_id)]
                        storage.update_object(panel)

                        _receipt(f"✂️ removed **{_char_names.get(ref.character_id, ref.character_id)}** "
                                 f"from this panel")
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .mark('uncast').classes('row-tool') \
                        .tooltip('Take this figure off the table') \
                        .on('click', lambda _, ref=f["ref"]: uncast(ref))

            def flatten_group(gname):
                from uuid import uuid4
                fresh_board(storage, panel)
                snapshot_board(storage, panel, "the layers before the group was combined")
                from helpers.compositor import DIMS, base_canvas, paste_acetates
                # capture everything the flatten touches, for the undo chip
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

                _receipt(f"🗜 combined the **{gname}** group into one acetate")
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
                if f["key"] == 'background/plate':
                    continue   # the background layer keeps its own rich row below
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
                        # THE CONVERSATION IS THE MODAL: type the new name,
                        # Enter renames directly
                        prefix = f"Rename the {gname} group to: "

                        def _do(new, gname=gname):
                            if not new or new == gname:
                                return
                            if new in (panel.layer_groups or {}):
                                ui.notify('Another group already has that name.', type='warning')
                                return
                            fresh_board(storage, panel)
                            panel.layer_groups = {(new if k == gname else k): v
                                                  for k, v in (panel.layer_groups or {}).items()}
                            storage.update_object(panel)
                            _receipt(f"🏷 renamed the **{gname}** group to **{new}**")
                            state.refresh_details()
                        state.user_input.value = prefix
                        state._input_intercept = (prefix, _do, None)
                        try:
                            state.user_input.run_method('focus')
                        except Exception:
                            pass
                    glabel.on('click', lambda _, g=gname: rename_group(g))
                    ui.space()

                    ui.button(icon='layers').props('flat round dense size=xs') \
                        .classes('row-tool') \
                        .tooltip('Combine this group into one acetate (hidden members are discarded)') \
                        .on('click', lambda _, g=gname: flatten_group(g))

                    def ungroup(gname=gname):
                        fresh_board(storage, panel)
                        snapshot_board(storage, panel, "the groups before one was dissolved")
                        panel.layer_groups.pop(gname, None)
                        storage.update_object(panel)

                        _receipt(f"📂 ungrouped **{gname}**")
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

                        _receipt(f"✂️ took the reference **{os.path.basename(path)}** off the table")
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

            # THE BACKGROUND LAYER — a row ONLY when a plate is actually laid, so
            # removing it clears its row like every other layer (no turds left).
            if background:
                bg_label = "Background — " + (setting.name if setting else 'the take')
                if split_plate and background == split_plate:
                    bg_label += " (split from the take)"
                with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
                    eye(bg_layer)
                    # PIN TO THE LIGHTBOX — like any other layer: a pinned
                    # background won't drag, scale or tilt until unpinned.
                    padlock({"key": "background/plate"})
                    ui.image(source=_src(background)).classes('light-thumb cursor-pointer') \
                        .tooltip('Swap the background — pick another setting') \
                        .on('click', lambda _: pick_background())
                    ui.label(bg_label).classes('text-sm') \
                        .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                    ui.space()
                    # DRESS THE SETTING — the setting's pose: new light, time of
                    # day, weather or camera angle.  Same dialog as posing.
                    ui.button(icon='videocam').props('flat round dense size=xs') \
                        .tooltip('Dress the setting — light, time of day, weather, camera angle') \
                        .on('click', lambda _: dress_dialog())
                    ui.button(icon='content_cut').props('flat round dense size=xs') \
                        .tooltip('Split this background into its elements (recognize, lift, repaint beneath)') \
                        .on('click', lambda _, p=background: split_flow('background', p))
                    ui.button(icon='healing').props('flat round dense size=xs') \
                        .tooltip('Heal or extend this background on the healing bench') \
                        .on('click', lambda _: heal_background())

                    # REMOVE THE BACKGROUND — like any other layer: the ✕ lifts
                    # the plate off the board outright (the eye just hides it),
                    # AND clears its on/off flag so nothing stale is left behind.
                    def drop_background():
                        fresh_board(storage, panel)
                        saved_plate = (panel.figure_images or {}).get('background/plate')
                        if saved_plate is None:
                            return
                        panel.figure_images.pop('background/plate', None)
                        panel.figure_blocking.pop('background/plate', None)
                        panel.figure_blocking.pop('background', None)   # the on/off flag, too
                        for gname in list(panel.layer_groups or {}):
                            panel.layer_groups[gname] = [k for k in panel.layer_groups[gname]
                                                         if k != 'background/plate']
                            if not panel.layer_groups[gname]:
                                panel.layer_groups.pop(gname)
                        storage.update_object(panel)

                        _receipt('✂️ removed the background from the table')
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=xs').classes('row-tool') \
                        .tooltip('Remove the background from this board') \
                        .on('click', lambda _: drop_background())

            # LAY A NEW ACETATE: figures, props and backgrounds lay down in
            # ONE CLICK from a picker; letters go through the coauthor (they
            # need writing).
            def _receipt(text: str):
                table_receipt(state, text)

            def _fresh():
                return storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel

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
                # THE MINIMUM BAR: enough here to stage a rough?  If not, speak
                # up and offer to flesh it out together (the author can override).
                collab = ("The brief for this panel is a bit thin to rough well. Let's flesh "
                          "it out together so the cast can be posed and the setting dressed.")
                if not await _brief_gate(brief, cover_mode, 'rough', collab):
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
                from gui.elements import studio_dialog
                with studio_dialog('Build the table from the brief', min_w=520, max_w=760) as dlg:
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
                        cid = f['character_id']
                        nm2 = (cast_names.get(cid) or cid).title()
                        # THE WARDROBE COMES FROM THE SCENE'S CAST — never guessed.
                        cast_vid = next((c.variant_id for c in (getattr(scene, 'cast', None) or [])
                                         if c.character_id == cid), None)
                        _variants = storage.read_all_objects(CharacterVariant,
                            primary_key={"series_id": series_id, "character_id": cid})
                        _vname = {v.id: (getattr(v, 'name', None) or v.id) for v in _variants}
                        if cast_vid is not None:
                            f['_variant_id'] = cast_vid
                            checks.append(('figure', f, ui.checkbox(
                                f"Pose {nm2} ({_vname.get(cast_vid, cast_vid)}) — "
                                f"{str(f.get('pose', ''))[:56]}", value=True)))
                        elif len(_variants) <= 1:
                            f['_variant_id'] = _variants[0].id if _variants else 'base'
                            checks.append(('figure', f, ui.checkbox(
                                f"Pose {nm2} — {str(f.get('pose', ''))[:60]}", value=True)))
                        else:
                            # NOT CAST + several wardrobes — ASK, never assume.
                            f['_variant_id'] = None
                            with ui.row().classes('w-full items-center flex-nowrap').style('gap: 8px;'):
                                _cb = ui.checkbox(f"Pose {nm2} — {str(f.get('pose', ''))[:40]}", value=True)
                                _sel = ui.select({v.id: _vname[v.id] for v in _variants}, value=None,
                                                 label="wardrobe — not cast, pick one") \
                                    .props('dense outlined').style('min-width: 220px;')
                                _sel.on_value_change(lambda e, f=f: f.__setitem__('_variant_id', e.value))
                            checks.append(('figure', f, _cb))
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
                        _uncast = []
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
                                # THE WARDROBE IS THE SCENE'S CAST (or a picked
                                # one) — never a guess.  No wardrobe → don't pose.
                                vid = item.get('_variant_id')
                                if not vid:
                                    _uncast.append(cast_names.get(cid) or cid.replace('-', ' '))
                                    continue
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
                        if _uncast:
                            ui.notify(
                                'No wardrobe chosen for ' + ', '.join(sorted(set(_uncast)))
                                + ' — cast them in the scene, or pick a look, then rough again.',
                                type='warning', timeout=6000)
                        state.refresh_details()
                    with ui.row().classes('w-full justify-end q-mt-sm'):
                        ui.button('Build the table', icon='auto_awesome').props('unelevated dense') \
                            .on('click', lambda _: go())
                dlg.open()

            def pick_figure():
                from gui.elements import studio_dialog
                with studio_dialog('Lay a figure on the table',
                                   min_w=480, max_w=720, scroll=True) as dlg:
                    from gui.elements import swatch_rack
                    already = {(c.character_id, c.variant_id) for c in (panel.character_references or [])}
                    items = []
                    for ch in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
                        for v in storage.read_all_objects(CharacterVariant, primary_key={"series_id": series_id, "character_id": ch.character_id}):
                            if (ch.character_id, v.id) in already:
                                continue
                            img = storage.find_variant_image(series_id=series_id, character_id=ch.character_id, variant_id=v.id)
                            vname = getattr(v, 'name', None) or v.id
                            items.append((f"{ch.name.title()} · {vname}", img, (ch, v)))

                    def lay(pl):
                        ch, v = pl
                        dlg.close()
                        lay_figure_on_table(state, panel, ch.character_id, v.id, ch.name)
                    swatch_rack(items, lay,
                                empty_text='Every cast member is already on the table.')

                    def _borrow(kind_word):
                        # BORROW FROM ANOTHER SERIES: the conversation is the
                        # import verb — the Librarian copies it in, then it
                        # appears right here in this picker
                        dlg.close()
                        state.user_input.value = (f"Import the {kind_word} ___ from another "
                                                  f"series into this one")
                        try:
                            state.user_input.run_method('focus')
                        except Exception:
                            pass
                    ui.button('Borrow from another series…', icon='local_library') \
                        .props('flat dense no-caps').classes('q-mt-sm') \
                        .on('click', lambda _: _borrow('character'))
                dlg.open()

            def pick_background():
                from gui.elements import studio_dialog
                with studio_dialog('Lay a background on the table',
                                   min_w=480, max_w=720, scroll=True) as dlg:
                    _can_shot = not (cover_mode or insert_mode)  # shots pin to a scene
                    with ui.row().classes('w-full items-start').style('gap: 8px;'):
                        for s in storage.read_all_objects(Setting, primary_key={"series_id": series_id}, order_by="name"):
                            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
                            with ui.column().classes('items-stretch').style('gap: 4px; width: 150px;'):
                                with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 150px;') as card:
                                    if img:
                                        ui.image(source=img).style('height: 80px;').props('fit=cover')
                                    ui.label(s.name.title() + '  · establishing').classes('text-xs text-center w-full')

                                def lay(s=s):
                                    dlg.close()
                                    lay_background_on_table(state, scene, panel, s)
                                card.on('click', lambda _, s=s: lay(s))

                                # SHOTS of this set — angle/time re-frames, one click
                                # each (a shot without art yet falls back to the master)
                                for sh in ((getattr(s, 'shots', None) or []) if _can_shot else []):
                                    def lay_shot(s=s, sh=sh):
                                        dlg.close()
                                        lay_background_on_table(state, scene, panel, s, sh)
                                    ui.chip(sh.name, icon='photo_camera') \
                                        .props('dense outline clickable size=sm') \
                                        .tooltip(f"Use the '{sh.name}' shot of {s.name}") \
                                        .on('click', lambda _, s=s, sh=sh: lay_shot(s, sh))

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

                    def _borrow_setting(_=None):
                        # the conversation is the import verb
                        dlg.close()
                        state.user_input.value = ("Import the setting ___ from another "
                                                  "series into this one")
                        try:
                            state.user_input.run_method('focus')
                        except Exception:
                            pass
                    ui.button('Borrow from another series…', icon='local_library') \
                        .props('flat dense no-caps').classes('q-mt-sm') \
                        .on('click', _borrow_setting)
                dlg.open()

            def pick_prop():
                from agentic.tools.normalization import normalize_id
                from gui.elements import studio_dialog
                with studio_dialog('Lay a prop on the table',
                                   min_w=480, max_w=720, scroll=True) as dlg:
                    with ui.row().classes('w-full q-mt-sm').style('gap: 8px;'):
                        for pa in storage.read_all_objects(PropAsset, primary_key={"series_id": series_id}, order_by="name"):
                            img = next((i for i in (pa.images or {}).values() if i and os.path.exists(i)), None)
                            with ui.card().classes('soft-card p-1 cursor-pointer relative').style('width: 130px;') as card:
                                if img:
                                    ui.image(source=img).style('height: 70px;').props('fit=contain')
                                ui.label(pa.name.title()).classes('text-xs text-center w-full')

                                # STRIKE A JUNK PROP right from the shop —
                                # recoverable from the wastebasket, no trip inside
                                async def _strike_prop(pa=pa):
                                    from gui.strike import strike
                                    from agentic.tools.assets import delete_prop
                                    dlg.close()
                                    await strike(state, delete_prop,
                                                 {"series_id": series_id, "prop_id": pa.prop_id},
                                                 f"the '{pa.name}' prop")
                                ui.button(icon='delete_outline').props('flat round dense size=xs') \
                                    .classes('absolute top-0 right-0 z-10') \
                                    .style('background: rgba(255,255,255,.72);') \
                                    .tooltip(f"Strike '{pa.name}' — it waits in the wastebasket") \
                                    .on('click.stop', _strike_prop)

                            def lay(pa=pa):
                                dlg.close()
                                # PROPS RIDE THE GLASS: the prop's art lands
                                # as a blockable acetate — no record is kept on
                                # the scene or the setting
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

                    def _borrow_prop(_=None):
                        # the conversation is the import verb
                        dlg.close()
                        state.user_input.value = ("Import the prop ___ from another "
                                                  "series into this one")
                        try:
                            state.user_input.run_method('focus')
                        except Exception:
                            pass
                    ui.button('Borrow from another series…', icon='local_library') \
                        .props('flat dense no-caps').classes('q-mt-sm') \
                        .on('click', _borrow_prop)
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
                    from gui.elements import studio_dialog
                    with studio_dialog('New letters', min_w=380) as dlg:

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

                # CLEAR THE BOARD — rightmost in the bar.  Removes EVERYTHING
                # from the table, no exceptions: the background/setting, every
                # acetate and posed figure, the cast on it, AND the letters
                # (balloons + narrator boxes).  Only the PRINT is kept.  Undoable.
                if not locked:
                    ui.space()

                    def clear_board():
                        fresh_board(storage, panel)
                        snapshot_board(storage, panel, "the table before it was cleared")
                        saved_imgs = dict(panel.figure_images or {})
                        saved_blk = {k: dict(v) for k, v in (panel.figure_blocking or {}).items()}
                        saved_groups = {g: list(ks) for g, ks in (panel.layer_groups or {}).items()}
                        saved_cast = list(getattr(panel, 'character_references', None) or [])
                        saved_dlg = list(getattr(panel, 'dialogue', None) or [])
                        saved_narr = list(getattr(panel, 'narration', None) or [])
                        if not (saved_imgs or saved_blk or saved_groups or saved_cast
                                or saved_dlg or saved_narr):
                            _receipt('the board is already bare — nothing to clear')
                            return
                        panel.figure_images = {}
                        panel.figure_blocking = {}
                        panel.layer_groups = {}
                        if hasattr(panel, 'character_references'):
                            panel.character_references = []
                        if hasattr(panel, 'dialogue'):
                            panel.dialogue = []
                        if hasattr(panel, 'narration'):
                            panel.narration = []
                        storage.update_object(panel)

                        _receipt('🧹 cleared the board — everything lifted off '
                                 '(only the print stays)')
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=sm') \
                        .tooltip('Clear the board — remove everything from the table '
                                 '(the cleared table waits in the wastebasket)') \
                        .on('click', lambda _: clear_board())

            # or just drop an image straight onto the table as a reference —
            # the ROW is the door: the page-level rescue feeds drops and
            # clicks to the hidden uploader (a bare q-uploader overlay
            # delivers neither in this app)
            with ui.row().classes('light-layer w-full items-center justify-center table-drop-zone cursor-pointer').style('min-height: 34px;'):
                def on_drop_reference(e):

                    _receipt(f"📌 pinned **{e.name}** to the table as a reference")
                    state.refresh_details()
                ui.upload(on_upload=on_drop_reference, auto_upload=True, max_files=1) \
                    .style('display: none;')
                ui.label('…or drop a reference image on the table — click to browse') \
                    .classes('text-xs text-gray-500')

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
                from gui.elements import studio_dialog
                with studio_dialog('Flatten the table', min_w=420) as dlg:
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
                        bid = panel.id   # every board kind answers .id
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
                    .on('click', lambda _: proof_flow())
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
                # THE ONE SHAPE PICKER (the author's ruling): panels use
                # the SAME shape grid as the open book's tile menu — pick
                # holds, Auto releases, the lit box is what prints.  Covers
                # and marks aren't paginated, so they keep a plain aspect
                # switch (there is no second truth to disagree with).
                from schema import FrameLayout as _FL
                if hasattr(panel, 'shape_locked') and not insert_mode:
                    _pk_btn = ui.button(icon='aspect_ratio') \
                        .props('flat round dense size=sm') \
                        .tooltip('Shape & size — the same picker as the book; '
                                 'a pick HOLDS the frame, Auto lets the flow shape it')
                    with _pk_btn:
                        with ui.menu().props('auto-close'):
                            shape_picker(state, storage, panel, receipt=_receipt)
                elif not insert_mode:
                    def reshape(shape):
                        fresh_board(storage, panel)
                        panel.aspect = shape
                        storage.update_object(panel)
                        state.refresh_details()
                    _simple_shapes = [('crop_landscape', _FL.LANDSCAPE, 'Landscape frame'),
                                      ('crop_portrait', _FL.PORTRAIT, 'Portrait frame')]
                    if artboard_mode:
                        _simple_shapes.append(('crop_square', _FL.SQUARE, 'Square frame'))
                    for icon, shape, tip in _simple_shapes:
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
            # THE BRIEF: the words the render is drawn from — editable RIGHT
            # HERE (a real editor, no confused coauthor round-trip), panel,
            # cover, or insert page alike.
            from gui.elements import caption_action, CrudButtonKind, markdown as _brief_md

            def edit_brief_dialog():
                # THE CONVERSATION IS THE MODAL (the author's ruling): the
                # brief is words, so it's written in the conversation box —
                # prefilled with the current brief, Enter saves DIRECTLY
                # (one-shot intercept, no agent round-trip), Shift+Enter
                # breaks a line, and an erased prefix stands down.
                prefix = f"{description_label}: "
                state.user_input.value = prefix + (panel.description or '')
                if len(panel.description or '') > 400:
                    state.user_input.classes('input-tall')

                def _save_brief(text):
                    if text is None:
                        ui.notify(f'{description_label} unchanged — write the words '
                                  f'after the prompt to rewrite it.', type='info')
                        return
                    fresh = storage.read_object(cls=type(panel),
                                                primary_key=panel.primary_key) or panel
                    fresh.description = text
                    snapshot_board(storage, fresh, "the brief before it was rewritten")
                    storage.update_object(fresh)
                    panel.description = fresh.description

                    _receipt(f"✍️ rewrote {description_label.lower()}")
                    state.refresh_details()
                state._input_intercept = (prefix, _save_brief, None)
                try:
                    state.user_input.run_method('focus')
                except Exception:
                    pass
                ui.notify('The words the render is drawn from — what you leave out is '
                          'left out of the art.  Enter saves; Shift+Enter for a new line.',
                          type='info', position='bottom', timeout=4000)

            _has_brief = bool((panel.description or '').strip())
            caption_action(description_label.title(),
                           CrudButtonKind.UPDATE if _has_brief else CrudButtonKind.CREATE,
                           lambda _: edit_brief_dialog(), 3)
            if _has_brief:
                _brief_md(panel.description)
            else:
                ui.label('No brief yet — click the pencil to write what this panel shows.') \
                    .classes('text-sm text-gray-500').style('font-style: italic; padding: 0 16px;')
        # an EXPLODED take auto-opens the split flow on its fresh plate
        if getattr(state, '_auto_split_board', None) == panel.id and split_plate:
            state._auto_split_board = None
            ui.timer(0.6, lambda: split_flow('background', split_plate), once=True)

        # THE BEAT/ROUGH/PROOF PENCIL, fired from the open book: when a tile's
        # pencil sent us here to rough or proof THIS panel, run the light
        # table's OWN action — build_table_flow (rough) or proof_flow (proof).
        # Same code path, just auto-fired.  (build_table_flow is conditional, so
        # look it up in locals(); a locked board simply has no rougher.)
        _auto = getattr(state, '_board_autorun', None)
        if _auto and _auto[1] == panel.id:
            _fn = locals().get('build_table_flow') if _auto[0] == 'rough' else locals().get('proof_flow')
            if _fn is not None:
                state._board_autorun = None
                ui.timer(0.4, _fn, once=True)

        if featured is not None:
            with ui.column().style('flex: 1 1 0; min-width: 0;'):
                ui.label('THE PRINT').classes('comic-label-sm')
                with ui.element('div').classes('rough-canvas').style(canvas_style):
                    ui.image(source=_src(featured)).props('fit=cover') \
                        .classes('absolute inset-0 w-full h-full')
                    if actions:
                        with ui.row().classes('absolute top-1 right-1 z-10 items-center').style('gap: 4px;'):
                            for icon, tip, handler in actions:
                                # the sentinel 'proof' binds the table's OWN
                                # proof flow — the render rides the queue with
                                # the one board line and HOLD/STOP, never a
                                # conversational detour
                                ui.button(icon=icon).props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip(tip) \
                                    .on('click.stop', proof_flow if handler == 'proof' else handler)


def view_artboard(state: APPState):
    """THE MARK'S BENCH: a masthead or logo composes on the light table —
    from text (write the brief, proof it), from layers (acetates, explode,
    rework), or from image (drop a take).  Featuring writes the mark home."""
    from schema import ArtBoard
    from gui.elements import header
    storage = state.storage
    selection = state.selection
    board_id = selection[-1].id
    scope_id = next((it.id for it in reversed(selection[:-1]) if it.id), None)
    board = storage.read_object(cls=ArtBoard, primary_key={
        "scope_id": scope_id, "board_id": board_id})
    details = state.details
    details.clear()
    if board is None:
        with details:
            ui.markdown(f"No mark here — the board `{board_id}` is gone or was struck.")
        return
    featured = board.image if board.image and os.path.exists(board.image) else None
    with details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0;'):
            header(board.name.title(), 0)
        light_table(state, board, board, None, featured=featured,
                    description_label='The lettering brief')
        # TAKES: every render of the mark on one wall — click one to
        # feature it (writes through to the series masthead / house logo)
        takes_row(state, board, featured)
