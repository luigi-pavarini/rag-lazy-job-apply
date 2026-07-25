"""Draw the copilot's markers onto the live page.

``badges`` puts a small numbered chip at each detected field so "balloon (3)"
in the terminal maps to a visible (3) on screen. ``highlight`` outlines one
field and scrolls it into view. All markers live in one container we own and
can clear; we never modify the page's own elements beyond a temporary outline.
"""

from __future__ import annotations

_CONTAINER_ID = "__lazyapply_overlay__"

_BADGES_JS = r"""
(fields) => {
  const CID = '__lazyapply_overlay__';
  document.getElementById(CID)?.remove();
  const box = document.createElement('div');
  box.id = CID;
  box.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  for (const f of fields) {
    const el = document.querySelector(`[data-lazyapply-id="${f.id}"]`);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    const chip = document.createElement('div');
    chip.textContent = String(f.id);
    chip.style.cssText = [
      'position:absolute',
      `top:${Math.max(0, r.top - 10)}px`,
      `left:${Math.max(0, r.left - 10)}px`,
      'min-width:18px;height:18px;padding:0 4px',
      'background:#2563eb;color:#fff;font:600 12px/18px system-ui',
      'text-align:center;border-radius:9px;box-shadow:0 1px 3px rgba(0,0,0,.4)',
    ].join(';');
    box.appendChild(chip);
    const ring = document.createElement('div');
    ring.style.cssText = [
      'position:absolute',
      `top:${r.top - 2}px`, `left:${r.left - 2}px`,
      `width:${r.width}px`, `height:${r.height}px`,
      'border:2px solid rgba(37,99,235,.55);border-radius:4px',
    ].join(';');
    box.appendChild(ring);
  }
  document.body.appendChild(box);
  return true;
}
"""

_HIGHLIGHT_JS = r"""
(id) => {
  const el = document.querySelector(`[data-lazyapply-id="${id}"]`);
  if (!el) return false;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const prev = el.style.outline;
  el.style.outline = '3px solid #f59e0b';
  el.style.outlineOffset = '2px';
  setTimeout(() => { el.style.outline = prev; }, 2500);
  return true;
}
"""

_CLEAR_JS = r"""
() => { document.getElementById('__lazyapply_overlay__')?.remove(); return true; }
"""


async def draw_badges(page, fields) -> None:
    payload = [{"id": f.id} for f in fields]
    try:
        await page.evaluate(_BADGES_JS, payload)
    except Exception:
        pass


async def highlight(page, field_id: int) -> bool:
    try:
        return bool(await page.evaluate(_HIGHLIGHT_JS, field_id))
    except Exception:
        return False


async def clear(page) -> None:
    try:
        await page.evaluate(_CLEAR_JS)
    except Exception:
        pass
