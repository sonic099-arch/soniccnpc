<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount,watch} from 'vue'
import {init,use,type ECharts,type EChartsCoreOption} from 'echarts/core'
import {LineChart,BarChart,PieChart} from 'echarts/charts'
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,MarkLineComponent,MarkAreaComponent,TitleComponent,AriaComponent} from 'echarts/components'
import {SVGRenderer} from 'echarts/renderers'
use([LineChart,BarChart,PieChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,MarkLineComponent,MarkAreaComponent,TitleComponent,AriaComponent,SVGRenderer])
const props=withDefaults(defineProps<{option:EChartsCoreOption;height?:string;label:string;group?:string}>(),{height:'320px'})
const host=ref<HTMLElement>();let chart:ECharts|undefined,observer:ResizeObserver|undefined
onMounted(()=>{if(!host.value)return;chart=init(host.value,undefined,{renderer:'svg'});if(props.group)chart.group=props.group;chart.setOption(props.option);observer=new ResizeObserver(()=>chart?.resize());observer.observe(host.value)})
watch(()=>props.option,v=>chart?.setOption(v,{notMerge:true}))
onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose()})
</script>
<template><div ref="host" :style="{height,width:'100%'}" role="img" :aria-label="label"/></template>
