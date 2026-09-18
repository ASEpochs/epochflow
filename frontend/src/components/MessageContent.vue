<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
const props = defineProps({ content: { type: String, default: '' } })
const html = computed(() => DOMPurify.sanitize(marked.parse(props.content, { breaks: true }), { USE_PROFILES: { html: true } }))
</script>
<template><div class="markdown-body" v-html="html"></div></template>
