<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import {
  askDeepSeek,
  createCategory,
  deleteCategory,
  deleteDocument,
  getDocument,
  importDocument,
  listCategory,
  listDocument,
  searchDocument,
  updateCategory,
  updateDocument,
  createDocument,
} from './api'

const activeView = ref('docs')
const categories = ref([])
const documents = ref([])
const total = ref(0)
const selectedCategoryId = ref(null)
const keyword = ref('')
const searchResults = ref([])
const loading = ref(false)
const toast = ref('')
const fileInput = ref(null)
const searchInput = ref(null)
const questionInput = ref(null)

const newCategoryName = ref('')
const showCreateCategory = ref(false)
const createCategoryInput = ref(null)
const editCategoryId = ref(null)
const editCategoryName = ref('')

const question = ref('')
const chatMessages = ref([])
const asking = ref(false)
const enableWebSearch = ref(true)

const previewOpen = ref(false)
const previewDoc = ref(null)
const previewKeyword = ref('')
const previewMatchTerms = ref([])
const previewBody = ref(null)
const previewEditing = ref(false)
const previewEditTitle = ref('')
const previewEditContent = ref('')
const previewSaving = ref(false)

const createDocOpen = ref(false)
const createDocTitle = ref('')
const createDocContent = ref('')
const createDocSaving = ref(false)
const createDocTitleInput = ref(null)

const selectedLabel = computed(() => {
  if (selectedCategoryId.value == null) return '全部资料'
  const found = findCategory(categories.value, selectedCategoryId.value)
  return found ? found.name : '全部资料'
})

const viewTitle = computed(() => {
  if (activeView.value === 'search') return '搜索结果'
  if (activeView.value === 'chat') return '问答结果'
  return '资料列表'
})

const resultScopeLabel = computed(() => selectedLabel.value)

const searchHint = computed(() =>
  selectedCategoryId.value == null
    ? '在全部资料中模糊查询'
    : `仅在「${selectedLabel.value}」中模糊查询`,
)

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function collectTerms(rawKeyword, extraTerms = []) {
  const keyword = String(rawKeyword || '').trim()
  const terms = []
  if (keyword) {
    terms.push(keyword)
    keyword.split(/\s+/).forEach((item) => {
      if (item) terms.push(item)
    })
  }
  ;(extraTerms || []).forEach((item) => {
    if (item) terms.push(String(item))
  })
  return Array.from(new Set(terms)).sort((a, b) => b.length - a.length)
}

function wrapHit(match, markFirstState) {
  if (markFirstState && !markFirstState.done) {
    markFirstState.done = true
    return `<mark id="keyword-hit-anchor" class="keyword-hit keyword-hit-current" style="color:#d32f2f;background:rgba(211,47,47,.28);font-weight:700;padding:0 2px;">${match}</mark>`
  }
  return `<mark class="keyword-hit" style="color:#d32f2f;background:rgba(211,47,47,.14);font-weight:700;padding:0 2px;">${match}</mark>`
}

function highlightText(text, rawKeyword, options = {}) {
  const markFirst = Boolean(options.markFirst)
  const extraTerms = options.terms || []
  const markFirstState = markFirst ? { done: false } : null
  let source = String(text || '')

  // 后端用 ⟦词⟧ 标记命中时，优先按标记渲染
  if (source.includes('⟦') && source.includes('⟧')) {
    let result = ''
    const markerReg = /⟦([\s\S]*?)⟧/g
    let lastIndex = 0
    let match = markerReg.exec(source)
    while (match) {
      result += escapeHtml(source.slice(lastIndex, match.index))
      result += wrapHit(escapeHtml(match[1]), markFirstState)
      lastIndex = match.index + match[0].length
      match = markerReg.exec(source)
    }
    result += escapeHtml(source.slice(lastIndex))
    return result
  }

  // 无标记时按关键字/分词标红
  let result = escapeHtml(source)
  const terms = collectTerms(rawKeyword, extraTerms)
  const pattern = terms
    .map((token) => escapeHtml(token).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .filter(Boolean)
    .join('|')
  if (!pattern) return result
  return result.replace(new RegExp(`(${pattern})`, 'gi'), (m) => wrapHit(m, markFirstState))
}

const previewHighlightedHtml = computed(() => {
  if (!previewDoc.value) return ''
  if (!previewKeyword.value) {
    return escapeHtml(previewDoc.value.contentText || '')
  }
  return highlightText(previewDoc.value.contentText || '', previewKeyword.value, {
    markFirst: true,
    terms: previewMatchTerms.value,
  })
})

function showToast(message) {
  toast.value = message
  setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 2600)
}

function findCategory(list, id) {
  for (const item of list) {
    if (item.id === id) return item
    const child = findCategory(item.children || [], id)
    if (child) return child
  }
  return null
}

async function switchView(view) {
  activeView.value = view
  await nextTick()
  if (view === 'search') {
    searchInput.value?.focus()
  }
  if (view === 'chat') {
    questionInput.value?.focus()
  }
}

async function refreshCategories() {
  const res = await listCategory({})
  categories.value = res.data || []
}

async function refreshDocuments() {
  const payload = {
    page: 1,
    pageSize: 50,
  }
  if (selectedCategoryId.value != null) {
    payload.categoryId = selectedCategoryId.value
  }
  const res = await listDocument(payload)
  documents.value = res.data?.items || []
  total.value = res.data?.total || 0
}

async function bootstrap() {
  loading.value = true
  try {
    await refreshCategories()
    await refreshDocuments()
  } catch (error) {
    showToast(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function openCreateCategory() {
  showCreateCategory.value = true
  await nextTick()
  createCategoryInput.value?.focus()
}

async function onCreateCategory() {
  const name = newCategoryName.value.trim()
  if (!name) {
    showToast('请输入分类名称')
    return
  }
  try {
    await createCategory({
      name,
      parentId: selectedCategoryId.value,
      sort: 0,
    })
    newCategoryName.value = ''
    showCreateCategory.value = false
    await refreshCategories()
    showToast('分类已创建')
  } catch (error) {
    showToast(error.message)
  }
}

async function onStartEdit(category) {
  editCategoryId.value = category.id
  editCategoryName.value = category.name
}

async function onSaveEdit() {
  if (!editCategoryId.value) return
  const name = editCategoryName.value.trim()
  if (!name) {
    showToast('分类名称不能为空')
    return
  }
  try {
    await updateCategory({ id: editCategoryId.value, name })
    editCategoryId.value = null
    editCategoryName.value = ''
    await refreshCategories()
    showToast('分类已更新')
  } catch (error) {
    showToast(error.message)
  }
}

async function onDeleteCategory(category) {
  if (!window.confirm(`确认删除分类「${category.name}」？`)) return
  try {
    await deleteCategory({ id: category.id })
    if (selectedCategoryId.value === category.id) {
      selectedCategoryId.value = null
    }
    await refreshCategories()
    await refreshDocuments()
    showToast('分类已删除')
  } catch (error) {
    showToast(error.message)
  }
}

async function selectCategory(id) {
  selectedCategoryId.value = id
  await refreshDocuments()
  if (activeView.value === 'search' && keyword.value.trim()) {
    await onSearch()
  } else if (activeView.value === 'search') {
    searchResults.value = []
  }
}

function triggerImport() {
  if (selectedCategoryId.value == null) {
    showToast('请先在上方「分类管理」中选择一个分类')
    return
  }
  if (!categories.value.length) {
    showToast('请先新建分类，再导入资料')
    return
  }
  fileInput.value?.click()
}

async function openCreateDocument() {
  if (selectedCategoryId.value == null) {
    showToast('请先在上方「分类管理」中选择一个分类')
    return
  }
  createDocOpen.value = true
  createDocTitle.value = ''
  createDocContent.value = ''
  switchView('docs')
  await nextTick()
  createDocTitleInput.value?.focus()
}

function closeCreateDocument() {
  if (createDocSaving.value) return
  createDocOpen.value = false
  createDocTitle.value = ''
  createDocContent.value = ''
}

async function saveCreateDocument() {
  if (selectedCategoryId.value == null) {
    showToast('请先选择分类')
    return
  }
  const title = createDocTitle.value.trim()
  if (!title) {
    showToast('请输入文档标题')
    return
  }
  createDocSaving.value = true
  try {
    const res = await createDocument({
      title,
      categoryId: selectedCategoryId.value,
      contentText: createDocContent.value,
    })
    const created = res.data
    createDocOpen.value = false
    createDocTitle.value = ''
    createDocContent.value = ''
    switchView('docs')
    await refreshDocuments()
    showToast('文档已创建')
    if (created?.id) {
      await onPreview({ id: created.id })
    }
  } catch (error) {
    showToast(error.message)
  } finally {
    createDocSaving.value = false
  }
}

async function onUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (selectedCategoryId.value == null) {
    showToast('请先在上方「分类管理」中选择一个分类')
    if (fileInput.value) fileInput.value.value = ''
    return
  }
  loading.value = true
  try {
    await importDocument({
      file,
      categoryId: selectedCategoryId.value,
      title: file.name.replace(/\.[^.]+$/, ''),
    })
    switchView('docs')
    await refreshDocuments()
    showToast(`已导入到「${selectedLabel.value}」`)
  } catch (error) {
    showToast(error.message)
  } finally {
    loading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function onSearch() {
  const value = keyword.value.trim()
  if (!value) {
    searchResults.value = []
    switchView('docs')
    await refreshDocuments()
    return
  }
  try {
    const payload = { keyword: value, limit: 50 }
    // 选中分类则只搜该分类；选中「全部资料」则搜全部
    if (selectedCategoryId.value != null) {
      payload.categoryId = selectedCategoryId.value
    }
    const res = await searchDocument(payload)
    searchResults.value = res.data || []
    switchView('search')
  } catch (error) {
    showToast(error.message)
  }
}

async function onDeleteDocument(doc) {
  if (!window.confirm(`确认删除文档「${doc.title}」？`)) return
  try {
    await deleteDocument({ id: doc.id })
    await refreshDocuments()
    searchResults.value = searchResults.value.filter((item) => item.id !== doc.id)
    showToast('文档已删除')
  } catch (error) {
    showToast(error.message)
  }
}

function closePreview() {
  if (previewSaving.value) return
  previewOpen.value = false
  previewDoc.value = null
  previewKeyword.value = ''
  previewMatchTerms.value = []
  previewEditing.value = false
  previewEditTitle.value = ''
  previewEditContent.value = ''
}

function startEditPreview() {
  if (!previewDoc.value) return
  previewEditing.value = true
  previewEditTitle.value = previewDoc.value.title || ''
  previewEditContent.value = previewDoc.value.contentText || ''
  previewKeyword.value = ''
  previewMatchTerms.value = []
}

function cancelEditPreview() {
  previewEditing.value = false
  previewEditTitle.value = ''
  previewEditContent.value = ''
}

async function savePreviewDocument() {
  if (!previewDoc.value) return
  const title = previewEditTitle.value.trim()
  if (!title) {
    showToast('标题不能为空')
    return
  }
  previewSaving.value = true
  try {
    const res = await updateDocument({
      id: previewDoc.value.id,
      title,
      contentText: previewEditContent.value,
    })
    previewDoc.value = res.data
    previewEditing.value = false
    await refreshDocuments()
    if (activeView.value === 'search' && keyword.value.trim()) {
      await onSearch()
    }
    showToast('文档已保存')
  } catch (error) {
    showToast(error.message)
  } finally {
    previewSaving.value = false
  }
}

function onGlobalKeydown(event) {
  if (event.key !== 'Escape') return
  if (createDocOpen.value) {
    closeCreateDocument()
    return
  }
  if (previewOpen.value) {
    if (previewEditing.value) {
      cancelEditPreview()
      return
    }
    closePreview()
  }
}

async function scrollToKeywordHit() {
  await nextTick()
  await nextTick()
  const anchor = document.getElementById('keyword-hit-anchor')
  const container = previewBody.value
  if (!anchor || !container) return
  const containerRect = container.getBoundingClientRect()
  const anchorRect = anchor.getBoundingClientRect()
  const offset = anchorRect.top - containerRect.top + container.scrollTop - container.clientHeight / 3
  container.scrollTo({ top: Math.max(offset, 0), behavior: 'smooth' })
}

async function onPreview(doc, options = {}) {
  const locateKeyword = Boolean(options.locateKeyword)
  const terms = options.terms || doc.matchTerms || []
  try {
    const res = await getDocument({ id: doc.id })
    previewDoc.value = res.data
    previewEditing.value = false
    previewEditTitle.value = ''
    previewEditContent.value = ''
    previewKeyword.value = locateKeyword ? keyword.value.trim() : ''
    previewMatchTerms.value = locateKeyword ? terms : []
    previewOpen.value = true
    if (previewKeyword.value) {
      await scrollToKeywordHit()
    } else if (previewBody.value) {
      previewBody.value.scrollTop = 0
    }
  } catch (error) {
    showToast(error.message)
  }
}

function onOpenSearchDoc(doc) {
  onPreview(doc, { locateKeyword: true, terms: doc.matchTerms || [] })
}

async function onAsk() {
  const text = question.value.trim()
  if (!text) return
  switchView('chat')
  chatMessages.value.push({ role: 'user', content: text })
  question.value = ''
  asking.value = true
  try {
    const payload = {
      question: text,
      topK: 5,
      enableWebSearch: enableWebSearch.value,
      webCount: 5,
    }
    if (selectedCategoryId.value != null) {
      payload.categoryId = selectedCategoryId.value
    }
    const res = await askDeepSeek(payload)
    chatMessages.value.push({
      role: 'assistant',
      content: res.data?.answer || '',
      sources: res.data?.sources || [],
      webUsed: Boolean(res.data?.webUsed),
    })
  } catch (error) {
    chatMessages.value.push({
      role: 'assistant',
      content: `调用失败：${error.message}`,
      sources: [],
      webUsed: false,
    })
  } finally {
    asking.value = false
  }
}

onMounted(() => {
  bootstrap()
  window.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <h1 class="brand">资料文档库</h1>
        <span class="scope-pill">当前：{{ resultScopeLabel }}</span>
      </div>
      <div class="topbar-actions">
        <button class="btn secondary" :disabled="loading" @click="bootstrap">刷新</button>
        <button
          class="btn secondary"
          :disabled="loading || selectedCategoryId == null"
          @click="triggerImport"
        >
          导入
        </button>
        <button
          class="btn"
          :disabled="loading || selectedCategoryId == null"
          @click="openCreateDocument"
        >
          新建文档
        </button>
        <input
          ref="fileInput"
          type="file"
          hidden
          accept=".txt,.md,.pdf,.docx"
          @change="onUpload"
        />
      </div>
    </header>

    <div class="layout">
      <aside class="side-panel">
        <div class="side-head">
          <h2>分类</h2>
          <button
            class="icon-btn"
            title="新建分类"
            aria-label="新建分类"
            @click="openCreateCategory"
          >
            ➕
          </button>
        </div>

        <div v-if="showCreateCategory" class="stack create-category-box">
          <input
            ref="createCategoryInput"
            v-model="newCategoryName"
            class="input"
            placeholder="输入分类名称"
            @keyup.enter="onCreateCategory"
            @keyup.esc="showCreateCategory = false"
          />
          <div class="toolbar">
            <button class="btn" @click="onCreateCategory">确定</button>
            <button class="btn ghost" @click="showCreateCategory = false">取消</button>
          </div>
        </div>

        <ul class="category-list">
          <li class="category-item" :class="{ active: selectedCategoryId === null }">
            <button class="name" @click="selectCategory(null)">全部资料</button>
          </li>
          <li v-for="item in categories" :key="item.id">
            <div class="category-item" :class="{ active: selectedCategoryId === item.id }">
              <button class="name" @click="selectCategory(item.id)">{{ item.name }}</button>
              <div class="category-actions">
                <button
                  class="icon-btn tiny"
                  title="修改分类"
                  aria-label="修改分类"
                  @click="onStartEdit(item)"
                >
                  ✏️
                </button>
                <button
                  class="icon-btn tiny danger"
                  title="删除分类"
                  aria-label="删除分类"
                  @click="onDeleteCategory(item)"
                >
                  🗑️
                </button>
              </div>
            </div>
            <ul v-if="item.children?.length" class="category-children">
              <li v-for="child in item.children" :key="child.id">
                <div class="category-item" :class="{ active: selectedCategoryId === child.id }">
                  <button class="name" @click="selectCategory(child.id)">{{ child.name }}</button>
                  <div class="category-actions">
                    <button
                      class="icon-btn tiny"
                      title="修改分类"
                      aria-label="修改分类"
                      @click="onStartEdit(child)"
                    >
                      ✏️
                    </button>
                    <button
                      class="icon-btn tiny danger"
                      title="删除分类"
                      aria-label="删除分类"
                      @click="onDeleteCategory(child)"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              </li>
            </ul>
          </li>
        </ul>

        <div v-if="editCategoryId" class="stack edit-box">
          <input v-model="editCategoryName" class="input" placeholder="修改分类名" />
          <div class="toolbar">
            <button class="btn secondary" @click="onSaveEdit">保存</button>
            <button class="btn ghost" @click="editCategoryId = null">取消</button>
          </div>
        </div>

        <p class="side-tip muted">选中分类后，浏览 / 搜索 / 问答 / 新建导入都只作用于该分类</p>
      </aside>

      <main class="main-panel">
        <nav class="view-tabs">
          <button
            class="tab-item"
            :class="{ active: activeView === 'docs' }"
            @click="switchView('docs')"
          >
            资料浏览
          </button>
          <button
            class="tab-item"
            :class="{ active: activeView === 'search' }"
            @click="switchView('search')"
          >
            模糊搜索
          </button>
          <button
            class="tab-item"
            :class="{ active: activeView === 'chat' }"
            @click="switchView('chat')"
          >
            DeepSeek 问答
          </button>
        </nav>

        <section v-if="activeView === 'search'" class="workspace-bar">
          <div class="workspace-bar-text">
            <strong>{{ viewTitle }}</strong>
            <span class="muted">{{ searchHint }}</span>
          </div>
          <div class="search-row">
            <input
              ref="searchInput"
              v-model="keyword"
              class="input"
              :placeholder="selectedCategoryId == null ? '输入关键词，检索全部资料' : `输入关键词，检索「${selectedLabel}」`"
              @keyup.enter="onSearch"
            />
            <button class="btn" @click="onSearch">搜索</button>
          </div>
        </section>

        <section v-else-if="activeView === 'chat'" class="workspace-bar chat-bar">
          <div class="workspace-bar-text">
            <strong>{{ viewTitle }}</strong>
            <span class="muted">
              知识库范围：{{ selectedLabel }}
              {{ selectedCategoryId == null ? '（全部）' : '（仅当前分类）' }}
            </span>
          </div>
          <label class="check-row">
            <input v-model="enableWebSearch" type="checkbox" />
            <span>同时联网搜索</span>
          </label>
          <div class="ask-row">
            <textarea
              ref="questionInput"
              v-model="question"
              class="textarea"
              placeholder="输入问题，Ctrl + Enter 发送"
              @keyup.ctrl.enter="onAsk"
            />
            <button class="btn" :disabled="asking" @click="onAsk">
              {{ asking ? '思考中...' : '提问' }}
            </button>
          </div>
        </section>

        <section v-else class="workspace-bar">
          <div class="workspace-bar-text">
            <strong>{{ viewTitle }}</strong>
            <span class="muted">共 {{ total }} 条 · 范围 {{ resultScopeLabel }}</span>
          </div>
        </section>

        <div v-if="activeView === 'docs'" class="result-body">
          <div v-if="!documents.length" class="empty">
            暂无文档。请先选择左侧分类，再点右上角「新建文档」或「导入」
          </div>
          <div v-else class="doc-grid">
            <article v-for="item in documents" :key="item.id" class="doc-card">
              <h3>{{ item.title }}</h3>
              <div v-if="item.fileType !== 'note'" class="doc-meta">{{ item.fileName }}</div>
              <p class="muted">{{ item.contentPreview }}</p>
              <div class="doc-actions">
                <button class="btn secondary" @click="onPreview(item)">查看</button>
                <button class="btn danger" @click="onDeleteDocument(item)">删除</button>
              </div>
            </article>
          </div>
        </div>

        <div v-else-if="activeView === 'search'" class="result-body">
          <div v-if="!keyword.trim()" class="empty">在上方输入关键词后搜索</div>
          <div v-else-if="!searchResults.length" class="empty">未找到相关资料</div>
          <div v-else class="doc-list">
            <article
              v-for="item in searchResults"
              :key="'s-' + item.id"
              class="doc-card clickable"
              @click="onOpenSearchDoc(item)"
            >
              <h3 v-html="highlightText(item.title, keyword, { terms: item.matchTerms || [] })"></h3>
              <div class="doc-meta">{{ item.fileName }} · 相关度 {{ item.score }}</div>
              <p
                class="search-snippet"
                v-html="highlightText(item.snippet, keyword, { terms: item.matchTerms || [] })"
              ></p>
              <div class="doc-actions" @click.stop>
                <button class="btn secondary" @click="onOpenSearchDoc(item)">定位查看</button>
                <button class="btn danger" @click="onDeleteDocument(item)">删除</button>
              </div>
            </article>
          </div>
        </div>

        <div v-else class="result-body chat-result">
          <div v-if="!chatMessages.length" class="empty">在上方输入问题后开始问答</div>
          <div v-else class="chat-log">
            <div
              v-for="(msg, index) in chatMessages"
              :key="index"
              class="bubble"
              :class="msg.role"
            >
              <div class="bubble-role">
                {{ msg.role === 'user' ? '我' : 'DeepSeek' }}
                <span v-if="msg.role === 'assistant' && msg.webUsed" class="web-tag">已联网</span>
              </div>
              <div>{{ msg.content }}</div>
              <div v-if="msg.sources?.length" class="sources">
                引用：
                <div v-for="(src, i) in msg.sources" :key="i">
                  <template v-if="src.sourceType === 'web'">
                    {{ i + 1 }}. [网页] {{ src.title }}
                    <a v-if="src.url" :href="src.url" target="_blank" rel="noopener noreferrer">打开</a>
                  </template>
                  <template v-else>
                    {{ i + 1 }}. [知识库] {{ src.title }}
                    <template v-if="src.chunkIndex != null">（片段{{ src.chunkIndex + 1 }}）</template>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <div v-if="createDocOpen" class="modal-mask" @click="closeCreateDocument">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <div class="modal-title-wrap">
            <h3>新建文档</h3>
            <p class="muted">将保存到分类：{{ selectedLabel }}</p>
          </div>
          <div class="toolbar modal-actions">
            <button class="btn" type="button" :disabled="createDocSaving" @click="saveCreateDocument">
              {{ createDocSaving ? '创建中...' : '创建' }}
            </button>
            <button class="btn secondary" type="button" :disabled="createDocSaving" @click="closeCreateDocument">
              取消
            </button>
          </div>
        </div>
        <div class="stack create-doc-form">
          <input
            ref="createDocTitleInput"
            v-model="createDocTitle"
            class="input"
            placeholder="文档标题"
            @keyup.enter="saveCreateDocument"
          />
          <textarea
            v-model="createDocContent"
            class="preview-editor create-doc-editor"
            placeholder="输入文档内容（可先留空，创建后再编辑）"
          ></textarea>
        </div>
      </div>
    </div>

    <div v-if="previewOpen" class="modal-mask" @click="closePreview">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <div class="modal-title-wrap">
            <template v-if="previewEditing">
              <input v-model="previewEditTitle" class="input" placeholder="文档标题" />
              <p v-if="previewDoc?.fileType !== 'note'" class="muted">{{ previewDoc?.fileName }}</p>
            </template>
            <template v-else>
              <h3
                v-if="previewKeyword"
                v-html="highlightText(previewDoc?.title || '', previewKeyword)"
              ></h3>
              <h3 v-else>{{ previewDoc?.title }}</h3>
              <p v-if="previewDoc?.fileType !== 'note' || previewKeyword" class="muted">
                <template v-if="previewDoc?.fileType !== 'note'">{{ previewDoc?.fileName }}</template>
                <span v-if="previewKeyword">
                  <template v-if="previewDoc?.fileType !== 'note'"> · </template>
                  已定位到关键字「{{ previewKeyword }}」
                </span>
              </p>
            </template>
          </div>
          <div class="toolbar modal-actions">
            <template v-if="previewEditing">
              <button class="btn" type="button" :disabled="previewSaving" @click="savePreviewDocument">
                {{ previewSaving ? '保存中...' : '保存' }}
              </button>
              <button class="btn secondary" type="button" :disabled="previewSaving" @click="cancelEditPreview">
                取消
              </button>
            </template>
            <template v-else>
              <button class="btn secondary" type="button" @click="startEditPreview">编辑</button>
              <button class="btn ghost" type="button" @click="closePreview">关闭</button>
            </template>
          </div>
        </div>
        <div ref="previewBody" class="modal-body">
          <textarea
            v-if="previewEditing"
            v-model="previewEditContent"
            class="preview-editor"
            placeholder="在此编辑文档内容"
          ></textarea>
          <pre
            v-else
            class="preview-content"
            v-html="previewHighlightedHtml"
          ></pre>
        </div>
        <p class="muted modal-hint">
          {{ previewEditing ? '编辑后点击保存；Esc 取消编辑' : '点击空白区域或按 Esc 关闭' }}
        </p>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>
