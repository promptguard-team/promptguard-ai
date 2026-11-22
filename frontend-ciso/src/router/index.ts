import { createRouter, createWebHistory, type Router, type RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import LoginPage from '@/features/auth/LoginPage.vue';
import AdminLayout from '@/features/layout/AdminLayout.vue';
import DashboardPage from '@/features/dashboard/DashboardPage.vue';
import EventsPage from '@/features/events/EventsPage.vue';
import { authGuard } from './guard';

export const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: LoginPage },
  {
    path: '/',
    component: AdminLayout,
    // Child routes inherit this through to.meta.
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'dashboard',
        component: DashboardPage,
        meta: { titleKey: 'nav.dashboard' },
      },
      { path: 'events', name: 'events', component: EventsPage, meta: { titleKey: 'nav.events' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

/** Installs the auth guard; the store is resolved lazily so pinia must be active by then. */
export function installGuard(target: Router): void {
  target.beforeEach((to) => {
    const auth = useAuthStore();
    return authGuard(to, {
      bootstrap: () => auth.bootstrap(),
      isAuthenticated: () => auth.isAuthenticated,
      takeEndReason: () => {
        const reason = auth.endReason;
        auth.endReason = null;
        return reason;
      },
    });
  });
}

export const router = createRouter({
  // BASE_URL is '/ciso/' (vite.config.ts), so routes stay prefix-free.
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

installGuard(router);
