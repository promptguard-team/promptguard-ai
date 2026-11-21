import { createPinia } from 'pinia';
import { Quasar } from 'quasar';
import type { Plugin } from 'vue';
import { i18n } from '@/i18n';

/** Plugins every component test mounts with. Use as `global: { plugins: appPlugins() }`. */
export function appPlugins(): Array<Plugin | [Plugin, unknown]> {
  return [[Quasar, {}], createPinia(), i18n];
}
