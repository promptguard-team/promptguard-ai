import { describe, expect, it } from 'vitest';
import { i18n } from './index';

describe('i18n', () => {
  it('serves Polish copy', () => {
    expect(i18n.global.t('app.name')).toBe('PromptGuard CISO');
    expect(i18n.global.t('ranges.7d')).toBe('7 dni');
  });
});
