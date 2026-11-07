// A tiny hyperscript helper for the hand-written view layer. No framework, no innerHTML.

export type Child = Node | string | null | undefined | false;
export type Props = Record<
  string,
  string | number | boolean | null | undefined | ((event: Event) => void)
>;

const SVG_NS = 'http://www.w3.org/2000/svg';

function apply(el: Element, props: Props | null | undefined): void {
  if (!props) return;
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (typeof value === 'function') {
      el.addEventListener(key.replace(/^on/, '').toLowerCase(), value);
    } else if (key === 'class') {
      el.setAttribute('class', String(value));
    } else {
      el.setAttribute(key, value === true ? '' : String(value));
    }
  }
}

function append(el: Element, children: Child[]): void {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    el.append(typeof child === 'string' ? document.createTextNode(child) : child);
  }
}

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props?: Props | null,
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  apply(el, props);
  append(el, children);
  return el;
}

export function svg<K extends keyof SVGElementTagNameMap>(
  tag: K,
  props?: Props | null,
  ...children: Child[]
): SVGElementTagNameMap[K] {
  const el = document.createElementNS(SVG_NS, tag);
  apply(el, props);
  append(el, children);
  return el;
}

/** Replace all children of a node. */
export function mount(parent: Element, ...children: Child[]): void {
  parent.replaceChildren();
  append(parent, children);
}
