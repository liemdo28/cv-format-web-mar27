export interface FileItem {
  id: string
  name: string           // original filename
  filename: string       // editable output filename
  type: 'PDF' | 'DOCX'
  status: 'pending' | 'processing' | 'success' | 'partial' | 'error'
  message: string
  file?: File
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
  outputDocxPath?: string
}
