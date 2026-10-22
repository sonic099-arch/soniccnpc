import { createRouter, createWebHistory } from 'vue-router'
import SkeletonPage from './views/SkeletonPage.vue'
export const navigation = [
  {path:'/', name:'系统首页'},
  {path:'/wells', name:'气井列表'},
  {path:'/anomalies', name:'异常井列表'},
  {path:'/import', name:'Excel导入'},
  {path:'/measures', name:'生产措施管理'},
  {path:'/rules', name:'规则配置'},
]
export default createRouter({history:createWebHistory(), routes:[
  ...navigation.map(item=>({...item,component:SkeletonPage})),
  {path:'/wells/:id',name:'单井分析',component:SkeletonPage},
  {path:'/:pathMatch(.*)*',redirect:'/'},
]})
