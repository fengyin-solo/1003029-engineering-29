import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { waitUntilReady } from './api/readiness'
import { renderBootStatus } from './boot'
import './styles/global.css'

const container = document.getElementById('app') as HTMLElement

// 后端没就绪之前不挂载页面：先把探测进度画出来，就绪了再挂载应用
waitUntilReady((report) => renderBootStatus(container, report)).then(() => {
  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.mount('#app')
})
