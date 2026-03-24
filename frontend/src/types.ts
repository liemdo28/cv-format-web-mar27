export interface FileItem {
  id: string
  name: string
  type: 'PDF' | 'DOCX'
  status: 'pending' | 'processing' | 'success' | 'partial' | 'error'
  message: string
  file?: File
}

export interface Settings {
  apiKey: string
  model: string
  extractionMode: 'auto' | 'claude_api' | 'ollama' | 'cached'
  backendUrl: string
}

export interface ProcessResult {
  status: 'success' | 'error' | 'partial'
  message: string
  outputUrl?: string
}
