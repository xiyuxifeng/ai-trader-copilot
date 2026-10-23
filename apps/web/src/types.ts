export type HoldingHorizon = "short" | "swing" | "long";
export type RiskLevel = "conservative" | "balanced" | "aggressive";

export interface Profile {
  id: string;
  market: "a_share";
  holding_horizon: HoldingHorizon;
  risk_level: RiskLevel;
  single_position_limit: string;
  notification_time: string;
  risk_policy_version: number;
  live_trading_enabled: false;
  updated_at: string;
}

export interface TodayData {
  setup_required: boolean;
  market_summary: string;
  data_as_of: string | null;
  positions_message: string;
  candidates_message: string;
  exceptions_count: number;
  learning_message: string;
}

export interface ComponentHealth {
  status: "ok" | "unavailable" | "not_configured";
  message: string;
}

export interface HealthData {
  status: "ok" | "degraded";
  database: ComponentHealth;
  worker: ComponentHealth;
  market_data: ComponentHealth;
  ai_service: ComponentHealth;
}

export interface OnboardingInput {
  holding_horizon: HoldingHorizon;
  risk_level: RiskLevel;
  single_position_limit: string;
  notification_time: string;
}

