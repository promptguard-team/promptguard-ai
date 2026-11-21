import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useConversationsStore } from '@/stores/conversations';
import LoginPage from '@/features/auth/LoginPage.vue';
import ChatLayout from '@/features/chat/ChatLayout.vue';
import { authGuard, CONVERSATION_ROUTE } from './guard';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginPage },
    { path: '/', name: 'home', component: ChatLayout, meta: { requiresAuth: true } },
    {
      path: '/c/:id',
      name: CONVERSATION_ROUTE,
      component: ChatLayout,
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  const conversations = useConversationsStore();
  return authGuard(to, {
    bootstrap: () => auth.bootstrap(),
    isAuthenticated: () => auth.isAuthenticated,
    userId: () => auth.user?.id ?? null,
    loadConversations: (userId) => conversations.load(userId),
    hasConversation: (id) => conversations.has(id),
  });
});
