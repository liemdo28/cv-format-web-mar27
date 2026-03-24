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
}

export interface Settings {
  apiKey: string
  openaiApiKey: string
  model: string
  openaiModel: string
  extractionMode: 'auto' | 'claude_api' | 'openai_api' | 'ollama' | 'cached'
  backendUrl: string
}

export interface ProcessResult {
  status: 'success' | 'error' | 'partial'
  message: string
  suggestedName?: string
  downloadId?: string
  downloadUrl?: string
}
