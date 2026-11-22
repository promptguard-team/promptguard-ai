import { describe, expect, it } from 'vitest';
import type { LocationQuery } from 'vue-router';
import { defaultEventFilters, eventListParams, parseEventQuery, toEventQuery } from './eventQuery';

const UUID = '3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e';

describe('eventQuery', () => {
  it('parses an empty query to the defaults', () => {
    expect(parseEventQuery({})).toEqual(defaultEventFilters());
  });

  it('round-trips every filter through the URL', () => {
    const filters = {
      ...defaultEventFilters(),
      range: 'custom' as const,
      fromDay: '2026-11-01',
      toDay: '2026-11-03',
      actions: ['blocked_prompt' as const, 'provider_error' as const],
      flagged: false,
      mlStatus: 'unavailable' as const,
      userId: UUID,
      userEmail: 'jan@example.com',
      page: 3,
      pageSize: 50 as const,
    };

    expect(parseEventQuery(toEventQuery(filters) as LocationQuery)).toEqual(filters);
  });

  it('omits defaults from the URL', () => {
    expect(toEventQuery(defaultEventFilters())).toEqual({});
  });

  it('drops invalid values', () => {
    expect(
      parseEventQuery({
        range: '1y',
        action: ['blocked_prompt', 'bogus', 'blocked_prompt'],
        flagged: 'maybe',
        ml: 'down',
        user: 'not-a-uuid',
        email: 'x@example.com',
        page: '0',
        size: '30',
      }),
    ).toEqual({ ...defaultEventFilters(), actions: ['blocked_prompt'] });
  });

  it('falls back to the default preset for a broken custom range', () => {
    expect(parseEventQuery({ range: 'custom', from: '2026-11-05', to: '2026-11-01' }).range).toBe(
      '7d',
    );
  });

  it('maps filters to API parameters', () => {
    const now = new Date('2026-11-20T10:00:00Z');
    const params = eventListParams(
      { ...defaultEventFilters(), range: '24h', page: 3, pageSize: 25, flagged: true },
      now,
    );

    expect(params).toMatchObject({ limit: 25, offset: 50, flagged: true, actions: [] });
    expect(params.range).toEqual({ from: new Date('2026-11-19T10:00:00Z'), to: now });
  });

  it('maps a custom range to whole Warsaw days', () => {
    const params = eventListParams({
      ...defaultEventFilters(),
      range: 'custom',
      fromDay: '2026-11-01',
      toDay: '2026-11-03',
    });

    expect(params.range).toEqual({
      from: new Date('2026-10-31T23:00:00Z'),
      to: new Date('2026-11-03T23:00:00Z'),
    });
  });
});
