import {createRouter,createWebHistory} from 'vue-router'
import SkeletonPage from './views/SkeletonPage.vue'
export const navigation=[
 {path:'/',name:'系统首页',symbol:'◈'},
 {path:'/wells',name:'气井列表',symbol:'▤'},
 {path:'/anomalies',name:'异常井列表',symbol:'◇'},
 {path:'/analysis',name:'运行分析',symbol:'▷'},
 {path:'/import',name:'Excel导入',symbol:'↥'},
 {path:'/measures',name:'生产措施管理',symbol:'◷'},
 {path:'/rules',name:'规则配置',symbol:'⚙'},
]
const pages:Record<string,()=>Promise<unknown>>={
 '/':()=>import('./views/Dashboard.vue'),'/wells':()=>import('./views/WellList.vue'),
 '/anomalies':()=>import('./views/AnomalyList.vue'),'/import':()=>import('./views/DataImport.vue'),
 '/analysis':()=>import('./views/AnalysisWorkbench.vue'),'/rules':()=>import('./views/RuleConfiguration.vue'),
}
export default createRouter({history:createWebHistory(),scrollBehavior:()=>({top:0}),routes:[
 ...navigation.map(item=>({...item,component:pages[item.path]??SkeletonPage})),
 {path:'/wells/:id',name:'单井分析',component:()=>import('./views/WellDetail.vue')},
 {path:'/:pathMatch(.*)*',redirect:'/'},
]})
