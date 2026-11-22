<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useAuthStore } from '@/stores/auth';
import { toggleTheme } from '@/theme';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

// With show-if-above the drawer opens itself on wide screens and starts closed on narrow ones.
const drawerOpen = ref(false);

const navItems = [
  { to: '/', icon: 'dashboard', labelKey: 'nav.dashboard', exact: true },
  { to: '/events', icon: 'list_alt', labelKey: 'nav.events', exact: false },
];

const title = computed(() => t(route.meta.titleKey ?? 'app.name'));

async function logout(): Promise<void> {
  auth.clearSession();
  await router.push('/login');
}
</script>

<template>
  <q-layout view="lHh LpR lFf">
    <q-header bordered :class="$q.dark.isActive ? 'bg-dark text-white' : 'bg-white text-dark'">
      <q-toolbar>
        <q-btn
          flat
          round
          dense
          icon="menu"
          class="lt-md"
          :aria-label="t('layout.toggleDrawer')"
          @click="drawerOpen = !drawerOpen"
        />
        <q-toolbar-title class="text-weight-medium" data-test="title">{{ title }}</q-toolbar-title>
        <q-btn
          flat
          round
          dense
          icon="contrast"
          :aria-label="t('layout.toggleTheme')"
          @click="toggleTheme"
        />
        <span class="q-mx-sm text-body2 gt-xs" data-test="user-email">{{ auth.user?.email }}</span>
        <q-btn
          flat
          dense
          no-caps
          icon="logout"
          data-test="logout"
          :label="t('layout.logout')"
          @click="logout"
        />
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="drawerOpen"
      show-if-above
      dark
      :breakpoint="1023"
      :width="240"
      class="admin-drawer"
    >
      <div class="q-px-lg q-py-lg text-h6 text-white">
        PromptGuard <span class="text-primary">CISO</span>
      </div>
      <q-list>
        <q-item
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          :exact="item.exact"
          clickable
          active-class="admin-drawer__item--active"
        >
          <q-item-section avatar>
            <q-icon :name="item.icon" />
          </q-item-section>
          <q-item-section>{{ t(item.labelKey) }}</q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>
