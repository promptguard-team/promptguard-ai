<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { ApiError } from '@/api/client';
import { useAuthStore } from '@/stores/auth';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const email = ref('');
const password = ref('');
const submitting = ref(false);
const error = ref<string | null>(null);

const expired = computed(() => route.query.reason === 'expired');

async function submit(): Promise<void> {
  error.value = null;
  submitting.value = true;
  try {
    await auth.login(email.value.trim(), password.value);
    await router.push('/');
  } catch (e) {
    error.value =
      e instanceof ApiError && e.kind === 'unauthorized'
        ? t('login.invalidCredentials')
        : t('login.genericError');
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <q-page class="flex flex-center">
        <q-card flat bordered class="login-card">
          <q-card-section>
            <div class="text-h6">{{ t('app.name') }}</div>
            <div class="text-subtitle2 text-grey-6">{{ t('login.title') }}</div>
          </q-card-section>

          <q-card-section v-if="expired" class="q-pt-none">
            <q-banner dense rounded class="bg-grey-9 text-grey-3">{{
              t('login.sessionExpired')
            }}</q-banner>
          </q-card-section>

          <q-card-section>
            <q-form class="column q-gutter-md" @submit.prevent="submit">
              <q-input
                v-model="email"
                type="email"
                outlined
                dense
                autocomplete="username"
                :label="t('login.email')"
                :rules="[(v: string) => !!v || t('login.required')]"
              />
              <q-input
                v-model="password"
                type="password"
                outlined
                dense
                autocomplete="current-password"
                :label="t('login.password')"
                :rules="[(v: string) => !!v || t('login.required')]"
              />
              <div v-if="error" class="text-negative text-body2">{{ error }}</div>
              <q-btn
                type="submit"
                color="primary"
                unelevated
                no-caps
                :loading="submitting"
                :label="t('login.submit')"
              />
            </q-form>
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped lang="sass">
.login-card
  width: 100%
  max-width: 380px
  margin: 16px
</style>
