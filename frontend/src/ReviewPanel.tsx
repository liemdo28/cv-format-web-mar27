import { useState, useCallback } from 'react'
import type { ValidationError } from './types'

// ── Types ────────────────────────────────────────────────────────

export interface ParsedCVData {
  full_name?: string
  gender?: string
  year_of_birth?: string
  marital_status?: string
  address?: string
  email?: string
  phone?: string
  career_summary?: CareerEntry[]
  education?: EducationEntry[]
  other_info?: OtherInfoEntry[]
}

export interface CareerEntry {
  period?: string
  company?: string
  company_description?: string
  positions?: Position[]
  responsibilities?: string[]
}

export interface Position {
  period?: string
  title?: string
  report_to?: string
  section_label?: string
  responsibilities?: string[]
  achievements_label?: string
  achievements?: string[]
}

export interface EducationEntry {
  period?: string
  institution?: string
  details?: string[]
}

export interface OtherInfoEntry {
  section_title?: string
  items?: string[]
}

export interface ValidationError {
  field: string
  code: string
  message: string
  severity: 'error' | 'warning' | 'info'
  value?: string
  suggestion?: string
}

export interface ReviewResult {
  validation_result: {
    is_valid: boolean
    is_exportable: boolean
    error_count: number
    warning_count: number
    errors: ValidationError[]
    warnings: ValidationError[]
    info: ValidationError[]
    summary: string
  }
  parsed_data: ParsedCVData
  original_filename: string
}

// ── Props ────────────────────────────────────────────────────────

interface ReviewPanelProps {
  reviewData: ReviewResult | null
  isOpen: boolean
  onClose: () => void
  onSave: (correctedData: ParsedCVData) => void
  onApprove: (correctedData: ParsedCVData) => void
  isSubmitting: boolean
  /** Role of the current user — controls approve permission. */
  userRole?: 'admin' | 'staff' | 'qc'
}

// ── Sub-components ────────────────────────────────────────────────

function ValidationBadge({ error }: { error: ValidationError }) {
  const colors: Record<string, string> = {
    error: { bg: '#FEE2E2', border: '#EF4444', text: '#991B1B' },
    warning: { bg: '#FEF3C7', border: '#F59E0B', text: '#92400E' },
    info: { bg: '#DBEAFE', border: '#3B82F6', text: '#1E40AF' },
  }
  const c = colors[error.severity] ?? colors.info
  return (
    <div style={{
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: 6,
      padding: '6px 10px',
      fontSize: 12,
      color: c.text,
      display: 'flex',
      alignItems: 'flex-start',
      gap: 6,
    }}>
      <span style={{ fontSize: 14 }}>
        {error.severity === 'error' ? '❌' : error.severity === 'warning' ? '⚠️' : 'ℹ️'}
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600 }}>{error.field}: {error.message}</div>
        {error.suggestion && (
          <div style={{ opacity: 0.8, marginTop: 2 }}>💡 {error.suggestion}</div>
        )}
        {error.value && (
          <div style={{ fontFamily: 'monospace', fontSize: 11, marginTop: 2, opacity: 0.7 }}>
            Current: {error.value}
          </div>
        )}
      </div>
    </div>
  )
}

function EditableField({
  label,
  value,
  onChange,
  multiline = false,
  hint,
}: {
  label: string
  value?: string
  onChange: (v: string) => void
  multiline?: boolean
  hint?: string
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
        {label}
        {hint && <span style={{ fontWeight: 400, color: '#9CA3AF', fontSize: 11 }}>{hint}</span>}
      </div>
      {multiline ? (
        <textarea
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          rows={3}
          style={{
            width: '100%', padding: '6px 10px', border: '1px solid #D1D5DB',
            borderRadius: 6, fontSize: 13, fontFamily: 'inherit',
            resize: 'vertical', outline: 'none', boxSizing: 'border-box',
            background: '#fff',
          }}
          placeholder={`Nhập ${label.toLowerCase()}...`}
        />
      ) : (
        <input
          type="text"
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          style={{
            width: '100%', padding: '6px 10px', border: '1px solid #D1D5DB',
            borderRadius: 6, fontSize: 13, fontFamily: 'inherit',
            outline: 'none', boxSizing: 'border-box',
            background: '#fff',
          }}
          placeholder={`Nhập ${label.toLowerCase()}...`}
        />
      )}
    </div>
  )
}

function SectionAccordion({
  title,
  children,
  defaultOpen = false,
  badge,
}: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
  badge?: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div style={{ border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden', marginBottom: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', background: open ? '#F9FAFB' : '#F3F4F6',
          border: 'none', padding: '10px 14px', fontSize: 13,
          fontWeight: 700, cursor: 'pointer', display: 'flex',
          alignItems: 'center', justifyContent: 'space-between',
          color: '#374151', textAlign: 'left',
        }}
      >
        <span>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {badge && (
            <span style={{ background: '#E5E7EB', borderRadius: 12, padding: '1px 8px', fontSize: 11 }}>
              {badge}
            </span>
          )}
          <span>{open ? '▲' : '▼'}</span>
        </div>
      </button>
      {open && (
        <div style={{ padding: 14, background: '#fff' }}>
          {children}
        </div>
      )}
    </div>
  )
}

// ── Main ReviewPanel ──────────────────────────────────────────────

export default function ReviewPanel({
  reviewData,
  isOpen,
  onClose,
  onSave,
  onApprove,
  isSubmitting,
  userRole = 'staff',
}: ReviewPanelProps) {
  const [data, setData] = useState<ParsedCVData | null>(null)
  const [activeTab, setActiveTab] = useState<'fields' | 'errors' | 'preview'>('fields')
  const [hasEdits, setHasEdits] = useState(false)

  // Sync local state when reviewData changes
  const currentData = data ?? reviewData?.parsed_data ?? {}
  const validation = reviewData?.validation_result

  /**
   * Recursive path setter for arbitrary-depth paths like:
   *   career_summary[0].company
   *   career_summary[0].positions[1].responsibilities
   *   other_info[2].items
   *
   * Handles array-leaf fields (responsibilities, details, items) by
   * splitting the multiline string into a string[] and storing that.
   */
  const updateField = useCallback((path: string, value: string) => {
    setData(prev => {
      const base = prev ?? { ...(reviewData?.parsed_data ?? {}) }
      const updated = JSON.parse(JSON.stringify(base)) as ParsedCVData

      // Tokenise: ["career_summary", 0, "positions", 1, "responsibilities"]
      const tokens: (string | number)[] = []
      const parts = path.split('.')
      for (const part of parts) {
        const idxMatch = part.match(/^([^\[]+)\[(\d+)\]$/)
        if (idxMatch) {
          tokens.push(idxMatch[1], parseInt(idxMatch[2], 10))
        } else {
          tokens.push(part)
        }
      }

      if (tokens.length === 0) return updated

      // Navigate to parent container
      let node: any = updated
      for (let i = 0; i < tokens.length - 1; i++) {
        const t = tokens[i]
        if (typeof t === 'number') {
          node = node[t]
        } else {
          node = (node as any)[t]
        }
        if (!node) return updated
      }

      const last = tokens[tokens.length - 1]
      if (typeof last !== 'string') return updated

      // Determine if the target field is an array-type (responsibilities / details / items)
      const arrayFields = new Set(['responsibilities', 'details', 'items'])
      if (arrayFields.has(last) && value.trim() !== '') {
        // Split multiline string into string[] — one item per non-empty line
        const lines = value.split('\n').map(l => l.trim()).filter(l => l.length > 0)
        ;(node as any)[last] = lines
      } else {
        ;(node as any)[last] = value
      }

      return updated
    })
    setHasEdits(true)
  }, [reviewData])

  if (!isOpen || !reviewData) return null

  const errorCount = validation?.error_count ?? 0
  const warnCount = validation?.warning_count ?? 0
  const isExportable = validation?.is_exportable ?? false
  const hasErrors = errorCount > 0

  // Role-aware approve logic:
  // - staff : can export only when there are NO errors (warnings are OK)
  // - qc/ad : can override and export even with warnings (cv:override_export)
  const canOverride = userRole === 'qc' || userRole === 'admin'
  const canApprove = !hasErrors || canOverride
  const isOverride = hasErrors && canOverride

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, width: '100%', maxWidth: 900,
        maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid #E5E7EB',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: '#1B2A4A', color: '#fff', borderRadius: '12px 12px 0 0',
        }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>
              🔍 Review CV: {reviewData.original_filename}
            </div>
            <div style={{ fontSize: 12, opacity: 0.8, marginTop: 2 }}>
              {validation?.summary ?? 'No validation data'}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Status badges */}
            {errorCount > 0 && (
              <span style={{ background: '#EF4444', color: '#fff', borderRadius: 12, padding: '2px 10px', fontSize: 12 }}>
                {errorCount} lỗi
              </span>
            )}
            {warnCount > 0 && (
              <span style={{ background: '#F59E0B', color: '#fff', borderRadius: 12, padding: '2px 10px', fontSize: 12 }}>
                {warnCount} cảnh báo
              </span>
            )}
            {!isExportable && (
              <span style={{ background: '#DC2626', color: '#fff', borderRadius: 8, padding: '2px 8px', fontSize: 11, fontWeight: 700 }}>
                {canOverride ? '⚠️ CẢNH BÁO' : '🔒 CHƯA PHÊ DUYỆT'}
              </span>
            )}
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer', lineHeight: 1 }}
            >
              &times;
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #E5E7EB', background: '#F9FAFB' }}>
          {(['fields', 'errors', 'preview'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '8px 16px', border: 'none', background: 'none',
                cursor: 'pointer', fontSize: 13, fontWeight: 600,
                color: activeTab === tab ? '#1B2A4A' : '#6B7280',
                borderBottom: activeTab === tab ? '2px solid #1B2A4A' : '2px solid transparent',
                textTransform: 'capitalize',
              }}
            >
              {tab === 'fields' && '📝 Chỉnh sửa fields'}
              {tab === 'errors' && `⚠️ Validation (${errorCount + warnCount})`}
              {tab === 'preview' && '👁️ Preview data'}
            </button>
          ))}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {/* FIELDS TAB */}
          {activeTab === 'fields' && (
            <div>
              {/* Personal info */}
              <SectionAccordion title="👤 Thông tin cá nhân" defaultOpen>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                  <EditableField label="Họ tên đầy đủ" value={currentData.full_name} onChange={v => updateField('full_name', v)} />
                  <EditableField label="Email" value={currentData.email} onChange={v => updateField('email', v)} />
                  <EditableField label="Số điện thoại" value={currentData.phone} onChange={v => updateField('phone', v)} />
                  <EditableField label="Năm sinh" value={currentData.year_of_birth} onChange={v => updateField('year_of_birth', v)} hint="YYYY" />
                  <EditableField label="Giới tính" value={currentData.gender} onChange={v => updateField('gender', v)} hint="Male/Female/Nam/Nữ" />
                  <EditableField label="Tình trạng hôn nhân" value={currentData.marital_status} onChange={v => updateField('marital_status', v)} />
                </div>
                <EditableField label="Địa chỉ" value={currentData.address} onChange={v => updateField('address', v)} multiline />
              </SectionAccordion>

              {/* Career */}
              <SectionAccordion
                title="💼 Kinh nghiệm làm việc"
                badge={`${currentData.career_summary?.length ?? 0} jobs`}
              >
                {(currentData.career_summary ?? []).map((job, i) => (
                  <div key={i} style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginBottom: 8, background: '#F9FAFB' }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#6B7280', marginBottom: 8 }}>
                      Job #{i + 1}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
                      <EditableField label="Công ty" value={job.company} onChange={v => updateField(`career_summary[${i}].company`, v)} />
                      <EditableField label="Thời gian (period)" value={job.period} onChange={v => updateField(`career_summary[${i}].period`, v)} hint="MM/YYYY - Present" />
                    </div>
                    {(job.positions ?? []).map((pos, j) => (
                      <div key={j} style={{ marginTop: 8, borderTop: '1px dashed #D1D5DB', paddingTop: 8 }}>
                        <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>Vị trí #{j + 1}</div>
                        <EditableField label="Chức danh (title)" value={pos.title} onChange={v => updateField(`career_summary[${i}].positions[${j}].title`, v)} />
                        <EditableField
                          label="Mô tả công việc"
                          value={(pos.responsibilities ?? []).join('\n')}
                          onChange={v => updateField(`career_summary[${i}].positions[${j}].responsibilities`, v)}
                          multiline
                          hint="Mỗi dòng = 1 bullet point"
                        />
                      </div>
                    ))}
                  </div>
                ))}
                {(!currentData.career_summary || currentData.career_summary.length === 0) && (
                  <div style={{ color: '#9CA3AF', textAlign: 'center', padding: 20 }}>
                    Không có kinh nghiệm làm việc
                  </div>
                )}
              </SectionAccordion>

              {/* Education */}
              <SectionAccordion
                title="🎓 Học vấn"
                badge={`${currentData.education?.length ?? 0}`}
              >
                {(currentData.education ?? []).map((edu, i) => (
                  <div key={i} style={{ border: '1px solid #E5E7EB', borderRadius: 8, padding: 12, marginBottom: 8, background: '#F9FAFB' }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#6B7280', marginBottom: 8 }}>
                      Education #{i + 1}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
                      <EditableField label="Trường học" value={edu.institution} onChange={v => updateField(`education[${i}].institution`, v)} />
                      <EditableField label="Thời gian" value={edu.period} onChange={v => updateField(`education[${i}].period`, v)} hint="YYYY - YYYY" />
                    </div>
                    <EditableField
                      label="Chi tiết"
                      value={(edu.details ?? []).join('\n')}
                      onChange={v => updateField(`education[${i}].details`, v)}
                      multiline
                    />
                  </div>
                ))}
              </SectionAccordion>

              {/* Other info */}
              <SectionAccordion
                title="📋 Thông tin khác"
                badge={`${currentData.other_info?.length ?? 0}`}
              >
                {(currentData.other_info ?? []).map((section, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <EditableField
                      label="Section title"
                      value={section.section_title}
                      onChange={v => updateField(`other_info[${i}].section_title`, v)}
                    />
                    <EditableField
                      label="Items"
                      value={(section.items ?? []).join('\n')}
                      onChange={v => updateField(`other_info[${i}].items`, v)}
                      multiline
                      hint="Mỗi dòng = 1 item"
                    />
                  </div>
                ))}
              </SectionAccordion>
            </div>
          )}

          {/* ERRORS TAB */}
          {activeTab === 'errors' && (
            <div>
              {errorCount === 0 && warnCount === 0 ? (
                <div style={{ textAlign: 'center', padding: 40, color: '#10B981' }}>
                  <div style={{ fontSize: 48 }}>✅</div>
                  <div style={{ fontSize: 16, fontWeight: 700, marginTop: 8 }}>Tất cả đều OK!</div>
                  <div style={{ color: '#6B7280', marginTop: 4 }}>Không có lỗi validation</div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {validation?.errors.map((err, i) => (
                    <ValidationBadge key={`err-${i}`} error={err} />
                  ))}
                  {validation?.warnings.map((warn, i) => (
                    <ValidationBadge key={`warn-${i}`} error={warn} />
                  ))}
                  {validation?.info.map((info, i) => (
                    <ValidationBadge key={`info-${i}`} error={info} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* PREVIEW TAB */}
          {activeTab === 'preview' && (
            <div>
              <pre style={{
                background: '#1B2A4A', color: '#E5E7EB', padding: 16,
                borderRadius: 8, fontSize: 12, overflow: 'auto', maxHeight: 500,
                fontFamily: 'monospace',
              }}>
                {JSON.stringify(currentData, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div style={{
          padding: '12px 20px', borderTop: '1px solid #E5E7EB',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: '#F9FAFB', flexShrink: 0,
        }}>
          <div style={{ fontSize: 12, color: '#9CA3AF' }}>
            {hasEdits && <span>⚠️ Có thay đổi chưa lưu</span>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Hủy
            </button>
            <button
              className="btn"
              onClick={() => onSave(currentData)}
              disabled={isSubmitting}
              style={{ background: '#6B7280', color: '#fff' }}
            >
              {isSubmitting ? '⏳...' : '💾 Lưu & tiếp tục'}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => onApprove(currentData)}
              disabled={isSubmitting || !canApprove}
              style={{
                background: hasErrors
                  ? (canOverride ? '#F59E0B' : '#9CA3AF')
                  : '#10B981',
              }}
            >
              {isSubmitting ? '⏳...' : hasErrors ? (
                canOverride ? '⚠️ Phê duyệt & Export (override)' : '🔒 Cần QC/Admin phê duyệt'
              ) : '✅ Phê duyệt & Export'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
