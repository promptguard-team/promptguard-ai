import { request } from './client';

export interface ChatResponse {
  response: string;
  blocked: boolean;
}

export function sendPrompt(prompt: string): Promise<ChatResponse> {
  return request<ChatResponse>('POST', '/chat', { prompt });
}
