<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { ApiError } from '@/api/client';
import { NotCisoError, useAuthStore } from '@/stores/auth';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const email = ref('');
const password = ref('');
const submitting = ref(false);
const error = ref<string | null>(null);

const reasonMessage = computed(() => {
  switch (route.query.reason) {
    case 'expired':
      return t('login.sessionExpired');
    case 'forbidden':
      return t('login.forbidden');
    default:
      return null;
  }
});

function messageFor(e: unknown): string {
  if (e instanceof NotCisoError) {
    return t('login.forbidden');
  }
  if (e instanceof ApiError && e.kind === 'unauthorized') {
    return t('login.invalidCredentials');
  }
  return t('login.genericError');
}

async function submit(): Promise<void> {
  if (submitting.value) {
    return;
  }
  error.value = null;
  submitting.value = true;
  try {
    await auth.login(email.value.trim(), password.value);
    await router.push('/');
  } catch (e) {
    error.value = messageFor(e);
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

          <q-card-section v-if="reasonMessage" class="q-pt-none">
            <q-banner
              dense
              rounded
              data-test="reason"
              :class="$q.dark.isActive ? 'bg-grey-9 text-grey-3' : 'bg-grey-3 text-grey-9'"
              >{{ reasonMessage }}</q-banner
            >
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
                :rules="[(v: string) => !!v?.trim() || t('login.required')]"
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
              <div v-if="error" role="alert" class="text-negative text-body2">{{ error }}</div>
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
