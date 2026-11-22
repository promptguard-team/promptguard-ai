import { describe, expect, it } from 'vitest';
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

    expect(parseEventQuery(toEventQuery(filters))).toEqual(filters);
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

  it.each(['\u00a03 ', ' 3 ', '1e2', '0x10', '1e20', '-1', '1.5', '1234567'])(
    'rejects the page %j',
    (page) => {
      expect(parseEventQuery({ page }).page).toBe(1);
    },
  );

  it('accepts a plain page number and any known size', () => {
    expect(parseEventQuery({ page: '12', size: '50' })).toMatchObject({ page: 12, pageSize: 50 });
    expect(parseEventQuery({ size: '25' }).pageSize).toBe(25);
  });

  it('takes the first value of a repeated scalar', () => {
    expect(parseEventQuery({ range: ['24h', '30d'] }).range).toBe('24h');
  });

  it('tolerates null query values', () => {
    expect(parseEventQuery({ flagged: null }).flagged).toBeNull();
    expect(parseEventQuery({ action: [null, 'allowed'] }).actions).toEqual(['allowed']);
  });

  it('rejects an impossible custom day', () => {
    const filters = parseEventQuery({ range: 'custom', from: '2026-02-30', to: '2026-03-02' });
    expect(filters.range).toBe('7d');
    expect(filters.fromDay).toBeNull();
  });

  it('keeps a valid user without an email', () => {
    const filters = parseEventQuery({ user: UUID });
    expect(filters.userId).toBe(UUID);
    expect(filters.userEmail).toBeNull();
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
