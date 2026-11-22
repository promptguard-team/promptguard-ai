import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import type { AuditEventPage } from '@/api/audit';
import { appPlugins } from '@/test/plugins';
import { defaultEventFilters } from './eventQuery';
import EventsTable from './EventsTable.vue';

const page: AuditEventPage = {
  items: [
    {
      id: 'e1',
      created_at: '2026-11-20T10:00:00Z',
      user_id: 'u1',
      user_email: 'jan@example.com',
      action: 'blocked_prompt',
      rule: null,
      ml_status: 'ok',
      ml_score: 0.9731,
      ml_label: 'injection',
      ml_model_version: null,
      flagged: true,
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
};

function mountTable(data: AuditEventPage | null = page) {
  return mount(EventsTable, {
    props: { page: data, loading: false, filters: defaultEventFilters() },
    global: { plugins: appPlugins() },
  });
}

describe('EventsTable', () => {
  it('renders event metadata with dashes for missing values', () => {
    const row = mountTable().get('tbody tr');

    expect(row.text()).toContain('jan@example.com');
    expect(row.text()).toContain('Zablokowany prompt');
    expect(row.text()).toContain('OK');
    expect(row.text()).toContain('0.97');
    expect(row.text()).toContain('injection');
    expect(row.text()).toContain('—');
    expect(row.find('[data-test="flagged-icon"]').exists()).toBe(true);
  });

  it('filters by a user when the email is clicked', async () => {
    const wrapper = mountTable();

    await wrapper.get('[data-test="user-link"]').trigger('click');

    expect(wrapper.emitted('filterUser')).toEqual([['u1', 'jan@example.com']]);
  });

  it('shows the empty message', () => {
    expect(mountTable({ items: [], total: 0, limit: 25, offset: 0 }).text()).toContain(
      'Brak zdarzeń dla wybranych filtrów.',
    );
  });
});
