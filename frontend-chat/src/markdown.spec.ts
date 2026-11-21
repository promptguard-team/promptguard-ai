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
});
