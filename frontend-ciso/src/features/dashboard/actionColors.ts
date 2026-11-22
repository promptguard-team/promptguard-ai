import type { AuditAction } from '@/api/audit';

/** Semantic chart colours: green allowed, two reds for blocks, grey provider errors. */
export const ACTION_COLORS: Record<AuditAction, string> = {
  allowed: '#22c55e',
  blocked_prompt: '#ef4444',
  blocked_response: '#b91c1c',
  provider_error: '#94a3b8',
};
