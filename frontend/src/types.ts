// ── Auth types ──────────────────────────────────────────────────

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'staff' | 'qc'
  is_active: boolean
  created_at?: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export interface RefreshRequest {
  refresh_token: string
}

// ── CV Job types ────────────────────────────────────────────────

export type CVJobStatus =
  | 'uploaded'
  | 'parsing'
  | 'parsed'
  | 'validated'
  | 'review'
  | 'qc'
  | 'approved'
  | 'exported'
  | 'error'
  | 'cancelled'

export interface ValidationError {
  field: string
  code: string
  message: string
  severity: 'error' | 'warning' | 'info'
  value?: string
  suggestion?: string
}

export interface ValidationResult {
  is_valid: boolean
  is_exportable: boolean
  error_count: number
  warning_count: number
  errors: ValidationError[]
  warnings: ValidationError[]
  info: ValidationError[]
  summary: string
}

export interface CVJob {
  id: string
  owner_id: string
  qc_by?: string
  original_filename: string
  file_size: number
  file_type: 'pdf' | 'docx'
  status: CVJobStatus
  extraction_mode: string
  parsed_data?: ParsedCVData
  parsed_at?: string
  validation_result?: ValidationResult
  validated_at?: string
  reviewed_data?: ParsedCVData
  reviewed_at?: string
  qc_result?: 'pass' | 'fail' | 'needs_revision'
  qc_notes?: string
  qc_at?: string
  output_filename?: string
  download_url?: string
  exported_at?: string
  created_at?: string
  updated_at?: string
  completed_at?: string
}

export interface CVVersion {
  id: string
  job_id: string
  version_number: number
  changed_by_id: string
  changed_by_role: string
  change_type: string
  data_snapshot: ParsedCVData
  notes?: string
  created_at?: string
}

// ── Parsed CV data (mirrors backend) ────────────────────────────

export interface Position {
  period?: string
  title?: string
  report_to?: string
  section_label?: string
  responsibilities?: string[]
  achievements_label?: string
  achievements?: string[]
}

export interface CareerEntry {
  period?: string
  company?: string
  company_description?: string
  positions?: Position[]
  responsibilities?: string[]
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
  // Offline engine fields
  current_company?: string
  current_position?: string
  summary?: string
  experience?: string
  skills?: string
  languages?: string
  [key: string]: unknown
}

// ── Batch processing types ──────────────────────────────────────

export type BatchJobStatus =
  | 'queued'
  | 'processing'
  | 'parsed'
  | 'validated'
  | 'review'
  | 'approved'
  | 'exporting'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface BatchJob {
  id: string
  batch_id: string
  original_filename: string
  file_type: string
  file_size: number
  status: BatchJobStatus
  progress: number  // 0.0 - 1.0
  message: string
  validation_result?: ValidationResult
  error?: string
  retry_count: number
  created_at?: string
  started_at?: string
  completed_at?: string
}

export interface Batch {
  id: string
  name: string
  owner_id: string
  job_count: number
  completed: number
  failed: number
  status: 'running' | 'completed' | 'completed_with_errors' | 'cancelled'
  created_at?: string
  completed_at?: string
}

// ── File processing (existing types) ───────────────────────────

export interface ReviewItem {
  placeholder: string
  mappedField: string
  confidence: number
  filled: boolean
}

export interface FileItem {
  id: string
  name: string
  filename: string
  type: 'PDF' | 'DOCX'
  status: 'pending' | 'processing' | 'success' | 'partial' | 'error'
  message: string
  file?: File
  downloadId?: string
  downloadUrl?: string
  reviewRequired?: ReviewItem[]
  // Extended fields (new)
  job_id?: string
  batch_id?: string
  validation_result?: ValidationResult
  cv_data?: ParsedCVData
}

export interface Settings {
  apiKey: string
  openaiApiKey: string
  model: string
  openaiModel: string
  extractionMode: 'auto' | 'claude_api' | 'openai_api' | 'ollama' | 'cached' | 'offline'
  backendUrl: string
}

export interface ProcessResult {
  status: 'success' | 'error' | 'partial'
  message: string
  suggestedName?: string
  downloadId?: string
  downloadUrl?: string
  reviewRequired?: ReviewItem[]
  // New: full job response
  job_id?: string
  batch_id?: string
  validation_result?: ValidationResult
  parsed_data?: ParsedCVData
}

// ── Audit log ───────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string
  user_id: string
  user_role: string
  action: string
  resource_type?: string
  resource_id?: string
  details?: Record<string, unknown>
  ip_address?: string
  created_at?: string
}
