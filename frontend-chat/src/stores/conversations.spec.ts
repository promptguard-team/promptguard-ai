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

    const raw = localStorage.getItem(storageKey('u1'));
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toMatchObject({ version: 1 });

    setActivePinia(createPinia());
    const fresh = useConversationsStore();
    fresh.load('u1');
    expect(fresh.get(id)?.messages).toHaveLength(2);
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
});
