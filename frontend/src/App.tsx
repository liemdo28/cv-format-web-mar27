import { useState, useRef, useCallback, useEffect } from 'react'
import axios from 'axios'
import type { FileItem, Settings, ProcessResult } from './types'

// ── Default settings ───────────────────────────────────────────
const DEFAULT_SETTINGS: Settings = {
  apiKey: '',
  openaiApiKey: '',
  model: 'claude-sonnet-4-20250514',
  openaiModel: 'gpt-4o-mini',
  extractionMode: 'auto',
  backendUrl: 'http://localhost:8000',
}

// ── Helpers ────────────────────────────────────────────────────
function uid() {
  return Math.random().toString(36).slice(2, 10)
}

function formatTime() {
  return new Date().toLocaleTimeString('en-US', { hour12: false })
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
  const [showSettings, setShowSettings] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [dragging, setDragging] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

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

  // ── Download ────────────────────────────────────────────────
  const downloadFiles = () => {
    const successFiles = files.filter(f => f.status === 'success' && f.downloadId)
    if (successFiles.length === 0) {
      showToast('No processed files to download')
      return
    }
    successFiles.forEach((file, i) => {
      setTimeout(() => {
        if (!file.downloadId) return
        const url = `${settings.backendUrl}/download/${file.downloadId}`
        const a = document.createElement('a')
        a.href = url
        a.download = file.filename || 'output.docx'
        a.target = '_blank'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        addLog(`Downloaded: ${file.filename}`)
      }, i * 500)
    })
    showToast(`Downloading ${successFiles.length} file(s)...`)
  }

  // Persist settings
  useEffect(() => {
    localStorage.setItem('cvformat-settings-v2', JSON.stringify(settings))
  }, [settings])

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
    const toProcess = files.filter(f => f.status !== 'success')
    if (toProcess.length === 0) { showToast('All files already processed'); return }

    // Pre-flight check: which providers are available?
    addLog('Checking AI providers...')
    let providerStatus: Record<string, string> = {}
    try {
      const res = await axios.get(`${settings.backendUrl}/health`, {
        params: {
          api_key: settings.apiKey,
          openai_api_key: settings.openaiApiKey,
        },
        timeout: 15000,
      })
      providerStatus = res.data
      for (const [provider, status] of Object.entries(providerStatus)) {
        const icons: Record<string, string> = {
          ok: '✅', unavailable: '❌', no_credit: '⚠️', invalid_key: '❌',
          quota_exceeded: '⚠️', error: '❌'
        }
        const icon = icons[status as string] ?? '❓'
        addLog(`  ${provider}: ${icon} ${status}`)
      }
    } catch {
      addLog('  (health check failed, proceeding anyway)')
    }

    const hasClaude = providerStatus['claude'] === 'ok'
    const hasOpenAI = providerStatus['openai'] === 'ok'
    const hasOllama = providerStatus['ollama'] === 'ok'

    if (!hasClaude && !hasOpenAI && !hasOllama) {
      const hints: string[] = []
      if (!settings.apiKey) hints.push('Claude: chưa nhập key')
      else if (providerStatus['claude'] === 'no_credit') hints.push('Claude: HẾT CREDIT - nạp tiền tại console.anthropic.com')
      else if (providerStatus['claude'] === 'invalid_key') hints.push('Claude: API key SAI - kiểm tra lại key')
      else hints.push('Claude: lỗi')

      if (!settings.openaiApiKey) hints.push('OpenAI: chưa nhập key')
      else if (providerStatus['openai'] === 'invalid_key') hints.push('OpenAI: API key sai')
      else if (providerStatus['openai'] === 'quota_exceeded') hints.push('OpenAI: HẾT QUOTA - nạp tiền tại platform.openai.com')
      else hints.push('OpenAI: lỗi')

      hints.push('Ollama: chưa chạy (chạy "ollama serve")')

      showToast('Không có AI provider nào khả dụng!')
      addLog('❌ No AI provider available:')
      hints.forEach(h => addLog(`  - ${h}`))
      return
    }

    addLog(`Starting processing with: ${[hasClaude && 'Claude', hasOpenAI && 'OpenAI', hasOllama && 'Ollama'].filter(Boolean).join(' + ')}`)
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

        const res = await axios.post<ProcessResult>(
          `${settings.backendUrl}/process`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300_000 }
        )

        const result = res.data
        const newStatus = result.status as FileItem['status']

        setFiles(prev => prev.map(f =>
          f.id === file.id
            ? {
                ...f,
                status: newStatus,
                message: result.message,
                filename: result.suggestedName
                  ? `${result.suggestedName}${f.name.substring(f.name.lastIndexOf('.'))}`
                  : f.filename,
                downloadId: result.downloadId ?? undefined,
              }
            : f
        ))
        addLog(`  [${file.filename}] ${newStatus.toUpperCase()}: ${result.message}`)
        if (result.suggestedName) {
          addLog(`  Suggested: ${result.suggestedName}`)
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
  const success = files.filter(f => f.status === 'success').length
  const errors = files.filter(f => f.status === 'error' || f.status === 'partial').length
  const pending = files.filter(f => f.status === 'pending').length

  return (
    <>
      {/* Header */}
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span className="header-title">CV Format Tool</span>
          <span className="header-sub">Navigos Search — Web</span>
        </div>
        {/* Author credit + Settings */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: '#8BA4C7' }}>
            Van, Cu Thi Thuy — <strong style={{ color: '#A0B4C8' }}>Navigos Search</strong>
          </span>
          <button className="settings-btn" onClick={() => setShowSettings(true)}>
            Settings
          </button>
        </div>
      </header>

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
                    background: f.status === 'success' ? '#D1FAE5' : '#FEF9C3',
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
              disabled={processing || success === 0}
              onClick={downloadFiles}
            >
              Download ({success})
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

      {/* Settings modal */}
      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={s => setSettings(s)}
          onClose={() => setShowSettings(false)}
        />
      )}

      {/* Toast */}
      {toast && <div className="toast">{toast}</div>}
    </>
  )
}
