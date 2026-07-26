"""Read the form on a page into a structured field list.

We inject JS that walks every visible form control, resolves its human label
from several sources, and stamps each one with a stable ``data-lazyapply-id``
so we can re-select it later for highlighting or filling. Returning a bounding
box lets the overlay draw a numbered badge next to each field.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


# JS runs in the page. It returns a plain-serialisable list of field objects.
_EXTRACT_JS = r"""
() => {
  const ATTR = 'data-lazyapply-id';
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || s.opacity === '0') return false;
    return true;
  };
  const text = (el) => (el ? (el.textContent || '').trim().replace(/\s+/g, ' ') : '');

  // Question text that sits ABOVE a field (headings/paragraphs), common on
  // form builders like Gupy where the prompt is not a real <label>.
  const PLACEHOLDER_RE = /^(digite|selecione|escolha|informe|type here|select|choose|your answer)/i;
  const questionAbove = (el) => {
    let node = el;
    for (let depth = 0; depth < 4 && node; depth++) {
      let sib = node.previousElementSibling;
      while (sib) {
        const t = text(sib);
        if (t && t.length >= 8 && !PLACEHOLDER_RE.test(t)) return t;
        sib = sib.previousElementSibling;
      }
      node = node.parentElement;
    }
    return '';
  };

  const labelFor = (el) => {
    // 1) explicit <label for=id>
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && text(l)) return text(l);
    }
    // 2) wrapping <label>
    const wrap = el.closest('label');
    if (wrap && text(wrap)) return text(wrap);
    // 3) aria-labelledby
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const parts = lb.split(/\s+/).map(id => text(document.getElementById(id))).filter(Boolean);
      if (parts.length) return parts.join(' ');
    }
    // 4) aria-label
    const al = el.getAttribute('aria-label');
    if (al && al.trim()) return al.trim();
    // 5) a real <label>/<legend> in the field's group
    const group = el.closest('div,section,fieldset,li,tr') || el.parentElement;
    if (group) {
      const lg = group.querySelector('label, legend');
      if (lg && text(lg)) return text(lg);
    }
    // 6) the question heading/paragraph sitting above the field
    const q = questionAbove(el);
    if (q) return q;
    // 7) last resort: placeholder / title / name
    for (const a of ['placeholder', 'title', 'name']) {
      const v = el.getAttribute(a);
      if (v && v.trim()) return v.trim();
    }
    return '';
  };

  const requiredOf = (el) =>
    el.required === true ||
    el.getAttribute('aria-required') === 'true' ||
    /\*|required|obrigat/i.test(labelFor(el));

  const controls = [];
  const seenRadioGroups = new Set();
  let idx = 0;

  const all = Array.from(document.querySelectorAll(
    'input, textarea, select, [contenteditable=""], [contenteditable="true"]'
  ));

  for (const el of all) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || (tag === 'select' ? 'select' : tag)).toLowerCase();
    if (type === 'hidden' || type === 'submit' || type === 'button' || type === 'image' || type === 'reset') continue;
    if (el.disabled) continue;
    if (!isVisible(el)) continue;

    // Radio/checkbox groups: collapse a radio group into a single field.
    if (type === 'radio') {
      const name = el.name || labelFor(el);
      if (seenRadioGroups.has(name)) continue;
      seenRadioGroups.add(name);
      const members = all.filter(x => x.type === 'radio' && (x.name || labelFor(x)) === name && isVisible(x));
      const options = members.map(m => ({ value: m.value, label: labelFor(m) || m.value }));
      const groupLabel = (() => {
        const fs = el.closest('fieldset');
        const lg = fs && fs.querySelector('legend');
        return (lg && text(lg)) || name;
      })();
      idx += 1;
      members.forEach(m => m.setAttribute(ATTR, String(idx)));
      const r = el.getBoundingClientRect();
      controls.push({
        id: idx, tag: 'radio-group', type: 'radio', label: groupLabel,
        required: members.some(requiredOf), value: (members.find(m => m.checked) || {}).value || '',
        options, box: { x: r.x, y: r.y, w: r.width, h: r.height },
      });
      continue;
    }

    idx += 1;
    el.setAttribute(ATTR, String(idx));
    const r = el.getBoundingClientRect();
    let options = [];
    if (tag === 'select') {
      options = Array.from(el.options).map(o => ({ value: o.value, label: text(o) || o.value }));
    }
    let value = '';
    if (type === 'checkbox') value = el.checked ? 'checked' : '';
    else if (el.isContentEditable) value = text(el);
    else value = el.value || '';

    controls.push({
      id: idx,
      tag,
      type,
      label: labelFor(el),
      required: requiredOf(el),
      value,
      options,
      box: { x: r.x, y: r.y, w: r.width, h: r.height },
    });
  }
  return {
    url: location.href,
    title: document.title,
    lang: document.documentElement.lang || '',
    fields: controls,
  };
}
"""


@dataclass
class Field:
    id: int
    tag: str
    type: str
    label: str
    required: bool
    value: str
    options: list[dict[str, str]]
    box: dict[str, float]

    def as_prompt_line(self) -> str:
        req = " (required)" if self.required else ""
        opts = ""
        if self.options:
            shown = ", ".join(o["label"] for o in self.options[:12])
            opts = f" options=[{shown}]"
        cur = f" current={self.value!r}" if self.value else ""
        label = self.label or "(no label)"
        return f"[{self.id}] {label} · type={self.type}{req}{opts}{cur}"


@dataclass
class PageForm:
    url: str
    title: str
    lang: str
    fields: list[Field]


async def extract_form(page) -> PageForm:
    """Run the extractor on a Playwright page and return structured fields."""
    data: dict[str, Any] = await page.evaluate(_EXTRACT_JS)
    fields = [Field(**f) for f in data.get("fields", [])]
    return PageForm(
        url=data.get("url", ""),
        title=data.get("title", ""),
        lang=data.get("lang", ""),
        fields=fields,
    )


def parse_form_dict(data: dict[str, Any]) -> PageForm:
    """Build a PageForm from a raw dict — used by offline tests with fixtures."""
    fields = [Field(**f) for f in data.get("fields", [])]
    return PageForm(
        url=data.get("url", ""),
        title=data.get("title", ""),
        lang=data.get("lang", ""),
        fields=fields,
    )


# Exposed so tests can run the same JS inside a headless page against fixtures.
EXTRACT_JS = _EXTRACT_JS


def fields_to_prompt(form: PageForm) -> str:
    lines = [f.as_prompt_line() for f in form.fields]
    return "\n".join(lines)


def field_dicts(form: PageForm) -> list[dict[str, Any]]:
    return [asdict(f) for f in form.fields]
