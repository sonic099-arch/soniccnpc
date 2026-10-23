import {defineConfig,loadEnv} from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig(({mode})=>{
 const target=loadEnv(mode,'.','BEITIAN_').BEITIAN_API_URL||'http://127.0.0.1:8000'
 return {plugins:[vue()],server:{proxy:{'/api':target,'/health':target,'/ready':target}},test:{exclude:['e2e/**','node_modules/**','dist/**']}}
})
