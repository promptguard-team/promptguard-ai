import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

// LLM output is untrusted. markdown-it never passes raw HTML through
// (html: false) and DOMPurify enforces an allowlist on the result.
const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const ALLOWED_TAGS = [
  'a',
  'p',
  'br',
  'hr',
  'strong',
  'em',
  's',
  'del',
  'code',
  'pre',
  'ul',
  'ol',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'blockquote',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
];
const ALLOWED_ATTR = ['href', 'title', 'target', 'rel', 'class'];

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

export function renderMarkdown(source: string): string {
  return DOMPurify.sanitize(md.render(source), { ALLOWED_TAGS, ALLOWED_ATTR });
}
