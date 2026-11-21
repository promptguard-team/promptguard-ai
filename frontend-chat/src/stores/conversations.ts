import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { sendPrompt } from '@/api/chat';
import { ApiError } from '@/api/client';
import { newId } from '@/ids';
import { readJson, writeJson } from '@/storage/local';
import type { Conversation, Message, MessageErrorKind } from './types';

const STORAGE_PREFIX = 'promptguard.chat.v1.';
const STORAGE_VERSION = 1;
const TITLE_MAX = 40;

export const PROMPT_MAX = 32000;

interface StoredState {
  version: number;
  conversations: Conversation[];
}

export function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}${userId}`;
}

export function makeTitle(text: string): string {
  const compact = text.trim().replace(/\s+/g, ' ');
  return compact.length <= TITLE_MAX ? compact : `${compact.slice(0, TITLE_MAX - 1)}…`;
}

function isStoredState(value: unknown): value is StoredState {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as StoredState).version === STORAGE_VERSION &&
    Array.isArray((value as StoredState).conversations)
  );
}

function errorKindOf(error: unknown): MessageErrorKind {
  if (error instanceof ApiError) {
    if (error.kind === 'provider') return 'provider';
    if (error.kind === 'network') return 'network';
    return 'http';
  }
  return 'network';
}

export const useConversationsStore = defineStore('conversations', () => {
  const conversations = ref<Conversation[]>([]);
  const userId = ref<string | null>(null);
  const sending = ref(false);

  const sorted = computed(() => [...conversations.value].sort((a, b) => b.updatedAt - a.updatedAt));

  function load(id: string): void {
    userId.value = id;
    const stored = readJson<unknown>(storageKey(id));
    if (stored === null) {
      conversations.value = [];
      return;
    }
    if (!isStoredState(stored)) {
      console.warn('conversation storage has an unexpected shape, starting empty');
      conversations.value = [];
      return;
    }
    conversations.value = stored.conversations;
  }

  function unload(): void {
    userId.value = null;
    conversations.value = [];
  }

  function persist(): void {
    if (userId.value === null) {
      return;
    }
    writeJson(storageKey(userId.value), {
      version: STORAGE_VERSION,
      conversations: conversations.value,
    } satisfies StoredState);
  }

  function get(id: string): Conversation | undefined {
    return conversations.value.find((c) => c.id === id);
  }

  function has(id: string): boolean {
    return get(id) !== undefined;
  }

  function remove(id: string): void {
    conversations.value = conversations.value.filter((c) => c.id !== id);
    persist();
  }

  /** Appends a user message (creating the conversation when needed) and requests a reply. */
  async function send(conversationId: string | null, text: string): Promise<string> {
    const now = Date.now();
    let conversation = conversationId === null ? undefined : get(conversationId);
    if (conversation === undefined) {
      conversations.value.push({
        id: newId(),
        title: makeTitle(text),
        createdAt: now,
        updatedAt: now,
        messages: [],
      });
      // Re-read through the reactive array; the pushed literal is not reactive.
      conversation = conversations.value[conversations.value.length - 1]!;
    }
    conversation.messages.push({ id: newId(), role: 'user', text, status: 'ok', createdAt: now });
    await deliver(conversation, text);
    return conversation.id;
  }

  /** Re-sends the prompt that produced an error message, replacing that message. */
  async function retry(conversationId: string, messageId: string): Promise<void> {
    const conversation = get(conversationId);
    if (conversation === undefined) {
      return;
    }
    const index = conversation.messages.findIndex((m) => m.id === messageId);
    if (index === -1 || conversation.messages[index]!.status !== 'error') {
      return;
    }
    const prompt = conversation.messages.slice(0, index).findLast((m) => m.role === 'user');
    if (prompt === undefined) {
      return;
    }
    conversation.messages.splice(index, 1);
    await deliver(conversation, prompt.text);
  }

  async function deliver(conversation: Conversation, prompt: string): Promise<void> {
    conversation.messages.push({
      id: newId(),
      role: 'assistant',
      text: '',
      status: 'sending',
      createdAt: Date.now(),
    });
    const placeholder: Message = conversation.messages[conversation.messages.length - 1]!;
    conversation.updatedAt = Date.now();
    sending.value = true;
    persist();
    try {
      const result = await sendPrompt(prompt);
      placeholder.status = result.blocked ? 'blocked' : 'ok';
      placeholder.text = result.blocked ? '' : result.response;
    } catch (error) {
      applyFailure(conversation, placeholder, error);
    } finally {
      conversation.updatedAt = Date.now();
      sending.value = false;
      persist();
    }
  }

  function applyFailure(conversation: Conversation, placeholder: Message, error: unknown): void {
    if (error instanceof ApiError && error.kind === 'forbidden') {
      conversation.messages.splice(conversation.messages.indexOf(placeholder), 1);
      const userMessage = conversation.messages.findLast((m) => m.role === 'user');
      if (userMessage !== undefined) {
        userMessage.status = 'blocked';
      }
      return;
    }
    placeholder.status = 'error';
    placeholder.errorKind = errorKindOf(error);
  }

  return { conversations, userId, sending, sorted, load, unload, get, has, remove, send, retry };
});
