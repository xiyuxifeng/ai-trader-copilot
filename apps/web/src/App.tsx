import { useEffect, useState } from "react";

import { getHealth, getProfile, getToday, saveOnboarding } from "./api";
import type {
  HealthData,
  HoldingHorizon,
  OnboardingInput,
  Profile,
  RiskLevel,
  TodayData,
} from "./types";

type Screen = "today" | "analysis" | "trader" | "settings";

const horizonLabels: Record<HoldingHorizon, { title: string; detail: string }> = {
  short: { title: "短线", detail: "关注数日至两周内的交易机会" },
  swing: { title: "波段", detail: "关注数周到数月的趋势，推荐" },
  long: { title: "中长线", detail: "关注季度以上的基本趋势" },
};

const riskLabels: Record<RiskLevel, { title: string; detail: string; limit: number }> = {
  conservative: { title: "保守", detail: "更重视回撤和本金保护", limit: 10 },
  balanced: { title: "均衡", detail: "在机会和风险之间保持平衡，推荐", limit: 20 },
  aggressive: { title: "进取", detail: "接受更大波动，仍受风险上限保护", limit: 30 },
};

export function App() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [screen, setScreen] = useState<Screen>("today");
  const [editingSettings, setEditingSettings] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    getProfile()
      .then(setProfile)
      .catch((error: Error) => setBootError(error.message));
  }, []);

  if (bootError) {
    return <ServiceError message={bootError} />;
  }

  if (profile === undefined) {
    return <LoadingScreen />;
  }

  if (profile === null || editingSettings) {
    return (
      <Onboarding
        initialProfile={editingSettings ? profile : null}
        onComplete={(nextProfile) => {
          setProfile(nextProfile);
          setEditingSettings(false);
          setScreen("today");
        }}
        onCancel={editingSettings ? () => setEditingSettings(false) : undefined}
      />
    );
  }

  return (
    <AppShell screen={screen} onNavigate={setScreen} onOpenSettings={() => setScreen("settings")}>
      {screen === "today" && <TodayPage />}
      {screen === "analysis" && <AnalysisPage />}
      {screen === "trader" && <TraderPage />}
      {screen === "settings" && (
        <SettingsPage profile={profile} onEdit={() => setEditingSettings(true)} />
      )}
    </AppShell>
  );
}

function Onboarding({
  initialProfile,
  onComplete,
  onCancel,
}: {
  initialProfile: Profile | null;
  onComplete: (profile: Profile) => void;
  onCancel?: () => void;
}) {
  const [step, setStep] = useState(initialProfile ? 1 : 0);
  const [horizon, setHorizon] = useState<HoldingHorizon>(
    initialProfile?.holding_horizon ?? "swing",
  );
  const [risk, setRisk] = useState<RiskLevel>(initialProfile?.risk_level ?? "balanced");
  const [positionLimit, setPositionLimit] = useState(
    initialProfile ? String(Math.round(Number(initialProfile.single_position_limit) * 100)) : "20",
  );
  const [notificationTime, setNotificationTime] = useState(
    initialProfile?.notification_time ?? "18:30",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setSaving(true);
    setError(null);
    const input: OnboardingInput = {
      holding_horizon: horizon,
      risk_level: risk,
      single_position_limit: (Number(positionLimit) / 100).toFixed(2),
      notification_time: notificationTime,
    };
    try {
      onComplete(await saveOnboarding(input));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="onboarding-shell">
      <section className="onboarding-panel" aria-labelledby="onboarding-title">
        <Brand />
        {step > 0 && (
          <div className="progress-wrap" aria-label={`设置进度：第 ${step} 步，共 4 步`}>
            <div className="progress-track" aria-hidden="true">
              <span style={{ width: `${step * 25}%` }} />
            </div>
            <span>{step}/4</span>
          </div>
        )}

        {step === 0 && (
          <div className="step-content intro">
            <p className="eyebrow">你的私人交易研究助手</p>
            <h1 id="onboarding-title">把研究交给系统，把决定留给自己。</h1>
            <p className="lead">
              系统会自动学习文章、验证规则并提示风险。它不会连接券商，也不会替你下单。
            </p>
            <button className="primary-button" type="button" onClick={() => setStep(1)}>
              用推荐设置开始
            </button>
          </div>
        )}

        {step === 1 && (
          <ChoiceStep
            title="你通常持有多久？"
            description="这会影响系统选择信号和评估规则的时间范围。"
            value={horizon}
            options={horizonLabels}
            onChange={(value) => setHorizon(value as HoldingHorizon)}
            onBack={onCancel ?? (() => setStep(0))}
            onNext={() => setStep(2)}
          />
        )}

        {step === 2 && (
          <ChoiceStep
            title="你更看重哪种风险方式？"
            description="系统会据此生成安全边界，之后可以随时调整。"
            value={risk}
            options={riskLabels}
            onChange={(value) => {
              const nextRisk = value as RiskLevel;
              setRisk(nextRisk);
              setPositionLimit(String(riskLabels[nextRisk].limit));
            }}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}

        {step === 3 && (
          <form
            className="step-content"
            onSubmit={(event) => {
              event.preventDefault();
              setStep(4);
            }}
          >
            <p className="eyebrow">风险上限</p>
            <h1 id="onboarding-title">单只股票最多投入多少？</h1>
            <p className="lead">推荐值已经根据你的风险偏好生成。</p>
            <label className="field-label" htmlFor="position-limit">
              最大仓位
            </label>
            <div className="percentage-field">
              <input
                id="position-limit"
                type="number"
                inputMode="decimal"
                min="5"
                max="50"
                step="1"
                value={positionLimit}
                onChange={(event) => setPositionLimit(event.target.value)}
                required
              />
              <span aria-hidden="true">%</span>
            </div>
            <p className="field-help">允许范围 5%～50%，这只是上限，不代表每次都要用满。</p>
            <StepActions onBack={() => setStep(2)} label="继续" />
          </form>
        )}

        {step === 4 && (
          <form
            className="step-content"
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <p className="eyebrow">最后一步</p>
            <h1 id="onboarding-title">什么时候接收每日摘要？</h1>
            <p className="lead">只有需要行动的风险会即时提醒，其余内容统一汇总。</p>
            <label className="field-label" htmlFor="notification-time">
              每日摘要时间
            </label>
            <input
              className="time-field"
              id="notification-time"
              type="time"
              value={notificationTime}
              onChange={(event) => setNotificationTime(event.target.value)}
              required
            />
            {error && <p role="alert" className="error-message">{error}</p>}
            <StepActions onBack={() => setStep(3)} label={saving ? "正在保存…" : "完成设置"} disabled={saving} />
          </form>
        )}
      </section>
    </main>
  );
}

function ChoiceStep({
  title,
  description,
  value,
  options,
  onChange,
  onBack,
  onNext,
}: {
  title: string;
  description: string;
  value: string;
  options: Record<string, { title: string; detail: string }>;
  onChange: (value: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <div className="step-content">
      <p className="eyebrow">个性化设置</p>
      <h1 id="onboarding-title">{title}</h1>
      <p className="lead">{description}</p>
      <fieldset className="choice-list">
        <legend className="sr-only">{title}</legend>
        {Object.entries(options).map(([key, option]) => (
          <label className={`choice-item ${value === key ? "selected" : ""}`} key={key}>
            <input
              type="radio"
              name="choice"
              value={key}
              checked={value === key}
              onChange={() => onChange(key)}
            />
            <span>
              <strong>{option.title}</strong>
              <small>{option.detail}</small>
            </span>
          </label>
        ))}
      </fieldset>
      <StepActions onBack={onBack} onNext={onNext} label="继续" />
    </div>
  );
}

function StepActions({
  onBack,
  onNext,
  label,
  disabled = false,
}: {
  onBack: () => void;
  onNext?: () => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div className="step-actions">
      <button className="text-button" type="button" onClick={onBack} disabled={disabled}>
        返回
      </button>
      <button className="primary-button" type={onNext ? "button" : "submit"} onClick={onNext} disabled={disabled}>
        {label}
      </button>
    </div>
  );
}

function AppShell({
  screen,
  onNavigate,
  onOpenSettings,
  children,
}: {
  screen: Screen;
  onNavigate: (screen: Screen) => void;
  onOpenSettings: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <button className="settings-button" type="button" onClick={onOpenSettings} aria-current={screen === "settings" ? "page" : undefined}>
          设置
        </button>
      </header>
      <nav className="primary-nav" aria-label="主导航">
        {([
          ["today", "今天"],
          ["analysis", "分析"],
          ["trader", "我的交易员"],
        ] as const).map(([key, label]) => (
          <button
            type="button"
            key={key}
            className={screen === key ? "active" : ""}
            aria-current={screen === key ? "page" : undefined}
            onClick={() => onNavigate(key)}
          >
            {label}
          </button>
        ))}
      </nav>
      <main className="page-content">{children}</main>
    </div>
  );
}

function Brand() {
  return (
    <div className="brand" aria-label="AI-Trader Copilot">
      <span className="brand-mark" aria-hidden="true">AI</span>
      <span>AI-Trader</span>
    </div>
  );
}

function TodayPage() {
  const [today, setToday] = useState<TodayData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getToday(), getHealth()])
      .then(([todayData, healthData]) => {
        setToday(todayData);
        setHealth(healthData);
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, []);

  if (error) return <InlineError message={error} />;
  if (!today || !health) return <PageLoading />;

  return (
    <div className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">今天</p>
        <h1>目前不需要你做任何操作。</h1>
        <p>系统只会在数据和规则都通过验证后给出建议。</p>
      </header>

      <section className="status-banner" aria-labelledby="market-status-title">
        <span className="status-dot neutral" aria-hidden="true" />
        <div>
          <h2 id="market-status-title">市场分析尚未开始</h2>
          <p>{today.market_summary}</p>
        </div>
      </section>

      <div className="content-grid">
        <section className="quiet-section">
          <p className="section-kicker">持仓</p>
          <h2>没有需要处理的风险</h2>
          <p>{today.positions_message}</p>
        </section>
        <section className="quiet-section">
          <p className="section-kicker">候选机会</p>
          <h2>没有满足条件的股票</h2>
          <p>{today.candidates_message}</p>
        </section>
      </div>

      <details className="learning-summary">
        <summary>系统状态与学习进度</summary>
        <p>{today.learning_message}</p>
        <ul className="health-list">
          <HealthItem label="业务数据" value={health.database} />
          <HealthItem label="后台任务" value={health.worker} />
          <HealthItem label="行情数据" value={health.market_data} />
          <HealthItem label="AI 服务" value={health.ai_service} />
        </ul>
      </details>
    </div>
  );
}

function HealthItem({ label, value }: { label: string; value: HealthData["database"] }) {
  return (
    <li>
      <span>{label}</span>
      <span className={`health-value ${value.status}`}>{value.message}</span>
    </li>
  );
}

function AnalysisPage() {
  return (
    <div className="page-stack narrow-page">
      <header className="page-heading">
        <p className="eyebrow">分析</p>
        <h1>分析一只股票</h1>
        <p>行情接入并通过质量验证后，这里会开放股票分析。</p>
      </header>
      <label className="field-label" htmlFor="stock-query">股票代码、名称或问题</label>
      <div className="search-row">
        <input id="stock-query" type="search" placeholder="例如：600519 或 贵州茅台" disabled />
        <button type="button" disabled>分析</button>
      </div>
      <p className="field-help">当前不提供模拟建议，避免把占位内容误认为真实分析。</p>
    </div>
  );
}

function TraderPage() {
  return (
    <div className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">我的交易员</p>
        <h1>你的规则库还是空的。</h1>
        <p>文章学习功能将在证据提取和验证链通过下一阶段门禁后开放。</p>
      </header>
      <section className="quiet-section full-width">
        <p className="section-kicker">后台研究</p>
        <h2>尚未开始</h2>
        <p>目前没有正在学习、验证或等待确认的规则。</p>
      </section>
    </div>
  );
}

function SettingsPage({ profile, onEdit }: { profile: Profile; onEdit: () => void }) {
  return (
    <div className="page-stack narrow-page">
      <header className="page-heading">
        <p className="eyebrow">设置</p>
        <h1>交易偏好与风险</h1>
        <p>没有异常时，你不需要经常来这里。</p>
      </header>
      <dl className="settings-list">
        <div><dt>交易市场</dt><dd>A 股</dd></div>
        <div><dt>操作周期</dt><dd>{horizonLabels[profile.holding_horizon].title}</dd></div>
        <div><dt>风险偏好</dt><dd>{riskLabels[profile.risk_level].title}</dd></div>
        <div><dt>单只股票最大仓位</dt><dd>{Math.round(Number(profile.single_position_limit) * 100)}%</dd></div>
        <div><dt>每日摘要</dt><dd>{profile.notification_time}</dd></div>
        <div><dt>自动下单</dt><dd>未启用，且 v1 不支持</dd></div>
      </dl>
      <button className="secondary-button" type="button" onClick={onEdit}>调整偏好</button>
    </div>
  );
}

function LoadingScreen() {
  return <main className="center-state" aria-live="polite">正在确认系统状态…</main>;
}

function PageLoading() {
  return <div className="page-loading" aria-live="polite">正在准备今天的状态…</div>;
}

function ServiceError({ message }: { message: string }) {
  return (
    <main className="center-state error-state">
      <Brand />
      <h1>系统暂时无法启动</h1>
      <p role="alert">{message}</p>
      <p>没有生成任何交易建议，请确认 API 和数据库已经启动。</p>
    </main>
  );
}

function InlineError({ message }: { message: string }) {
  return <div className="inline-error" role="alert">{message} 当前不生成任何建议。</div>;
}

