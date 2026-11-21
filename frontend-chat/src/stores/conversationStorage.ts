import { readJson, writeJson } from '@/storage/local';
import type { Conversation, Message } from './types';

const STORAGE_PREFIX = 'promptguard.chat.v1.';
const STORAGE_VERSION = 1;

const ROLES: readonly unknown[] = ['user', 'assistant'];
const STATUSES: readonly unknown[] = ['sending', 'ok', 'blocked', 'error'];
const ERROR_KINDS: readonly unknown[] = ['provider', 'network', 'http'];

interface StoredState {
  version: number;
  conversations: Conversation[];
}

export function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}${userId}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function isMessage(value: unknown): value is Message {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.text === 'string' &&
    typeof value.createdAt === 'number' &&
    ROLES.includes(value.role) &&
    STATUSES.includes(value.status) &&
    (value.errorKind === undefined || ERROR_KINDS.includes(value.errorKind))
  );
}

export function isConversation(value: unknown): value is Conversation {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.title === 'string' &&
    typeof value.createdAt === 'number' &&
    typeof value.updatedAt === 'number' &&
    Array.isArray(value.messages) &&
    value.messages.every(isMessage)
  );
}

/** A placeholder can only be in flight in the tab that created it; after a reload it is lost. */
function recoverStuckSends(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((m) =>
      m.status === 'sending' ? { ...m, status: 'error', errorKind: 'network', text: '' } : m,
    ),
  };
}

/** Reads a user's conversations, dropping anything that does not match the expected shape. */
export function readConversations(userId: string): Conversation[] {
  const stored = readJson<unknown>(storageKey(userId));
  if (stored === null) {
    return [];
  }
  if (
    !isRecord(stored) ||
    stored.version !== STORAGE_VERSION ||
    !Array.isArray(stored.conversations)
  ) {
    console.warn('conversation storage has an unexpected shape, starting empty');
    return [];
  }
  const valid = stored.conversations.filter(isConversation);
  if (valid.length !== stored.conversations.length) {
    console.warn(
      `dropped ${stored.conversations.length - valid.length} malformed stored conversation(s)`,
    );
  }
  return valid.map(recoverStuckSends);
}

export function writeConversations(userId: string, conversations: Conversation[]): void {
  writeJson(storageKey(userId), {
    version: STORAGE_VERSION,
    conversations,
  } satisfies StoredState);
}
