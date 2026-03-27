import { useState, useRef, useCallback, useEffect } from 'react'
import axios, { type AxiosError } from 'axios'
import type {
  FileItem, Settings, ProcessResult,
  AuthUser, LoginResponse, ParsedCVData,
} from './types'
import TrainingPanel from './TrainingPanel'
import ReviewPanel from './ReviewPanel'

// ── Auth state ────────────────────────────────────────────────
interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
}

// ── PUBLIC MODE: auto-logged-in as admin for team testing ────
function loadAuth(): AuthState {
  return {
    user: {
      id: 'public-user',
      email: 'public@cvformat.local',
      full_name: 'Team User',
      role: 'admin',
      is_active: true,
    },
    accessToken: 'public-mode',
    refreshToken: null,
  }
}

// ── Default settings ───────────────────────────────────────────
const DEFAULT_SETTINGS: Settings = {
  apiKey: '',
  openaiApiKey: '',
  model: 'claude-sonnet-4-20250514',
  openaiModel: 'gpt-4o-mini',
  extractionMode: 'offline',
  backendUrl: (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000',
}

// ── Helpers ────────────────────────────────────────────────────
function uid() {
  return Math.random().toString(36).slice(2, 10)
}

function formatTime() {
  return new Date().toLocaleTimeString('en-US', { hour12: false })
}

function stripExtension(name: string) {
  return name.replace(/\.[^.]+$/, '')
}

// ── Settings Modal ─────────────────────────────────────────────
interface SettingsModalProps {
  settings: Settings
  onSave: (s: Settings) => void
  onClose: () => void
}

function SettingsModal({ settings, onSave, onClose }: SettingsModalProps) {
  const [s, setS] = useState<Settings>({ ...settings })

  const modes: { value: Settings['extractionMode']; label: string }[] = [
    { value: 'offline',      label: 'Offline Rule Engine (No API)' },
    { value: 'auto',         label: 'Auto (Claude → OpenAI → Ollama)' },
    { value: 'claude_api',   label: 'Claude API Only' },
    { value: 'openai_api',   label: 'OpenAI API Only' },
    { value: 'ollama',       label: 'Ollama Only (local)' },
    { value: 'cached',       label: 'Cached (no AI)' },
  ]

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">Settings</span>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <span className="form-label">Backend URL</span>
            <input
              type="text"
              value={s.backendUrl}
              onChange={e => setS({ ...s, backendUrl: e.target.value })}
              placeholder="http://localhost:8000"
              style={{ flex: 1, padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}
            />
          </div>

          <div style={{ borderTop: '1px solid #F0F2F5', margin: '12px 0', paddingTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--navy)', marginBottom: 10 }}>CLAUDE API</div>
            <div className="form-row">
              <span className="form-label">API Key</span>
              <input
                type="password"
                value={s.apiKey}
                onChange={e => setS({ ...s, apiKey: e.target.value })}
                placeholder="sk-ant-..."
                style={{ flex: 1, padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}
              />
            </div>
            <div className="form-row">
              <span className="form-label">Model</span>
              <input
                type="text"
                value={s.model}
                onChange={e => setS({ ...s, model: e.target.value })}
                placeholder="claude-sonnet-4-20250514"
                style={{ flex: 1, padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}
              />
            </div>
          </div>

          <div style={{ borderTop: '1px solid #F0F2F5', margin: '12px 0', paddingTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--navy)', marginBottom: 10 }}>OPENAI API (FALLBACK)</div>
            <div className="form-row">
              <span className="form-label">API Key</span>
              <input
                type="password"
                value={s.openaiApiKey}
                onChange={e => setS({ ...s, openaiApiKey: e.target.value })}
                placeholder="sk-..."
                style={{ flex: 1, padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}
              />
            </div>
            <div className="form-row">
              <span className="form-label">Model</span>
              <input
                type="text"
                value={s.openaiModel}
                onChange={e => setS({ ...s, openaiModel: e.target.value })}
                placeholder="gpt-4o-mini"
                style={{ flex: 1, padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}
              />
            </div>
          </div>

          <div style={{ borderTop: '1px solid #F0F2F5', margin: '12px 0', paddingTop: 12 }}>
            <div className="form-row" style={{ alignItems: 'flex-start' }}>
              <span className="form-label" style={{ paddingTop: 4 }}>Extraction</span>
              <div className="radio-group" style={{ flex: 1 }}>
                {modes.map(m => (
                  <label key={m.value} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', marginBottom: 4 }}>
                    <input
                      type="radio"
                      name="mode"
                      value={m.value}
                      checked={s.extractionMode === m.value}
                      onChange={() => setS({ ...s, extractionMode: m.value })}
                    />
                    {m.label}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => { onSave(s); onClose() }}>
            Save
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Login Modal ───────────────────────────────────────────────
interface LoginModalProps {
  onSuccess: (user: AuthUser, accessToken: string, refreshToken: string) => void
  onClose: () => void
  backendUrl: string
}

function LoginModal({ onSuccess, onClose, backendUrl }: LoginModalProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await axios.post<LoginResponse>(
        `${backendUrl}/auth/login`,
        { email, password },
        { headers: { 'Content-Type': 'application/json' } }
      )
      onSuccess(res.data.user, res.data.access_token, res.data.refresh_token)
    } catch (err) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data as { detail?: string })?.detail ?? err.message
        : (err instanceof Error ? err.message : 'Login failed')
      setError(typeof msg === 'string' ? msg : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 380 }}>
        <div className="modal-header">
          <span className="modal-title">🔐 Đăng nhập</span>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--navy)', marginBottom: 4 }}>Email</div>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoFocus
                style={{ width: '100%', padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
                placeholder="admin@ns.vn"
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--navy)', marginBottom: 4 }}>Password</div>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                style={{ width: '100%', padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
                placeholder="••••••••"
              />
            </div>
            {error && (
              <div style={{ background: '#FEE2E2', border: '1px solid #EF4444', borderRadius: 6, padding: '6px 10px', fontSize: 12, color: '#991B1B' }}>
                ❌ {error}
              </div>
            )}
            <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF' }}>
              Liên hệ Admin để được cấp tài khoản.
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn" onClick={onClose}>Hủy</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? '⏳...' : 'Đăng nhập'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Axios auth interceptor ─────────────────────────────────────
// Refreshes access token when expired; re-attempts original request.
axios.interceptors.response.use(
  res => res,
  async (err: AxiosError) => {
    const orig = err.config as (typeof err.config & { _retry?: boolean }) | undefined
    if (
      err.response?.status === 401 &&
      orig && !orig._retry &&
      !orig.url?.includes('/auth/')
    ) {
      orig._retry = true
      try {
        const auth = loadAuth()
        if (!auth.refreshToken) throw new Error('No refresh token')
        const refreshRes = await axios.post<{ access_token: string }>(
          `${DEFAULT_SETTINGS.backendUrl}/auth/refresh`,
          { refresh_token: auth.refreshToken },
          { headers: { 'Content-Type': 'application/json' } }
        )
        const newToken = refreshRes.data.access_token
        const newAuth = { ...auth, accessToken: newToken }
        localStorage.setItem('cvformat-auth-v2', JSON.stringify(newAuth))
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
        orig.headers.Authorization = `Bearer ${newToken}`
        return axios(orig)
      } catch {
        localStorage.removeItem('cvformat-auth-v2')
        delete axios.defaults.headers.common['Authorization']
        window.location.reload()
        return Promise.reject(err)
      }
    }
    return Promise.reject(err)
  }
)

// ── Main App ──────────────────────────────────────────────────
export default function App() {
  const [files, setFiles] = useState<FileItem[]>([])
  const [logs, setLogs] = useState<string[]>([])
  const [settings, setSettings] = useState<Settings>(() => {
    try {
      const saved = localStorage.getItem('cvformat-settings-v2')
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS
    } catch {
      return DEFAULT_SETTINGS
    }
  })
  // ── Auth state ───────────────────────────────────────────────
  const [auth, setAuth] = useState<AuthState>(loadAuth)
  const [showLogin, setShowLogin] = useState(!loadAuth().user)

  // ── Review panel state ───────────────────────────────────────
  const [reviewFile, setReviewFile] = useState<FileItem | null>(null)
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [dragging, setDragging] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'process' | 'training'>('process')
  const [showSettings, setShowSettings] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  // Keep a ref so review callbacks don't go stale across renders
  const reviewFileRef = useRef<FileItem | null>(null)

  const addLog = useCallback((...lines: string[]) => {
    setLogs(prev => [...prev,
      ...lines.map(l => `[${formatTime()}] ${l}`)
    ])
    setTimeout(() => logEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }, [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }


  // ── Helpers ────────────────────────────────────────────────────
  function normalizeBackendUrl(url: string): string {
    return url.trim().replace(/\/+$/, '')
  }

  const openGuideline = () => {
    const url = `${normalizeBackendUrl(settings.backendUrl)}/guideline.pdf`
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  function isDownloadable(file: FileItem): boolean {
    return Boolean(file.downloadUrl || file.downloadId)
  }

  function getOutputFilename(file: FileItem): string {
    const trimmed = file.filename.trim()
    const baseName = trimmed ? stripExtension(trimmed) : 'output'
    return `${baseName}.docx`
  }

  function buildDownloadUrl(file: FileItem, backendUrl: string): string {
    const normalizedBackendUrl = normalizeBackendUrl(backendUrl)
    if (file.downloadUrl) {
      return file.downloadUrl.startsWith('http')
        ? file.downloadUrl
        : `${normalizedBackendUrl}/${file.downloadUrl.replace(/^\/+/, '')}`
    }
    if (file.downloadId) {
      return `${normalizedBackendUrl}/download/${encodeURIComponent(file.downloadId)}`
    }
    return ''
  }

  async function downloadSingleFile(file: FileItem, backendUrl: string): Promise<void> {
    const url = buildDownloadUrl(file, backendUrl)
    if (!url) throw new Error('No download URL available')
    const normalizedBackendUrl = normalizeBackendUrl(backendUrl)
    const isExternalUrl = /^https?:\/\//i.test(url) && !url.startsWith(normalizedBackendUrl)

    if (isExternalUrl) {
      const link = document.createElement('a')
      link.href = url
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      document.body.appendChild(link)
      link.click()
      link.remove()
      return
    }

    const res = await fetch(url)
    if (!res.ok) throw new Error(`Download failed: ${res.status}`)
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = getOutputFilename(file)
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
  }

  async function handleSingleDownload(file: FileItem) {
    try {
      await downloadSingleFile(file, settings.backendUrl)
      addLog(`Downloaded: ${getOutputFilename(file)}`)
      showToast(`Downloading ${getOutputFilename(file)}...`)
    } catch {
      addLog(`Download failed: ${file.name}`)
      showToast(`Download failed: ${file.name}`)
    }
  }

  // ── Download ────────────────────────────────────────────────
  const downloadFiles = async () => {
    const downloadableFiles = files.filter(isDownloadable)
    if (downloadableFiles.length === 0) {
      showToast('No processed files to download')
      return
    }
    for (const file of downloadableFiles) {
      try {
        await downloadSingleFile(file, settings.backendUrl)
        addLog(`Downloaded: ${getOutputFilename(file)}`)
      } catch (err) {
        addLog(`Download failed: ${file.filename}`)
      }
    }
    showToast(`Downloading ${downloadableFiles.length} file(s)...`)
  }

  // Persist settings
  useEffect(() => {
    localStorage.setItem('cvformat-settings-v2', JSON.stringify(settings))
  }, [settings])

  // ── Auth: set Bearer token when auth changes ──────────────────
  useEffect(() => {
    if (auth.accessToken) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${auth.accessToken}`
    } else {
      delete axios.defaults.headers.common['Authorization']
    }
  }, [auth.accessToken])

  const handleLoginSuccess = useCallback((
    user: AuthUser,
    accessToken: string,
    refreshToken: string,
  ) => {
    const next: AuthState = { user, accessToken, refreshToken }
    localStorage.setItem('cvformat-auth-v2', JSON.stringify(next))
    setAuth(next)
    setShowLogin(false)
    addLog(`✅ Đăng nhập thành công: ${user.full_name} (${user.role})`)
  }, [addLog])


  // ── Review panel handlers ─────────────────────────────────────
  /**
   * Called when user clicks "Review" on a file in the list.
   * Fetches the full CVJob from the backend to get parsed_data + validation_result.
   */
  const handleOpenReview = useCallback(async (file: FileItem) => {
    reviewFileRef.current = file
    setReviewFile(file)
    if (!auth.accessToken || !file.job_id) return
    try {
      const res = await axios.get(`${settings.backendUrl}/jobs/${file.job_id}`, {
        headers: { Authorization: `Bearer ${auth.accessToken}` },
      })
      const job = res.data
      const updated = {
        ...file,
        cv_data: job.parsed_data,
        validation_result: job.validation_result,
      }
      reviewFileRef.current = updated
      setReviewFile(updated)
    } catch {
      // Fall back to whatever we already had
    }
  }, [auth.accessToken, settings.backendUrl])

  /**
   * "Save & continue" — calls PATCH /jobs/:id/review to persist edits.
   * Does NOT approve/export. Job stays in "review" status.
   */
  const handleReviewSave = useCallback(async (correctedData: ParsedCVData) => {
    const file = reviewFileRef.current
    if (!file?.job_id || !auth.accessToken) return
    setReviewSubmitting(true)
    try {
      await axios.patch(
        `${settings.backendUrl}/jobs/${file.job_id}/review`,
        { reviewed_data: correctedData },
        { headers: { Authorization: `Bearer ${auth.accessToken}`, 'Content-Type': 'application/json' } }
      )
      setFiles(prev => prev.map(f =>
        f.id === file.id ? { ...f, cv_data: correctedData } : f
      ))
      showToast('✅ Đã lưu chỉnh sửa')
      reviewFileRef.current = null
      setReviewFile(null)
    } catch (err) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data as { detail?: string })?.detail ?? err.message
        : (err instanceof Error ? err.message : 'Lưu thất bại')
      showToast(`❌ ${typeof msg === 'string' ? msg : 'Lưu thất bại'}`)
    } finally {
      setReviewSubmitting(false)
    }
  }, [auth.accessToken, settings.backendUrl])

  /**
   * "Approve & Export" — calls PATCH /review then POST /export.
   * Backend checks cv:override_export permission based on user role.
   * On success, persists data, updates file state, and auto-downloads.
   */
  const handleReviewApprove = useCallback(async (correctedData: ParsedCVData) => {
    const file = reviewFileRef.current
    if (!file?.job_id || !auth.accessToken) return
    setReviewSubmitting(true)
    try {
      // Step 1: Persist reviewed data
      await axios.patch(
        `${settings.backendUrl}/jobs/${file.job_id}/review`,
        { reviewed_data: correctedData },
        { headers: { Authorization: `Bearer ${auth.accessToken}`, 'Content-Type': 'application/json' } }
      )
      // Step 2: Trigger export
      const exportRes = await axios.post(
        `${settings.backendUrl}/jobs/${file.job_id}/export`,
        {},
        { headers: { Authorization: `Bearer ${auth.accessToken}` } }
      )
      const downloadId: string | undefined = exportRes.data?.download_id
      const downloadUrl: string | undefined = exportRes.data?.download_url
      // Update local file state
      setFiles(prev => prev.map(f =>
        f.id === file.id
          ? { ...f, status: 'success' as const, cv_data: correctedData, downloadId, downloadUrl, message: 'Phê duyệt thành công' }
          : f
      ))
      showToast('✅ Phê duyệt & đang tải file...')
      reviewFileRef.current = null
      setReviewFile(null)
      // Auto-download the exported DOCX
      if (downloadId) {
        const a = document.createElement('a')
        a.href = `${settings.backendUrl}/download/${encodeURIComponent(downloadId)}`
        a.download = `${file.filename}.docx`
        document.body.appendChild(a)
        a.click()
        a.remove()
      } else if (downloadUrl) {
        const a = document.createElement('a')
        a.href = downloadUrl
        a.download = `${file.filename}.docx`
        document.body.appendChild(a)
        a.click()
        a.remove()
      }
    } catch (err) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data as { detail?: string })?.detail ?? err.message
        : (err instanceof Error ? err.message : 'Export thất bại')
      showToast(`❌ ${typeof msg === 'string' ? msg : 'Export thất bại'}`)
    } finally {
      setReviewSubmitting(false)
    }
  }, [auth.accessToken, settings.backendUrl])

  // ── File handling ──────────────────────────────────────────
  const addFiles = (newFiles: File[]) => {
    const items: FileItem[] = newFiles
      .filter(f => /\.(pdf|docx)$/i.test(f.name))
      .map(f => ({
        id: uid(),
        name: f.name,
        filename: f.name.replace(/\.(pdf|docx)$/i, ''),
        type: (f.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX') as FileItem['type'],
        status: 'pending' as const,
        message: '',
        file: f,
      }))

    if (items.length === 0) {
      showToast('No PDF or DOCX files found')
      return
    }

    setFiles(prev => [...prev, ...items])
    addLog(`Added ${items.length} file(s)`)
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files))
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files) addFiles(Array.from(e.dataTransfer.files))
  }

  // ── Process ────────────────────────────────────────────────
  const processFiles = async () => {
    if (files.length === 0) { showToast('No files to process'); return }
    const toProcess = files.filter(f => !isDownloadable(f) && f.status !== 'success')
    if (toProcess.length === 0) { showToast('All files already processed'); return }

    const isOfflineMode = settings.extractionMode === 'offline'

    let providerStatus: Record<string, string> = {}
    let hasClaude = false
    let hasOpenAI = false
    let hasOllama = false

    if (!isOfflineMode) {
      // Pre-flight check: which providers are available?
      addLog('Checking AI providers...')
      try {
        const res = await axios.get(`${settings.backendUrl}/health`, {
          params: {
            api_key: settings.apiKey,
            openai_api_key: settings.openaiApiKey,
          },
          timeout: 15000,
        })
        providerStatus = res.data
        const providerKeys = ['claude', 'openai', 'ollama']
        for (const [provider, status] of Object.entries(providerStatus)) {
          if (!providerKeys.includes(provider) && typeof status !== 'string') continue
          const icons: Record<string, string> = {
            ok: '✅', unavailable: '❌', no_credit: '⚠️', invalid_key: '❌',
            quota_exceeded: '⚠️', error: '❌'
          }
          const icon = icons[status as string] ?? '❓'
          if (providerKeys.includes(provider)) {
            addLog(`  ${provider}: ${icon} ${status}`)
          }
        }
      } catch {
        addLog('  (health check failed, proceeding anyway)')
      }

      // Check provider status from health response (if backend supports it)
      const hasProviderFields = 'claude' in providerStatus || 'openai' in providerStatus || 'ollama' in providerStatus

      if (hasProviderFields) {
        hasClaude = providerStatus['claude'] === 'ok'
        hasOpenAI = providerStatus['openai'] === 'ok'
        hasOllama = providerStatus['ollama'] === 'ok'
      } else {
        // Backend doesn't report provider status — assume available if keys are set
        hasClaude = !!settings.apiKey
        hasOpenAI = !!settings.openaiApiKey
        hasOllama = false
      }

      if (!hasClaude && !hasOpenAI && !hasOllama) {
        const hints: string[] = []
        if (!settings.apiKey) hints.push('Claude: chưa nhập key')
        else if (providerStatus['claude'] === 'no_credit') hints.push('Claude: HẾT CREDIT - nạp tiền tại console.anthropic.com')
        else if (providerStatus['claude'] === 'invalid_key') hints.push('Claude: API key SAI - kiểm tra lại key')
        else if (providerStatus['claude'] === 'error') hints.push('Claude: lỗi kết nối - kiểm tra lại key')
        else hints.push('Claude: chưa nhập key')

        if (!settings.openaiApiKey) hints.push('OpenAI: chưa nhập key')
        else if (providerStatus['openai'] === 'invalid_key') hints.push('OpenAI: API key sai')
        else if (providerStatus['openai'] === 'quota_exceeded') hints.push('OpenAI: HẾT QUOTA - nạp tiền tại platform.openai.com')
        else hints.push('OpenAI: chưa nhập key')

        hints.push('Ollama: chưa chạy (chạy "ollama serve")')

        showToast('Không có AI provider nào khả dụng! Nhập API key trong Settings hoặc dùng Offline mode.')
        addLog('❌ No AI provider available:')
        hints.forEach(h => addLog(`  - ${h}`))
        return
      }

      addLog(`Starting processing with: ${[hasClaude && 'Claude', hasOpenAI && 'OpenAI', hasOllama && 'Ollama'].filter(Boolean).join(' + ')}`)
    } else {
      addLog('Starting processing with: Offline Rule Engine (No API)')
    }
    setProcessing(true)
    setProgress({ done: 0, total: toProcess.length })

    for (const file of toProcess) {
      setFiles(prev => prev.map(f =>
        f.id === file.id ? { ...f, status: 'processing' as const, message: 'Processing...' } : f
      ))
      addLog(`Processing: ${file.name}`)

      try {
        const formData = new FormData()
        if (file.file) formData.append('file', file.file)
        formData.append('extraction_mode', settings.extractionMode)
        formData.append('model', settings.model)
        formData.append('openai_api_key', settings.openaiApiKey)
        formData.append('openai_model', settings.openaiModel)
        formData.append('api_key', settings.apiKey)

        // Try /jobs first (new workflow with DB + review), fall back to /process (legacy)
        let res: import('axios').AxiosResponse<ProcessResult>
        try {
          res = await axios.post<ProcessResult>(
            `${settings.backendUrl}/jobs`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300_000 }
          )
        } catch (jobErr) {
          if (axios.isAxiosError(jobErr) && jobErr.response?.status === 404) {
            // /jobs not available — use legacy /process endpoint
            const fallbackForm = new FormData()
            if (file.file) fallbackForm.append('file', file.file)
            fallbackForm.append('extraction_mode', settings.extractionMode)
            fallbackForm.append('model', settings.model)
            fallbackForm.append('openai_api_key', settings.openaiApiKey)
            fallbackForm.append('openai_model', settings.openaiModel)
            fallbackForm.append('api_key', settings.apiKey)
            res = await axios.post<ProcessResult>(
              `${settings.backendUrl}/process`,
              fallbackForm,
              { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300_000 }
            )
          } else {
            throw jobErr
          }
        }

        const result = res.data as any
        // /jobs response has validation_result; /process has reviewRequired
        const errorCount = result.validation_result?.error_count ?? 0
        const warnCount = result.validation_result?.warning_count ?? 0
        const reviewCount = result.reviewRequired?.length ?? 0
        const hasIssues = errorCount > 0 || warnCount > 0 || reviewCount > 0
        const newStatus = (hasIssues ? 'partial' : result.status === 'success' ? 'success' : result.status) as FileItem['status']
        const statusMessage = hasIssues
          ? `${result.message} — 🔍 Cần Review (${errorCount} lỗi, ${warnCount} cảnh báo)`
          : result.message

        setFiles(prev => prev.map(f =>
          f.id === file.id
            ? {
                ...f,
                status: newStatus,
                message: statusMessage,
                filename: (result as any).suggestedName
                  ? stripExtension((result as any).suggestedName)
                  : stripExtension(f.filename),
                // New workflow fields (from /jobs endpoint)
                job_id: (result as any).job_id ?? f.job_id,
                cv_data: (result as any).parsed_data ?? f.cv_data,
                validation_result: (result as any).validation_result ?? f.validation_result,
                // Legacy fields (from /process endpoint)
                downloadId: (result as any).downloadId ?? undefined,
                downloadUrl: (result as any).downloadUrl ?? undefined,
                reviewRequired: (result as any).reviewRequired ?? undefined,
              }
            : f
        ))
        addLog(`  [${file.filename}] ${newStatus.toUpperCase()}: ${statusMessage}`)
        if ((result as any).suggestedName) {
          addLog(`  Suggested: ${(result as any).suggestedName}`)
        }
        if (hasIssues) {
          const fields = ((result as any).reviewRequired ?? []).map((r: any) => r.placeholder).slice(0, 5).join(', ')
          if (fields) addLog(`  Review fields: ${fields}`)
        }

      } catch (err: unknown) {
        let msg = 'Unknown error'
        if (axios.isAxiosError(err)) {
          const data = err.response?.data
          if (typeof data?.detail === 'string') {
            msg = data.detail
          } else if (typeof data?.detail === 'object') {
            msg = JSON.stringify(data.detail)
          } else {
            msg = err.message
          }
        } else if (err instanceof Error) {
          msg = err.message
        }

        // Extract provider error for display
        const providerErrors = msg.split(' | ')
        const shortMsgs = providerErrors.map(e => {
          if (e.includes('credit balance')) return 'Claude: hết credit'
          if (e.includes('Incorrect API key') || e.includes('invalid_api_key')) return 'OpenAI: API key sai'
          if (e.includes('401')) return 'OpenAI: key không hợp lệ'
          if (e.includes('Connection refused') || e.includes('Ollama unavailable')) return 'Ollama: chưa chạy'
          if (e.includes('500') || e.includes('502') || e.includes('503')) return 'Server đang bận, thử lại'
          return e.substring(0, 60)
        })
        const shortMsg = shortMsgs.join(' | ')

        setFiles(prev => prev.map(f =>
          f.id === file.id ? { ...f, status: 'error' as const, message: shortMsg } : f
        ))
        addLog(`  [${file.filename}] ERROR: ${shortMsg}`)

      }

      setProgress(prev => ({ ...prev, done: prev.done + 1 }))
    }

    setProcessing(false)
    showToast('Processing complete')
    addLog('── Processing complete ──')
  }

  // ── Summary ────────────────────────────────────────────────
  const total = files.length
  const downloadable = files.filter(isDownloadable).length
  const success = files.filter(f => f.status === 'success' || (f.status === 'partial' && isDownloadable(f))).length
  const errors = files.filter(f => f.status === 'error' || (f.status === 'partial' && !isDownloadable(f))).length
  const pending = files.filter(f => f.status === 'pending').length

  return (
    <>
      {/* Header */}
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span className="header-title">CV Format Tool</span>
          <span className="header-sub">Navigos Search — Web</span>
        </div>
        {/* Author + toolbar buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: '#A8C8E8', fontWeight: 600 }}>
            Van, Cu Thi Thuy
          </span>
          <button className="settings-btn" onClick={openGuideline}>
            Guideline
          </button>
          <button className="settings-btn" onClick={() => setShowSettings(true)}>
            Settings
          </button>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="tab-nav">
        <button
          className={`tab-btn${activeTab === 'process' ? ' active' : ''}`}
          onClick={() => setActiveTab('process')}
        >
          📋 Process CV
        </button>
        <button
          className={`tab-btn${activeTab === 'training' ? ' active' : ''}`}
          onClick={() => setActiveTab('training')}
        >
          🧠 Format Training
        </button>
      </nav>

      {/* Tab Content */}
      {activeTab === 'training' ? (
        <TrainingPanel
          backendUrl={settings.backendUrl}
          onLog={msg => addLog(`[TRAIN] ${msg}`)}
          onToast={showToast}
        />
      ) : (
      <>
      {/* Main layout */}
      <div className="layout">

        {/* Left: File list */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">CV Files</span>
            <span style={{ color: '#8BA4C7', fontSize: 12 }}>{files.length} file(s)</span>
          </div>

          {/* Toolbar */}
          <div className="toolbar">
            <div className="toolbar-left">
              <button
                className="btn btn-primary"
                onClick={() => fileInputRef.current?.click()}
                disabled={processing}
              >
                + Add Files
              </button>
              <button
                className="btn"
                onClick={() => setFiles([])}
                disabled={processing || files.length === 0}
              >
                Clear All
              </button>
            </div>
            <div className="toolbar-right">
              <div className="mode-selector">
                <span>Mode:</span>
                <select
                  value={settings.extractionMode}
                  onChange={e => setSettings(s => ({ ...s, extractionMode: e.target.value as Settings['extractionMode'] }))}
                >
                  <option value="offline">Offline</option>
                  <option value="auto">Auto</option>
                  <option value="claude_api">Claude</option>
                  <option value="openai_api">OpenAI</option>
                  <option value="ollama">Ollama</option>
                  <option value="cached">Cached</option>
                </select>
              </div>
            </div>
          </div>

          {/* File list / drop zone */}
          <div
            className={`drop-zone${dragging ? ' dragging' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{ margin: 8, padding: files.length === 0 ? 40 : 8 }}
          >
            {files.length === 0 && (
              <>
                <div className="file-empty-icon">📄</div>
                <p>Drop PDF or DOCX files here</p>
                <small>or click to browse</small>
              </>
            )}
          </div>

          {files.map((f, i) => (
            <div key={f.id} className={`file-item ${f.status}`}>
              <span className="file-num">{i + 1}</span>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div className="file-name" title={f.name}>{f.name}</div>
                <input
                  type="text"
                  value={f.filename}
                  onChange={e => setFiles(prev => prev.map(item =>
                    item.id === f.id ? { ...item, filename: e.target.value } : item
                  ))}
                  style={{
                    width: '100%',
                    fontSize: 12,
                    color: 'var(--green)',
                    fontWeight: 600,
                    border: '1px solid #D1FAE5',
                    borderRadius: 4,
                    padding: '2px 6px',
                    fontFamily: 'inherit',
                    background: isDownloadable(f) ? '#D1FAE5' : '#FEF9C3',
                    outline: 'none',
                  }}
                  title="Output filename"
                />
              </div>
              <span className="file-type">{f.type}</span>
              <span className={`file-status status-${f.status}`}>
                {f.status === 'success' && '✓ Done'}
                {f.status === 'error' && `✗ ${f.message}`}
                {f.status === 'processing' && '⏳ Processing...'}
                {f.status === 'partial' && `⚠ ${f.message}`}
                {f.status === 'pending' && '○ Pending'}
              </span>
              {isDownloadable(f) && (
                <button
                  className="btn btn-download-inline"
                  onClick={() => void handleSingleDownload(f)}
                  disabled={processing}
                >
                  Download
                </button>
              )}
              {f.cv_data && (
                <button
                  className="btn"
                  onClick={() => void handleOpenReview(f)}
                  style={{ padding: '3px 8px', fontSize: 11, background: '#EFF6FF', color: '#1D4ED8', border: '1px solid #BFDBFE' }}
                >
                  🔍 Review
                </button>
              )}
            </div>
          ))}

          {/* Action bar */}
          <div className="action-bar">
            <button
              className="btn btn-primary"
              onClick={processFiles}
              disabled={processing || files.length === 0}
              style={{ fontWeight: 700, fontSize: 13, padding: '7px 20px' }}
            >
              Process All
            </button>
            <button
              className="btn"
              disabled={processing || downloadable === 0}
              onClick={downloadFiles}
            >
              Download ({downloadable})
            </button>
            <div className="progress-area">
              <div className="progress-text">
                {progress.total > 0 ? `${progress.done} / ${progress.total} completed` : 'Ready'}
              </div>
              <div className="progress-bar-bg">
                <div
                  className="progress-bar-fill"
                  style={{ width: progress.total > 0 ? `${(progress.done / progress.total) * 100}%` : '0%' }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Summary + Log */}
        <div className="sidebar">
          {/* Summary */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Summary</span>
            </div>
            <div className="summary-body">
              <div className="summary-row"><span>Total</span> <span style={{ color: 'var(--dark-text)' }}>{total}</span></div>
              <div className="summary-row"><span>Success</span> <span style={{ color: 'var(--green)' }}>{success}</span></div>
              <div className="summary-row"><span>Errors</span> <span style={{ color: 'var(--red)' }}>{errors}</span></div>
              <div className="summary-row"><span>Pending</span> <span style={{ color: '#9CA3AF' }}>{pending}</span></div>
            </div>
          </div>

          {/* Log */}
          <div className="card" style={{ flex: 1 }}>
            <div className="card-header">
              <span className="card-title">Log</span>
              <button className="btn" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => setLogs([])}>
                Clear
              </button>
            </div>
            <div className="log-box">
              {logs.length === 0 && (
                <div style={{ color: '#9CA3AF', textAlign: 'center', padding: 20 }}>
                  No activity yet
                </div>
              )}
              {logs.map((l, i) => <div key={i} className="log-entry">{l}</div>)}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileInput}
      />
      </>
      )}

      {/* Settings modal */}
      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={s => setSettings(s)}
          onClose={() => setShowSettings(false)}
        />
      )}

      {/* Login modal */}
      {showLogin && (
        <LoginModal
          backendUrl={settings.backendUrl}
          onSuccess={handleLoginSuccess}
          onClose={() => setShowLogin(false)}
        />
      )}

      {/* Review panel — full modal overlay */}
      <ReviewPanel
        reviewData={reviewFile ? {
          original_filename: reviewFile.filename,
          parsed_data: reviewFile.cv_data ?? {} as ParsedCVData,
          validation_result: reviewFile.validation_result ?? {
            is_valid: true, is_exportable: true,
            error_count: 0, warning_count: 0,
            errors: [], warnings: [], info: [], summary: '',
          },
        } : null}
        isOpen={!!reviewFile}
        onClose={() => setReviewFile(null)}
        onSave={handleReviewSave}
        onApprove={handleReviewApprove}
        isSubmitting={reviewSubmitting}
        userRole={auth.user?.role}
      />

      {/* Toast */}
      {toast && <div className="toast">{toast}</div>}
    </>
  )
}
