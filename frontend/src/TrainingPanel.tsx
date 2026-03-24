import { useState, useRef, useCallback } from 'react'
import axios from 'axios'

interface TrainingPair {
  id: string
  rawFile: File
  doneFile: File
}

interface TrainingResult {
  learnedAliases: Record<string, string[]>
  learnedMappings: Record<string, string>
  labelCandidates: number
  sectionCandidates: number
  pairCount: number
}

interface TrainingPanelProps {
  backendUrl: string
  onLog: (msg: string) => void
  onToast: (msg: string) => void
}

const uid = () => Math.random().toString(36).slice(2, 10)

export default function TrainingPanel({ backendUrl, onLog, onToast }: TrainingPanelProps) {
  const [pairs, setPairs] = useState<TrainingPair[]>([])
  const [dragTarget, setDragTarget] = useState<'raw' | 'done' | null>(null)
  const [tempRaw, setTempRaw] = useState<File | null>(null)
  const [tempDone, setTempDone] = useState<File | null>(null)
  const [training, setTraining] = useState(false)
  const [result, setResult] = useState<TrainingResult | null>(null)
  const [knowledge, setKnowledge] = useState<Record<string, unknown> | null>(null)
  const [showKnowledge, setShowKnowledge] = useState(false)
  const rawInputRef = useRef<HTMLInputElement>(null)
  const doneInputRef = useRef<HTMLInputElement>(null)

  const addPair = useCallback((raw: File, done: File) => {
    setPairs(prev => [...prev, { id: uid(), rawFile: raw, doneFile: done }])
    setTempRaw(null)
    setTempDone(null)
    setResult(null)
    onLog(`Added pair: ${raw.name} + ${done.name}`)
  }, [onLog])

  const removePair = useCallback((id: string) => {
    setPairs(prev => prev.filter(p => p.id !== id))
    setResult(null)
  }, [])

  const handleRawFile = (file: File) => {
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      onToast('Chỉ chấp nhận file PDF hoặc DOCX')
      return
    }
    setTempRaw(file)
    if (tempDone) {
      addPair(file, tempDone)
    }
  }

  const handleDoneFile = (file: File) => {
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      onToast('Chỉ chấp nhận file PDF hoặc DOCX')
      return
    }
    setTempDone(file)
    if (tempRaw) {
      addPair(tempRaw, file)
    }
  }

  const handleDrop = (e: React.DragEvent, type: 'raw' | 'done') => {
    e.preventDefault()
    setDragTarget(null)
    const file = e.dataTransfer.files[0]
    if (file) {
      if (type === 'raw') handleRawFile(file)
      else handleDoneFile(file)
    }
  }

  const runTraining = async () => {
    if (pairs.length === 0) {
      onToast('Cần ít nhất 1 cặp file để train')
      return
    }

    setTraining(true)
    setResult(null)
    onLog(`Starting batch training: ${pairs.length} pair(s)...`)

    const allAliases: Record<string, string[]> = {}
    const allMappings: Record<string, string> = {}
    let totalLabels = 0
    let totalSections = 0

    try {
      for (let i = 0; i < pairs.length; i++) {
        const pair = pairs[i]
        onLog(`Training pair ${i + 1}/${pairs.length}: ${pair.rawFile.name} + ${pair.doneFile.name}`)

        const formData = new FormData()
        formData.append('raw_file', pair.rawFile)
        formData.append('done_file', pair.doneFile)

        const res = await axios.post(`${backendUrl}/train/format`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120_000,
        })

        const data = res.data
        if (data.learnedAliases) {
          for (const [canonical, aliases] of Object.entries(data.learnedAliases as Record<string, string[]>)) {
            allAliases[canonical] = [...(allAliases[canonical] || []), ...aliases]
          }
        }
        Object.assign(allMappings, data.learnedMappings || {})
        totalLabels += data.labelCandidates || 0
        totalSections += data.sectionCandidates || 0

        onLog(`  Learned ${Object.keys(data.learnedMappings || {}).length} mappings, ${Object.keys(data.learnedAliases || {}).length} alias groups`)
      }

      const combined: TrainingResult = {
        learnedAliases: allAliases,
        learnedMappings: allMappings,
        labelCandidates: totalLabels,
        sectionCandidates: totalSections,
        pairCount: pairs.length,
      }

      setResult(combined)
      onLog(`Training complete. ${Object.keys(allMappings).length} new mappings learned.`)
      onToast(`Train thành công! Đã học ${Object.keys(allMappings).length} mapping mới`)

    } catch (err) {
      let msg = 'Training failed'
      if (axios.isAxiosError(err)) {
        msg = (err.response?.data as { detail?: string })?.detail || err.message
      } else if (err instanceof Error) {
        msg = err.message
      }
      onLog(`Training ERROR: ${msg}`)
      onToast(`Train thất bại: ${msg}`)
    } finally {
      setTraining(false)
    }
  }

  const loadKnowledge = async () => {
    try {
      const res = await axios.get(`${backendUrl}/offline/rules`, { timeout: 10_000 })
      setKnowledge(res.data.data)
      setShowKnowledge(true)
    } catch {
      onToast('Không tải được knowledge base')
    }
  }

  const resetKnowledge = async () => {
    if (!confirm('Reset tất cả rules về mặc định?')) return
    try {
      await axios.post(`${backendUrl}/offline/rules/reset`, {}, { timeout: 10_000 })
      setKnowledge(null)
      setResult(null)
      setPairs([])
      setTempRaw(null)
      setTempDone(null)
      onLog('Knowledge base reset to defaults')
      onToast('Đã reset knowledge base')
    } catch {
      onToast('Reset thất bại')
    }
  }

  const canTrain = pairs.length > 0 && !training

  const renderDropZone = (type: 'raw' | 'done') => {
    const temp = type === 'raw' ? tempRaw : tempDone
    const label = type === 'raw' ? '📄 Chưa Format (Raw CV)' : '✅ Đã Format (Done CV)'
    const sub = type === 'raw' ? 'Kéo thả hoặc click để chọn file CV gốc' : 'Kéo thả hoặc click để chọn file CV đã format chuẩn'
    const icon = type === 'raw' ? '📄' : '✅'
    const inputRef = type === 'raw' ? rawInputRef : doneInputRef

    return (
      <div
        className={`training-drop-zone${dragTarget === type ? ' drag-over' : ''}${temp ? ' has-file' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragTarget(type) }}
        onDragLeave={() => setDragTarget(null)}
        onDrop={e => handleDrop(e, type)}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          style={{ display: 'none' }}
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) {
              if (type === 'raw') handleRawFile(file)
              else handleDoneFile(file)
            }
            e.target.value = ''
          }}
        />
        <div className="dz-icon">{icon}</div>
        <div className="dz-label">{label}</div>
        <div className="dz-sub">{sub}</div>
        {temp && <div className="dz-filename">{temp.name}</div>}
      </div>
    )
  }

  const totalMappings = result ? Object.keys(result.learnedMappings).length : 0
  const totalAliases = result
    ? Object.values(result.learnedAliases).reduce((acc, arr) => acc + arr.length, 0)
    : 0

  return (
    <div className="training-layout">
      {/* Left: Upload Pairs */}
      <div>
        {/* Drop columns */}
        <div className="training-drop-col" style={{ marginBottom: 16 }}>
          {renderDropZone('raw')}
          <div style={{ textAlign: 'center', color: '#9CA3AF', fontSize: 18, fontWeight: 700 }}>+</div>
          {renderDropZone('done')}
        </div>

        {/* Pair list */}
        <div className="training-pair-card">
          <div className="card-header">
            <span className="card-title">Cặp Files đã thêm ({pairs.length})</span>
            {pairs.length > 0 && (
              <button className="btn btn-danger" style={{ padding: '2px 10px', fontSize: 11 }} onClick={() => { setPairs([]); setResult(null) }}>
                Clear All
              </button>
            )}
          </div>
          <div className="training-pair-list">
            {pairs.length === 0 ? (
              <div className="training-pair-empty">
                Chưa có cặp file nào.<br />
                Upload 1 file Raw + 1 file Done để thêm cặp.
              </div>
            ) : (
              pairs.map((pair, i) => (
                <div key={pair.id} className="training-pair-item">
                  <div className="pair-num">{i + 1}</div>
                  <div className="pair-files">
                    <div className="pair-raw">📄 {pair.rawFile.name}</div>
                    <div className="pair-done">✅ {pair.doneFile.name}</div>
                  </div>
                  <button className="pair-remove" onClick={() => removePair(pair.id)} title="Remove pair">✕</button>
                </div>
              ))
            )}
          </div>

          {/* Quick add note */}
          {pairs.length === 0 && tempRaw && !tempDone && (
            <div style={{ padding: '8px 16px', background: '#FEF3C7', fontSize: 12, color: '#92400E' }}>
              Đã thêm file Raw. Tiếp tục upload file Done để hoàn thành cặp.
            </div>
          )}
          {pairs.length === 0 && !tempRaw && tempDone && (
            <div style={{ padding: '8px 16px', background: '#FEF3C7', fontSize: 12, color: '#92400E' }}>
              Đã thêm file Done. Tiếp tục upload file Raw để hoàn thành cặp.
            </div>
          )}

          {/* Actions */}
          <div className="training-actions">
            <button
              className="btn btn-primary train-btn-main"
              onClick={runTraining}
              disabled={!canTrain}
            >
              {training ? '⏳ Training...' : `🚀 Train ${pairs.length} cặp`}
            </button>
            {pairs.length > 0 && (
              <button
                className="btn"
                onClick={() => {
                  setTempRaw(null)
                  setTempDone(null)
                }}
              >
                + Thêm cặp khác
              </button>
            )}
            <span className="pair-count">{pairs.length} cặp file</span>
          </div>
        </div>
      </div>

      {/* Right: Results + Knowledge */}
      <div>
        {/* Stats */}
        {result && (
          <div className="training-results">
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <span className="card-title">Kết quả Training</span>
              </div>
              <div style={{ padding: 16 }}>
                <div className="training-stats-grid">
                  <div className="training-stat-card">
                    <div className="stat-value">{result.pairCount}</div>
                    <div className="stat-label">Cặp đã train</div>
                  </div>
                  <div className="training-stat-card">
                    <div className="stat-value" style={{ color: 'var(--green)' }}>{totalMappings}</div>
                    <div className="stat-label">Mapping mới</div>
                  </div>
                  <div className="training-stat-card">
                    <div className="stat-value" style={{ color: 'var(--amber)' }}>{totalAliases}</div>
                    <div className="stat-label">Alias học thêm</div>
                  </div>
                </div>

                {/* Learned mappings */}
                {Object.keys(result.learnedMappings).length > 0 && (
                  <div className="result-section">
                    <div className="result-title">
                      🔗 Learned Mappings
                      <span className="result-badge success">{totalMappings} new</span>
                    </div>
                    <div>
                      {Object.entries(result.learnedMappings).map(([placeholder, canonical]) => (
                        <span key={placeholder} className="alias-chip new">
                          <strong>{placeholder}</strong>
                          <span className="chip-arrow">→</span>
                          <span className="chip-canonical">{canonical}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Learned aliases */}
                {Object.entries(result.learnedAliases).map(([canonical, aliases]) => (
                  aliases.length > 0 && (
                    <div key={canonical} className="result-section">
                      <div className="result-title">
                        🔤 {canonical}
                        <span className="result-badge">{aliases.length} aliases</span>
                      </div>
                      <div>
                        {aliases.map(alias => (
                          <span key={alias} className="alias-chip">
                            {alias}
                          </span>
                        ))}
                      </div>
                    </div>
                  )
                ))}

                {totalMappings === 0 && totalAliases === 0 && (
                  <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 20 }}>
                    Không tìm thấy format mới trong các cặp file này.
                    Thử cặp file khác có cấu trúc khác nhau.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {!result && !training && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <span className="card-title">Chưa có kết quả training</span>
            </div>
            <div style={{ padding: 24, textAlign: 'center', color: '#9CA3AF' }}>
              Upload cặp file và bấm <strong>Train</strong> để hệ thống học format mới.
            </div>
          </div>
        )}

        {/* Knowledge base */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Knowledge Base</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn" style={{ padding: '2px 10px', fontSize: 11 }} onClick={loadKnowledge}>
                Xem Rules
              </button>
              <button className="btn btn-danger" style={{ padding: '2px 10px', fontSize: 11 }} onClick={resetKnowledge}>
                Reset
              </button>
            </div>
          </div>
          <div style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
              Knowledge base lưu trong <code style={{ background: '#F3F4F6', padding: '1px 4px', borderRadius: 4 }}>backend/learning_store.json</code>.
              Mỗi khi train thành công, rules mới được ghi vào đây.
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn" onClick={loadKnowledge} style={{ fontSize: 12 }}>
                📋 Xem Rules hiện tại
              </button>
              <button className="btn" onClick={resetKnowledge} style={{ fontSize: 12, color: 'var(--red)' }}>
                🗑 Reset về mặc định
              </button>
            </div>
            <details className="training-knowledge" style={{ marginTop: 12 }}>
              <summary onClick={e => { e.preventDefault(); setShowKnowledge(s => !s) }}>
                {showKnowledge ? '▼' : '▶'} Knowledge JSON
              </summary>
              {showKnowledge && knowledge && (
                <pre>{JSON.stringify(knowledge, null, 2)}</pre>
              )}
            </details>
          </div>
        </div>
      </div>
    </div>
  )
}
