import { useState, useRef, useCallback, useEffect } from 'react'
import axios from 'axios'
import type { FileItem, Settings, ProcessResult } from './types'

// ── Default settings ───────────────────────────────────────────
const DEFAULT_SETTINGS: Settings = {
  apiKey: '',
  model: 'claude-sonnet-4-20250514',
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

function log(lines: string[]) {
  return lines.map((l, i) => (
    <div key={i} className="log-entry">
      [{formatTime()}] {l}
    </div>
  ))
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
    { value: 'auto', label: 'Auto (Claude → Ollama)' },
    { value: 'claude_api', label: 'Claude API Only' },
    { value: 'ollama', label: 'Ollama Only' },
    { value: 'cached', label: 'Cached (no AI)' },
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
            <label>Backend URL</label>
            <input
              type="text"
              value={s.backendUrl}
              onChange={e => setS({ ...s, backendUrl: e.target.value })}
              placeholder="http://localhost:8000"
            />
          </div>
          <div className="form-row">
            <label>API Key</label>
            <input
              type="password"
              value={s.apiKey}
              onChange={e => setS({ ...s, apiKey: e.target.value })}
              placeholder="sk-ant-..."
            />
          </div>
          <div className="form-row">
            <label>Model</label>
            <input
              type="text"
              value={s.model}
              onChange={e => setS({ ...s, model: e.target.value })}
              placeholder="claude-sonnet-4-20250514"
            />
          </div>
          <div className="form-row">
            <label>Extraction</label>
            <div className="radio-group">
              {modes.map(m => (
                <label key={m.value}>
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
  const [logs, setLogs] = useState<React.ReactNode[]>([])
  const [settings, setSettings] = useState<Settings>(() => {
    try {
      const saved = localStorage.getItem('cvformat-settings')
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
    setLogs(prev => [...prev, ...log(lines)])
    setTimeout(() => logEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }, [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  // Persist settings
  useEffect(() => {
    localStorage.setItem('cvformat-settings', JSON.stringify(settings))
  }, [settings])

  // ── File handling ──────────────────────────────────────────
  const addFiles = (newFiles: File[]) => {
    const items: FileItem[] = newFiles
      .filter(f => /\.(pdf|docx)$/i.test(f.name))
      .map(f => ({
        id: uid(),
        name: f.name,
        type: f.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX',
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
    if (!settings.apiKey) { showToast('API Key is required in Settings'); return }

    setProcessing(true)
    setProgress({ done: 0, total: files.length })

    const toProcess = files.filter(f => f.status !== 'success')
    let done = 0

    for (const file of toProcess) {
      // Mark processing
      setFiles(prev => prev.map(f => f.id === file.id ? { ...f, status: 'processing', message: 'Processing...' } : f))
      addLog(`Processing: ${file.name}`)

      try {
        const formData = new FormData()
        if (file.file) formData.append('file', file.file)
        formData.append('extraction_mode', settings.extractionMode)
        formData.append('model', settings.model)
        formData.append('api_key', settings.apiKey)

        const res = await axios.post<ProcessResult>(
          `${settings.backendUrl}/process`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300_000 }
        )

        const result = res.data

        setFiles(prev => prev.map(f =>
          f.id === file.id
            ? { ...f, status: result.status as FileItem['status'], message: result.message }
            : f
        ))
        addLog(`  → ${result.status.toUpperCase()}: ${result.message}`)

      } catch (err: unknown) {
        const msg = axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : String(err)
        setFiles(prev => prev.map(f =>
          f.id === file.id ? { ...f, status: 'error', message: msg } : f
        ))
        addLog(`  → ERROR: ${msg}`)
      }

      done++
      setProgress({ done, total: toProcess.length })
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
        <button className="settings-btn" onClick={() => setShowSettings(true)}>
          ⚙ Settings
        </button>
      </header>

      {/* Main layout */}
      <div className="layout">

        {/* Left: File list */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">📁 CV Files</span>
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
              <button
                className="btn"
                onClick={() => setFiles(prev => prev.slice(0, -1))}
                disabled={processing || files.length === 0}
              >
                Remove
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
                  <option value="claude_api">Claude API</option>
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
            {files.length === 0 ? (
              <>
                <div className="file-empty-icon">📄</div>
                <p>Drop PDF or DOCX files here</p>
                <small>or click to browse</small>
              </>
            ) : null}
          </div>

          {files.map((f, i) => (
            <div key={f.id} className={`file-item ${f.status}`}>
              <span className="file-num">{i + 1}</span>
              <span className="file-name" title={f.name}>{f.name}</span>
              <span className="file-type">{f.type}</span>
              <span className={`file-status status-${f.status}`}>
                {f.status === 'success' && '✓ Success'}
                {f.status === 'error' && `✗ ${f.message}`}
                {f.status === 'processing' && '⏳ Processing...'}
                {f.status === 'partial' && `⚠ ${f.message}`}
                {f.status === 'pending' && '○ Pending'}
              </span>
            </div>
          ))}

          {/* Output */}
          <div className="output-bar">
            <label>Output:</label>
            <input type="text" defaultValue="./output" readOnly />
          </div>

          {/* Action bar */}
          <div className="action-bar">
            <button
              className="btn btn-primary"
              onClick={processFiles}
              disabled={processing || files.length === 0}
              style={{ fontWeight: 700, fontSize: 13, padding: '7px 20px' }}
            >
              ▶ Process All
            </button>
            <button
              className="btn"
              disabled={processing || success === 0}
            >
              Download
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
              <span className="card-title">📊 Summary</span>
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
              <span className="card-title">📋 Log</span>
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
              {logs}
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
