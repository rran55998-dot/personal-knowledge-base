async function request(path, options = {}) {
  const response = await fetch(path, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = data.detail || data.message || `请求失败(${response.status})`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return data
}

export function createCategory(payload) {
  return request('/api/createCategory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateCategory(payload) {
  return request('/api/updateCategory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteCategory(payload) {
  return request('/api/deleteCategory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function listCategory(payload = {}) {
  return request('/api/listCategory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function listDocument(payload) {
  return request('/api/listDocument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteDocument(payload) {
  return request('/api/deleteDocument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getDocument(payload) {
  return request('/api/getDocument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateDocument(payload) {
  return request('/api/updateDocument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function createDocument(payload) {
  return request('/api/createDocument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function searchDocument(payload) {
  return request('/api/searchDocument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function askDeepSeek(payload) {
  return request('/api/askDeepSeek', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function importDocument({ file, categoryId, title }) {
  const form = new FormData()
  form.append('file', file)
  if (categoryId != null && categoryId !== '') {
    form.append('categoryId', String(categoryId))
  }
  if (title) {
    form.append('title', title)
  }
  return request('/api/importDocument', {
    method: 'POST',
    body: form,
  })
}
