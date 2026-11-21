import DOMPurify from 'dompurify';
import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './markdown';

// markdown-it escapes raw HTML into inert text, so assert on the parsed DOM
// rather than on substrings that may legitimately appear as escaped text.
function parse(html: string): HTMLElement {
  const root = document.createElement('div');
  root.innerHTML = html;
  return root;
}

describe('renderMarkdown', () => {
  it('renders lists, emphasis and code', () => {
    const html = renderMarkdown('- **bold** item\n- `code`\n\n```js\nlet x = 1;\n```');
    expect(html).toContain('<ul>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<code>code</code>');
    expect(html).toContain('<pre>');
  });

  it('never emits raw HTML or scripts', () => {
    const html = renderMarkdown('<script>alert(1)</script><img src=x onerror=alert(1)>');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<img');
    const root = parse(html);
    expect(root.querySelector('script, img')).toBeNull();
    expect(root.querySelector('[onerror]')).toBeNull();
  });

  it('drops javascript: links', () => {
    const html = renderMarkdown('[x](javascript:alert(1))');
    const root = parse(html);
    expect(root.querySelector('a')).toBeNull();
    expect(root.querySelector('[href]')).toBeNull();
  });

  it('opens links in a new tab with rel="noopener noreferrer"', () => {
    const html = renderMarkdown('[site](https://example.com)');
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it('keeps line breaks inside a paragraph', () => {
    expect(renderMarkdown('a\nb')).toContain('<br');
  });

  it('renders the alt text of a blocked image as plain text', () => {
    const root = parse(renderMarkdown('![cat <b>pic</b>](https://evil.example/x.png)'));
    expect(root.querySelector('img')).toBeNull();
    expect(root.querySelector('b')).toBeNull();
    expect(root.textContent).toContain('cat <b>pic</b>');
  });

  it('drops entity-encoded javascript: schemes', () => {
    const root = parse(renderMarkdown('[x](&#106;avascript:alert(1))'));
    expect(root.querySelector('a')).toBeNull();
    expect(root.querySelector('[href]')).toBeNull();
  });

  it('drops javascript: reference-style links', () => {
    const root = parse(renderMarkdown('[x][r]\n\n[r]: javascript:alert(1)'));
    expect(root.querySelector('[href]')).toBeNull();
  });

  it('linkifies bare URLs with target and rel', () => {
    const a = parse(renderMarkdown('see https://example.com')).querySelector('a');
    expect(a?.getAttribute('href')).toBe('https://example.com');
    expect(a?.getAttribute('target')).toBe('_blank');
    expect(a?.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('keeps HTML inside a code span escaped', () => {
    const root = parse(renderMarkdown('`<img src=x onerror=alert(1)>`'));
    expect(root.querySelector('img')).toBeNull();
    expect(root.querySelector('code')?.textContent).toBe('<img src=x onerror=alert(1)>');
  });

  it('does not leak the link hook into the global DOMPurify instance', () => {
    renderMarkdown('[site](https://example.com)');
    const root = parse(DOMPurify.sanitize('<a href="https://e.com">x</a>'));
    expect(root.querySelector('a')?.hasAttribute('target')).toBe(false);
  });
});
