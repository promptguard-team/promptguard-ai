import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { Quasar, Dark } from 'quasar';
import '@quasar/extras/material-icons/material-icons.css';
import 'quasar/src/css/index.sass';
import './styles/app.sass';
import App from './App.vue';
import { configureClient } from './api/client';
import { i18n } from './i18n';
import { router } from './router';
import { useAuthStore } from './stores/auth';
import { useConversationsStore } from './stores/conversations';
import { resetGuardState } from './router/guard';

const app = createApp(App);
app.use(createPinia());
app.use(Quasar, { plugins: { Dark }, config: { dark: true } });
app.use(i18n);

const auth = useAuthStore();
const conversations = useConversationsStore();
configureClient({
  getToken: () => auth.token,
  onUnauthorized: () => {
    auth.clearSession();
    conversations.unload();
    resetGuardState();
    void router.push({ path: '/login', query: { reason: 'expired' } });
  },
});

app.use(router);
app.mount('#app');
