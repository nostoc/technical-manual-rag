export interface TableData {
  file_name: string;
  page: number;
  table_index: number;
  headers: string[];
  rows: Record<string, string>[];
  col_names: string[]
}

export interface SourceNode {
  type: "text" | "table_summary";
  file_name: string;
  page: number | string;
  snippet: string;
  score: number | null;
}

export interface QueryResponse {
  answer: string;
  images: string[];
  tables: TableData[];
  sources: SourceNode[];
}

export interface Message {
  role: "user" | "assistant" | "error";
  text?: string;
  answer?: string;
  images?: string[];
  tables?: TableData[];
  sources?: SourceNode[];
}

export interface UploadResponse {
  message: string;
  file: string;
}

export interface HealthResponse {
  status: string;
}