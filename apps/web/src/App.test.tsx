import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

describe("App", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("guides a new user through one question at a time", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(null));
    render(<App />);

    expect(await screen.findByText("把研究交给系统，把决定留给自己。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "用推荐设置开始" }));
    expect(screen.getByRole("heading", { name: "你通常持有多久？" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "继续" }));
    expect(screen.getByRole("heading", { name: "你更看重哪种风险方式？" })).toBeInTheDocument();
  });

  it("shows truthful empty states for a configured profile", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(profile))
      .mockResolvedValueOnce(
        jsonResponse({
          setup_required: false,
          market_summary: "行情数据尚未接入，今天不生成操作建议。",
          data_as_of: null,
          positions_message: "当前没有需要处理的持仓。",
          candidates_message: "当前没有可验证的候选机会。",
          exceptions_count: 0,
          learning_message: "系统骨架运行正常。",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "degraded",
          database: { status: "ok", message: "业务数据库连接正常" },
          worker: { status: "unavailable", message: "后台任务尚未启动" },
          market_data: { status: "not_configured", message: "行情服务尚未配置" },
          ai_service: { status: "not_configured", message: "AI 服务尚未配置" },
        }),
      );

    render(<App />);

    expect(await screen.findByRole("heading", { name: "目前不需要你做任何操作。" })).toBeInTheDocument();
    expect(screen.getByText("行情数据尚未接入，今天不生成操作建议。")).toBeInTheDocument();
    expect(screen.getByText("没有满足条件的股票")).toBeInTheDocument();
  });
});

const profile = {
  id: "3b1cb993-e91e-4a58-9d5a-b3dc720a595f",
  market: "a_share",
  holding_horizon: "swing",
  risk_level: "balanced",
  single_position_limit: "0.2000",
  notification_time: "18:30",
  risk_policy_version: 1,
  live_trading_enabled: false,
  updated_at: "2026-10-23T10:00:00Z",
};

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}

