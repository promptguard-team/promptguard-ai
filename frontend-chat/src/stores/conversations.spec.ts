import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { ApiError } from '@/api/client';
import * as chatApi from '@/api/chat';
import { makeTitle, storageKey, useConversationsStore } from './conversations';

vi.mock('@/api/chat');

const send = vi.mocked(chatApi.sendPrompt);

function pending(): { resolve: (v: chatApi.ChatResponse) => void; reject: (e: unknown) => void } {
  let resolve!: (v: chatApi.ChatResponse) => void;
  let reject!: (e: unknown) => void;
  send.mockReturnValue(
    new Promise<chatApi.ChatResponse>((res, rej) => {
      resolve = res;
      reject = rej;
    }),
  );
  return { resolve, reject };
}

describe('makeTitle', () => {
  it('collapses whitespace and keeps short text as is', () => {
    expect(makeTitle('  hello\n  world ')).toBe('hello world');
  });

  it('truncates to 40 characters with an ellipsis', () => {
    const title = makeTitle('a'.repeat(50));
    expect(title).toHaveLength(40);
    expect(title.endsWith('…')).toBe(true);
  });
});

describe('stores/conversations', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    send.mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates a conversation on the first send and routes the reply into it', async () => {
    send.mockResolvedValue({ response: 'Hi **there**', blocked: false });
    const store = useConversationsStore();
    store.load('u1');

    const id = await store.send(null, 'hello');

    const conversation = store.get(id)!;
    expect(conversation.title).toBe('hello');
    expect(conversation.messages.map((m) => [m.role, m.status, m.text])).toEqual([
      ['user', 'ok', 'hello'],
      ['assistant', 'ok', 'Hi **there**'],
    ]);
    expect(send).toHaveBeenCalledWith('hello');
  });

  it('shows a sending placeholder and blocks input until the reply arrives', async () => {
    const { resolve } = pending();
    const store = useConversationsStore();
    store.load('u1');

    const promise = store.send(null, 'hello');
    await Promise.resolve();
    expect(store.sending).toBe(true);
    const conversation = store.sorted[0]!;
    expect(conversation.messages.at(-1)).toMatchObject({ role: 'assistant', status: 'sending' });

    resolve({ response: 'done', blocked: false });
    await promise;
    expect(store.sending).toBe(false);
    expect(conversation.messages.at(-1)).toMatchObject({ status: 'ok', text: 'done' });
  });

  it('marks a blocked response', async () => {
    send.mockResolvedValue({ response: '', blocked: true });
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'hello');
    expect(store.get(id)!.messages.at(-1)).toMatchObject({ role: 'assistant', status: 'blocked' });
  });

  it('marks the user message blocked and drops the placeholder on 403', async () => {
    send.mockRejectedValue(new ApiError('forbidden', 403));
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'bad');
    const messages = store.get(id)!.messages;
    expect(messages).toHaveLength(1);
    expect(messages[0]).toMatchObject({ role: 'user', status: 'blocked' });
  });

  it.each([
    [new ApiError('provider', 502), 'provider'],
    [new ApiError('network'), 'network'],
    [new ApiError('http', 500), 'http'],
    [new ApiError('unauthorized', 401), 'http'],
    [new Error('boom'), 'network'],
  ])('turns %o into an error message of kind %s', async (error, kind) => {
    send.mockRejectedValue(error);
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'hello');
    expect(store.get(id)!.messages.at(-1)).toMatchObject({
      role: 'assistant',
      status: 'error',
      errorKind: kind,
    });
  });

  it('retry replaces the error message with a fresh attempt for the same prompt', async () => {
    send.mockRejectedValueOnce(new ApiError('provider', 502));
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'again');
    const errorId = store.get(id)!.messages.at(-1)!.id;

    send.mockResolvedValueOnce({ response: 'ok now', blocked: false });
    await store.retry(id, errorId);

    const messages = store.get(id)!.messages;
    expect(messages).toHaveLength(2);
    expect(messages[1]).toMatchObject({ role: 'assistant', status: 'ok', text: 'ok now' });
    expect(send).toHaveBeenLastCalledWith('again');
  });

  it('appends to an existing conversation and bumps updatedAt', async () => {
    send.mockResolvedValue({ response: 'r', blocked: false });
    const store = useConversationsStore();
    store.load('u1');
    const first = await store.send(null, 'one');
    const before = store.get(first)!.updatedAt;
    await new Promise((r) => setTimeout(r, 2));
    const second = await store.send(first, 'two');
    expect(second).toBe(first);
    expect(store.get(first)!.messages).toHaveLength(4);
    expect(store.get(first)!.updatedAt).toBeGreaterThan(before);
  });

  it('sorts newest first', async () => {
    send.mockResolvedValue({ response: 'r', blocked: false });
    const store = useConversationsStore();
    store.load('u1');
    const a = await store.send(null, 'a');
    await new Promise((r) => setTimeout(r, 2));
    const b = await store.send(null, 'b');
    expect(store.sorted.map((c) => c.id)).toEqual([b, a]);
  });

  it('removes a conversation', async () => {
    send.mockResolvedValue({ response: 'r', blocked: false });
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'a');
    store.remove(id);
    expect(store.get(id)).toBeUndefined();
    expect(store.sorted).toHaveLength(0);
  });

  it('persists under the user key and reloads', async () => {
    send.mockResolvedValue({ response: 'r', blocked: false });
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'persisted');
    send.mockRejectedValueOnce(new ApiError('forbidden', 403));
    await store.send(id, 'bad');
    send.mockRejectedValueOnce(new ApiError('provider', 502));
    await store.send(id, 'flaky');

    const raw = localStorage.getItem(storageKey('u1'));
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toMatchObject({ version: 1 });

    setActivePinia(createPinia());
    const fresh = useConversationsStore();
    fresh.load('u1');
    expect(fresh.get(id)?.messages.map((m) => [m.role, m.status, m.text, m.errorKind])).toEqual([
      ['user', 'ok', 'persisted', undefined],
      ['assistant', 'ok', 'r', undefined],
      ['user', 'blocked', 'bad', undefined],
      ['user', 'ok', 'flaky', undefined],
      ['assistant', 'error', '', 'provider'],
    ]);
  });

  it('turns a sending placeholder left in storage into a retryable network error', async () => {
    pending();
    const store = useConversationsStore();
    store.load('u1');
    void store.send(null, 'hello');
    await Promise.resolve();
    const stuckId = store.sorted[0]!.id;

    setActivePinia(createPinia());
    const fresh = useConversationsStore();
    fresh.load('u1');
    expect(fresh.get(stuckId)!.messages.at(-1)).toMatchObject({
      role: 'assistant',
      status: 'error',
      errorKind: 'network',
      text: '',
    });

    send.mockResolvedValueOnce({ response: 'recovered', blocked: false });
    await fresh.retry(stuckId, fresh.get(stuckId)!.messages.at(-1)!.id);
    expect(fresh.get(stuckId)!.messages.at(-1)).toMatchObject({ status: 'ok', text: 'recovered' });
  });

  it('ignores a late reply for a conversation that was unloaded and reloaded', async () => {
    const first = pending();
    const store = useConversationsStore();
    store.load('u1');
    const firstSend = store.send(null, 'one');
    await Promise.resolve();
    const id = store.sorted[0]!.id;

    store.unload();
    expect(store.sending).toBe(false);
    store.load('u1');
    const second = pending();
    const secondSend = store.send(id, 'two');
    await Promise.resolve();
    expect(store.sending).toBe(true);

    first.resolve({ response: 'late', blocked: false });
    await firstSend;
    expect(store.sending).toBe(true);
    expect(store.get(id)!.messages.map((m) => m.text)).not.toContain('late');

    second.resolve({ response: 'fresh', blocked: false });
    await secondSend;
    expect(store.sending).toBe(false);
    expect(store.get(id)!.messages.at(-1)).toMatchObject({ status: 'ok', text: 'fresh' });
  });

  it('leaves a conversation removed mid-flight alone and releases the input', async () => {
    const { resolve } = pending();
    const store = useConversationsStore();
    store.load('u1');
    const promise = store.send(null, 'hello');
    await Promise.resolve();
    const conversation = store.sorted[0]!;

    store.remove(conversation.id);
    resolve({ response: 'late', blocked: false });
    await promise;

    expect(store.sending).toBe(false);
    expect(conversation.messages.at(-1)).toMatchObject({ status: 'sending' });
    expect(localStorage.getItem(storageKey('u1'))).not.toContain(conversation.id);
  });

  it('ignores send and retry while a request is in flight', async () => {
    send.mockRejectedValueOnce(new ApiError('provider', 502));
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'one');
    const errorId = store.get(id)!.messages.at(-1)!.id;

    const { resolve } = pending();
    const other = store.send(null, 'other');
    await Promise.resolve();
    expect(send).toHaveBeenCalledTimes(2);

    expect(await store.send(id, 'ignored')).toBe(id);
    expect(await store.send(null, 'ignored')).toBe('');
    await store.retry(id, errorId);
    expect(send).toHaveBeenCalledTimes(2);
    expect(store.get(id)!.messages).toHaveLength(2);
    expect(store.conversations).toHaveLength(2);

    resolve({ response: 'r', blocked: false });
    await other;
  });

  it('does not retry an error that is no longer the last message', async () => {
    send.mockRejectedValueOnce(new ApiError('provider', 502));
    const store = useConversationsStore();
    store.load('u1');
    const id = await store.send(null, 'one');
    const errorId = store.get(id)!.messages.at(-1)!.id;
    send.mockResolvedValueOnce({ response: 'r', blocked: false });
    await store.send(id, 'two');
    const before = JSON.stringify(store.get(id)!.messages);

    await store.retry(id, errorId);

    expect(send).toHaveBeenCalledTimes(2);
    expect(JSON.stringify(store.get(id)!.messages)).toBe(before);
  });

  it('keeps users apart', async () => {
    send.mockResolvedValue({ response: 'r', blocked: false });
    const store = useConversationsStore();
    store.load('u1');
    await store.send(null, 'mine');
    store.unload();
    store.load('u2');
    expect(store.sorted).toHaveLength(0);
  });

  it('resets on corrupt or mismatched storage', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    localStorage.setItem(storageKey('u1'), '{"version":99,"conversations":[{}]}');
    const store = useConversationsStore();
    store.load('u1');
    expect(store.sorted).toHaveLength(0);

    localStorage.setItem(storageKey('u1'), 'garbage');
    store.load('u1');
    expect(store.sorted).toHaveLength(0);
  });

  it('drops malformed stored conversations and keeps the valid ones', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const valid = {
      id: 'ok',
      title: 't',
      createdAt: 1,
      updatedAt: 2,
      messages: [{ id: 'm', role: 'user', text: 'hi', status: 'ok', createdAt: 1 }],
    };
    const badMessage = { ...valid, id: 'bad', messages: [{ id: 'm', role: 'robot' }] };
    localStorage.setItem(
      storageKey('u1'),
      JSON.stringify({ version: 1, conversations: [null, {}, badMessage, valid] }),
    );
    const store = useConversationsStore();
    store.load('u1');

    expect(store.sorted.map((c) => c.id)).toEqual(['ok']);
    expect(store.get('ok')!.messages).toHaveLength(1);
    expect(warn).toHaveBeenCalledOnce();
  });
});
