export type MessageRole = 'user' | 'assistant';
export type MessageStatus = 'sending' | 'ok' | 'blocked' | 'error';
export type MessageErrorKind = 'provider' | 'network' | 'http';

export interface Message {
  id: string;
  role: MessageRole;
  text: string;
  status: MessageStatus;
  /** Only set when status === 'error'. */
  errorKind?: MessageErrorKind;
  createdAt: number;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}
