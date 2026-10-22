<script setup lang="ts">
import { navigation } from './router'
</script>
<template>
  <el-container class="layout">
    <el-aside width="230px">
      <h2>北田气井</h2><p class="subtitle">智能分析系统 · 第一阶段</p>
      <el-menu router :default-active="$route.path">
        <el-menu-item v-for="item in navigation" :key="item.path" :index="item.path">{{ item.name }}</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container><el-header>气井生产异常筛查 <el-tag type="info">任务3 · 规则筛查</el-tag></el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>
<style>
body{margin:0;font-family:"PingFang SC","Microsoft YaHei",sans-serif;color:#233c46;background:#f2f6f7}
.layout{min-height:100vh} .el-aside{background:white;border-right:1px solid #e1e9eb}
h2{padding:16px 24px 0;color:#17776d}.subtitle{padding:0 24px;color:#71848b;font-size:12px}
.el-header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e1e9eb;background:white}
.el-menu{border-right:0}.el-main{padding:32px}.el-card{max-width:1050px}p{line-height:1.8}
</style>
