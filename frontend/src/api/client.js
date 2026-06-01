import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60_000,
})

/**
 * Upload files and create a reconstruction job.
 * @param {File[]} files
 * @param {Object} params  — inference parameters
 * @param {Function} onProgress — (0-100) upload progress callback
 */
export async function createJob(files, params, onProgress) {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      form.append(key, String(value))
    }
  }

  const { data } = await api.post('/jobs', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0, // no timeout for large uploads
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
  return data
}

/** Fetch all jobs. */
export async function listJobs() {
  const { data } = await api.get('/jobs')
  return data
}

/** Fetch a single job by ID. */
export async function getJob(jobId) {
  const { data } = await api.get(`/jobs/${jobId}`)
  return data
}

/** Delete a job and its associated files. */
export async function deleteJob(jobId) {
  const { data } = await api.delete(`/jobs/${jobId}`)
  return data
}

/** Health check. */
export async function getHealth() {
  const { data } = await api.get('/health')
  return data
}

/** Return the URL of the result GLB for a completed job. */
export function resultUrl(jobId) {
  return `/api/jobs/${jobId}/result`
}

/**
 * Open a WebSocket to stream job progress.
 * @param {string} jobId
 * @param {{ onMessage, onClose }} callbacks
 * @returns WebSocket instance
 */
export function watchJob(jobId, { onMessage, onClose } = {}) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/api/jobs/${jobId}/ws`)

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      onMessage?.(msg)
    } catch {
      /* ignore parse errors */
    }
  }

  ws.onclose = () => onClose?.()

  return ws
}
