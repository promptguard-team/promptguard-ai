import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getStats, getTimeseries, isAuditAction, isMlStatus, listEvents } from './audit';
import { configureClient } from './client';

const range = {
  from: new Date('2026-11-13T23:00:00Z'),
  to: new Date('2026-11-20T10:00:00Z'),
};

describe('api/audit', () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    fetchMock.mockImplementation(() => Promise.resolve(new Response('{}', { status: 200 })));
    configureClient({ getToken: () => 'tok', onSessionEnd: () => {} });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function calledUrl(): URL {
    return new URL(String(fetchMock.mock.calls[0]![0]), 'http://x');
  }

  it('requests stats for a range', async () => {
    await getStats(range);

    const url = calledUrl();
    expect(url.pathname).toBe('/api/audit/stats');
    expect(url.searchParams.get('from')).toBe('2026-11-13T23:00:00.000Z');
    expect(url.searchParams.get('to')).toBe('2026-11-20T10:00:00.000Z');
  });

  it('requests a timeseries with its bucket', async () => {
    await getTimeseries(range, 'day');

    const url = calledUrl();
    expect(url.pathname).toBe('/api/audit/timeseries');
    expect(url.searchParams.get('bucket')).toBe('day');
  });

  it('sends only the set event filters', async () => {
    const signal = new AbortController().signal;
    await listEvents(
      {
        range,
        actions: ['blocked_prompt', 'blocked_response'],
        flagged: false,
        mlStatus: null,
        userId: null,
        limit: 25,
        offset: 50,
      },
      signal,
    );

    const url = calledUrl();
    expect(url.pathname).toBe('/api/audit/events');
    expect(url.searchParams.getAll('action')).toEqual(['blocked_prompt', 'blocked_response']);
    expect(url.searchParams.get('flagged')).toBe('false');
    expect(url.searchParams.has('ml_status')).toBe(false);
    expect(url.searchParams.has('user_id')).toBe(false);
    expect(url.searchParams.get('limit')).toBe('25');
    expect(url.searchParams.get('offset')).toBe('50');
    expect(fetchMock.mock.calls[0]![1]?.signal).toBe(signal);
  });

  it('omits the action filter when no action is selected', async () => {
    await listEvents({ range, actions: [], limit: 5, offset: 0 });

    expect(calledUrl().searchParams.has('action')).toBe(false);
  });

  it('narrows unknown values to actions and ML statuses', () => {
    expect(isAuditAction('blocked_prompt')).toBe(true);
    expect(isAuditAction('nope')).toBe(false);
    expect(isMlStatus('unavailable')).toBe(true);
    expect(isMlStatus(null)).toBe(false);
  });
});
