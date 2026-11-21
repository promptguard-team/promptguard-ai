import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { Quasar, Dark } from 'quasar';
import '@quasar/extras/material-icons/material-icons.css';
import 'quasar/src/css/index.sass';
import './styles/app.sass';
import App from './App.vue';
import { i18n } from './i18n';

const app = createApp(App);
app.use(createPinia());
app.use(Quasar, { plugins: { Dark }, config: { dark: true } });
app.use(i18n);
app.mount('#app');
