<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { getStrategyConfig, updateStrategyConfig } from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import type { StrategyConfig } from '@/types/market'

const form = reactive<StrategyConfig>({
  technical_weight: 35,
  fundamental_weight: 25,
  money_flow_weight: 25,
  sentiment_weight: 15,
  rebalance_cycle: 'weekly',
  min_turnover: 2.5,
  min_listing_days: 180,
  exclude_st: true,
  exclude_new_shares: true,
})

const totalWeight = computed(
  () =>
    form.technical_weight +
    form.fundamental_weight +
    form.money_flow_weight +
    form.sentiment_weight,
)

async function loadConfig() {
  Object.assign(form, await getStrategyConfig())
}

async function saveConfig() {
  if (totalWeight.value !== 100) {
    ElMessage.warning('四个维度权重之和需要等于 100。')
    return
  }

  Object.assign(form, await updateStrategyConfig({ ...form }))
  ElMessage.success('策略配置已保存。')
}

onMounted(() => {
  void loadConfig()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="先把推荐系统的第一套规则调顺，再考虑更复杂的模型"
      description="策略页是你后续不断迭代推荐系统的核心入口。当前版本先支持维度权重、调仓周期和股票池过滤，后面适合继续补财务因子、行业中性化和回测参数。"
    >
      <template #actions>
        <el-button type="primary" @click="saveConfig">保存策略</el-button>
      </template>
    </PageHeader>

    <section class="section-grid strategy-grid">
      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>评分权重</span>
            <el-tag :type="totalWeight === 100 ? 'success' : 'warning'">
              当前合计 {{ totalWeight }}
            </el-tag>
          </div>
        </template>

        <div class="slider-list">
          <div class="slider-item">
            <div class="slider-head">
              <span>技术面</span>
              <strong>{{ form.technical_weight }}</strong>
            </div>
            <el-slider v-model="form.technical_weight" :max="100" />
          </div>

          <div class="slider-item">
            <div class="slider-head">
              <span>基本面</span>
              <strong>{{ form.fundamental_weight }}</strong>
            </div>
            <el-slider v-model="form.fundamental_weight" :max="100" />
          </div>

          <div class="slider-item">
            <div class="slider-head">
              <span>资金面</span>
              <strong>{{ form.money_flow_weight }}</strong>
            </div>
            <el-slider v-model="form.money_flow_weight" :max="100" />
          </div>

          <div class="slider-item">
            <div class="slider-head">
              <span>情绪面</span>
              <strong>{{ form.sentiment_weight }}</strong>
            </div>
            <el-slider v-model="form.sentiment_weight" :max="100" />
          </div>
        </div>
      </el-card>

      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>股票池约束</span>
            <span class="hint">先保守一点更稳</span>
          </div>
        </template>

        <el-form label-position="top" class="strategy-form">
          <el-form-item label="调仓周期">
            <el-select v-model="form.rebalance_cycle">
              <el-option label="日频" value="daily" />
              <el-option label="周频" value="weekly" />
              <el-option label="双周" value="biweekly" />
            </el-select>
          </el-form-item>

          <el-form-item label="最低换手率 (%)">
            <el-input-number v-model="form.min_turnover" :min="0" :step="0.1" />
          </el-form-item>

          <el-form-item label="最少上市天数">
            <el-input-number v-model="form.min_listing_days" :min="30" :step="30" />
          </el-form-item>

          <div class="switch-row">
            <div class="switch-item">
              <div>
                <strong>排除 ST 股票</strong>
                <p>避免高风险或基本面异常标的。</p>
              </div>
              <el-switch v-model="form.exclude_st" />
            </div>

            <div class="switch-item">
              <div>
                <strong>排除次新股</strong>
                <p>减少因历史样本不足导致的噪声。</p>
              </div>
              <el-switch v-model="form.exclude_new_shares" />
            </div>
          </div>
        </el-form>
      </el-card>
    </section>
  </div>
</template>

<style scoped>
.strategy-grid {
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 1fr);
}

.card-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.hint {
  color: var(--text-faint);
  font-size: 13px;
}

.slider-list {
  display: grid;
  gap: 22px;
}

.slider-item {
  display: grid;
  gap: 10px;
}

.slider-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.slider-head strong {
  color: var(--accent);
}

.strategy-form {
  display: grid;
  gap: 4px;
}

.switch-row {
  display: grid;
  gap: 14px;
}

.switch-item {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.06);
}

.switch-item p {
  margin: 6px 0 0;
  color: var(--text-soft);
}

@media (max-width: 960px) {
  .strategy-grid {
    grid-template-columns: 1fr;
  }

  .switch-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
