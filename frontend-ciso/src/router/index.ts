import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import LoginPage from '@/features/auth/LoginPage.vue';
import { authGuard } from './guard';

export const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: LoginPage },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
];

export const router = createRouter({
  // BASE_URL is '/ciso/' (vite.config.ts), so routes stay prefix-free.
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  return authGuard(to, {
    bootstrap: () => auth.bootstrap(),
    isAuthenticated: () => auth.isAuthenticated,
  });
});
