import { describe, expect, it } from 'vitest';
import { QTable } from 'quasar';
import { mount } from '@vue/test-utils';
import type { AuditEventPage } from '@/api/audit';
import { appPlugins } from '@/test/plugins';
import { defaultEventFilters, type EventFilters } from './eventQuery';
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

function mountTable(data: AuditEventPage | null = page, error = false) {
  return mount(EventsTable, {
    props: { page: data, loading: false, error, filters: defaultEventFilters() },
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
    const flag = row.get('[data-test="flagged-icon"]');
    expect(flag.attributes('role')).toBe('img');
    expect(flag.attributes('aria-label')).toBe('Oflagowane');
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

  it('hides the empty message under an error', () => {
    expect(mountTable(null, true).text()).not.toContain('Brak zdarzeń dla wybranych filtrów.');
  });

  describe('server-side pagination', () => {
    const big: AuditEventPage = { ...page, total: 120, limit: 25, offset: 25 };
    const mountPaged = (pageNo: number) =>
      mount(EventsTable, {
        props: {
          page: big,
          loading: false,
          error: false,
          filters: { ...defaultEventFilters(), page: pageNo },
        },
        global: { plugins: appPlugins() },
      });

    it('follows the page and total props', () => {
      expect(mountPaged(2).get('.q-table__bottom').text()).toContain('26–50 z 120');
    });

    it('emits the next page', async () => {
      const wrapper = mountPaged(2);
      await wrapper.findAll('.q-table__bottom button')[2]!.trigger('click');
      expect(wrapper.emitted('paginate')).toEqual([[3, 25]]);
    });

    it('emits the requested page size', () => {
      const wrapper = mountPaged(2);
      wrapper
        .findComponent(QTable)
        .vm.$emit('request', { pagination: { page: 1, rowsPerPage: 50 } });
      expect(wrapper.emitted('paginate')).toEqual([[1, 50]]);
    });

    it('updates the label when the page prop changes', async () => {
      const wrapper = mountPaged(2);
      await wrapper.setProps({ filters: { ...defaultEventFilters(), page: 3 } as EventFilters });
      expect(wrapper.get('.q-table__bottom').text()).toContain('51–75 z 120');
    });
  });
});
