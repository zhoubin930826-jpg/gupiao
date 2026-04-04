<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <div class="page-header glass-card">
    <div>
      <p class="subhead">研究工作流</p>
      <h3>{{ title }}</h3>
      <p class="description">{{ description }}</p>
    </div>
    <div class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 24px;
  align-items: flex-start;
}

.subhead {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
}

h3 {
  margin: 0 0 10px;
  font-size: 32px;
  color: var(--text);
}

.description {
  margin: 0;
  max-width: 760px;
  line-height: 1.7;
  color: var(--text-soft);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
