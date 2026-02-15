/**
 * Debug Panel Types
 *
 * Types for the debug API responses and frontend components.
 */

export type SessionStatus = 'pending' | 'success' | 'error' | 'partial';

export interface DebugSession {
  session_id: string;
  timestamp: string;
  user_id: number | null;
  user_role: string | null;
  input_message: string;
  status: SessionStatus;
  llm_model: string | null;
  llm_tokens_used: number | null;
  execution_time_ms: number | null;
  attempt_count?: number;
  action_type?: string | null;
}

export interface DebugSessionDetail extends DebugSession {
  retrieved_schema: Record<string, unknown> | null;
  retrieved_tools: Record<string, unknown>[] | null;
  llm_prompt: string | null;
  llm_response: string | null;
  llm_prompt_parts: Record<string, unknown> | null;
  llm_response_parsed: Record<string, unknown> | null;
  llm_latency_ms: number | null;
  actions_executed: Record<string, unknown>[] | null;
  final_result: Record<string, unknown> | null;
  errors: Record<string, unknown>[] | null;
  metadata: Record<string, unknown> | null;
}

export interface AttemptLog {
  attempt_id: string;
  session_id: string;
  attempt_number: number;
  action_name: string;
  params: Record<string, unknown>;
  success: boolean;
  error: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  timestamp: string;
}

export interface SessionDetailResponse {
  session: DebugSessionDetail;
  attempts: AttemptLog[];
}

export interface ReplayOverrides {
  llm_model?: string;
  llm_temperature?: number;
  llm_max_tokens?: number;
  llm_base_url?: string;
  action_params_override?: Record<string, Record<string, unknown>>;
}

export interface ReplayRequest {
  session_id: string;
  overrides?: ReplayOverrides;
  dry_run?: boolean;
}

export interface ReplayResult {
  replay_id: string;
  original_session_id: string;
  success: boolean;
  result: Record<string, unknown> | null;
  attempts: Record<string, unknown>[];
  execution_time_ms: number;
  llm_model: string;
  llm_tokens_used: number | null;
  error: string | null;
  timestamp: string;
  dry_run: boolean;
}

export interface SessionDiff {
  status_changed: boolean;
  original_status: string;
  replay_status: string;
  result_changed: boolean;
  original_result: Record<string, unknown> | null;
  replay_result: Record<string, unknown> | null;
  field_diffs: Record<string, { original: unknown; replay: unknown }>;
}

export interface AttemptDiff {
  attempt_number: number;
  success_changed: boolean;
  original_success: boolean;
  replay_success: boolean;
  params_changed: boolean;
  original_params: Record<string, unknown>;
  replay_params: Record<string, unknown>;
  error_changed: boolean;
  original_error: string | null;
  replay_error: string | null;
}

export interface PerformanceDiff {
  execution_time_diff_ms: number | null;
  execution_time_change_pct: number | null;
  tokens_diff: number | null;
  tokens_change_pct: number | null;
}

export interface ReplayComparison {
  session_comparison: SessionDiff;
  attempt_comparison: AttemptDiff[];
  performance_diff: PerformanceDiff;
  summary: string;
  replay_metadata: Record<string, unknown>;
}

export interface ReplayResponse {
  replay: ReplayResult;
  original_session: DebugSessionDetail;
  comparison: ReplayComparison | null;
}

export interface DebugStatistics {
  total_sessions: number;
  total_attempts: number;
  status_counts: Record<string, number>;
  recent_sessions_24h: number;
}

export interface SessionsListResponse {
  sessions: DebugSession[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReplaysListResponse {
  replays: ReplayResult[];
  count: number;
}

// Analytics types

export interface TokenTrendDataPoint {
  day: string;
  session_count: number;
  total_tokens: number;
  avg_tokens: number;
  avg_latency_ms: number;
}

export interface TokenTrendResponse {
  days: number;
  data: TokenTrendDataPoint[];
}

export interface TopError {
  error_msg: string;
  count: number;
}

export interface ErrorAggregationResponse {
  days: number;
  by_day: { day: string; error_count: number }[];
  top_errors: TopError[];
  totals: {
    total_sessions: number;
    error_sessions: number;
    success_sessions: number;
  };
}
