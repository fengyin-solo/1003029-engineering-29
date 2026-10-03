import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { waitForBackend } from './ready'
import './styles/global.css'

async function bootstrap(): Promise<void> {
  const container = document.getElementById('app')
  if (!container) {
    throw new Error('找不到 #app 挂载点')
  }
  // 就绪门：后端没就绪先不挂载页面（等待页由 ready.ts 用纯 DOM 渲染），探到就绪再挂载
  await waitForBackend(container)
  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.mount('#app')
}

void bootstrap()
