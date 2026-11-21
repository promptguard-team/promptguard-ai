import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { sendPrompt } from '@/api/chat';
import { ApiError } from '@/api/client';
import { newId } from '@/ids';
import { readConversations, writeConversations } from './conversationStorage';
import type { Conversation, Message, MessageErrorKind } from './types';

export { storageKey } from './conversationStorage';

const TITLE_MAX = 40;

export const PROMPT_MAX = 32000;

export function makeTitle(text: string): string {
  const compact = text.trim().replace(/\s+/g, ' ');
  return compact.length <= TITLE_MAX ? compact : `${compact.slice(0, TITLE_MAX - 1)}…`;
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
  /** Identifies the request that owns `sending`; a stale request must not release it. */
  let activeRequest: symbol | null = null;

  const sorted = computed(() => [...conversations.value].sort((a, b) => b.updatedAt - a.updatedAt));

  function load(id: string): void {
    userId.value = id;
    conversations.value = readConversations(id);
  }

  function unload(): void {
    userId.value = null;
    conversations.value = [];
    sending.value = false;
    activeRequest = null;
  }

  function persist(): void {
    if (userId.value !== null) {
      writeConversations(userId.value, conversations.value);
    }
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

  /**
   * Creates an empty conversation titled after `text` and returns its id. Lets callers route to
   * a new conversation before its first reply arrives.
   */
  function create(text: string): string {
    const now = Date.now();
    const id = newId();
    conversations.value.push({
      id,
      title: makeTitle(text),
      createdAt: now,
      updatedAt: now,
      messages: [],
    });
    persist();
    return id;
  }

  /**
   * Appends a user message (creating the conversation when needed) and requests a reply.
   * Resolves to the conversation id. While another request is in flight this is a no-op that
   * resolves to the given id, or '' when none was given, so callers never navigate on it.
   */
  async function send(conversationId: string | null, text: string): Promise<string> {
    if (sending.value) {
      return conversationId ?? '';
    }
    // Read through the reactive array; a freshly pushed literal is not reactive.
    const conversation =
      (conversationId === null ? undefined : get(conversationId)) ?? get(create(text))!;
    conversation.messages.push({
      id: newId(),
      role: 'user',
      text,
      status: 'ok',
      createdAt: Date.now(),
    });
    await deliver(conversation, text);
    return conversation.id;
  }

  /**
   * Re-sends the prompt that produced an error message, replacing that message. Only the last
   * message of a conversation can be retried, and never while another request is in flight.
   */
  async function retry(conversationId: string, messageId: string): Promise<void> {
    const conversation = get(conversationId);
    if (sending.value || conversation === undefined) {
      return;
    }
    const last = conversation.messages.at(-1);
    if (last === undefined || last.id !== messageId || last.status !== 'error') {
      return;
    }
    const prompt = conversation.messages.findLast((m) => m.role === 'user');
    if (prompt === undefined) {
      return;
    }
    conversation.messages.pop();
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
    const request = Symbol('request');
    activeRequest = request;
    sending.value = true;
    persist();
    let settle: () => void;
    try {
      const result = await sendPrompt(prompt);
      settle = () => {
        placeholder.status = result.blocked ? 'blocked' : 'ok';
        placeholder.text = result.blocked ? '' : result.response;
      };
    } catch (error) {
      settle = () => applyFailure(conversation, placeholder, error);
    }
    if (activeRequest === request) {
      activeRequest = null;
      sending.value = false;
    }
    // The conversation may have been removed, or the store unloaded, while the request ran.
    if (get(conversation.id) !== conversation) {
      return;
    }
    settle();
    conversation.updatedAt = Date.now();
    persist();
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

  return {
    conversations,
    userId,
    sending,
    sorted,
    load,
    unload,
    get,
    has,
    remove,
    create,
    send,
    retry,
  };
});
