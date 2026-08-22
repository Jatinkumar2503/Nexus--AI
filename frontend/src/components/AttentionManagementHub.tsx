import React, { useState, useEffect } from "react";
import {
  Brain,
  Sliders,
  Bell,
  AlertTriangle,
  Zap,
  ShieldCheck,
  SlidersHorizontal,
  ChevronRight,
  Sparkles,
  Layers,
  Edit3,
  TrendingUp,
  CheckCircle,
  XCircle,
  Check
} from "lucide-react";

interface AttentionSettings {
  auto_approve_confidence_threshold: number;
  interruption_sensitivity: "LOW" | "BALANCED" | "HIGH";
  batch_review_interval_sec: number;
  max_batch_size: number;
  crli_overload_threshold: number;
  enable_auto_approval: boolean;
  enable_smart_prefill: boolean;
  enable_dispatcher_learning: boolean;
}

interface CRLIData {
  crli_score: number;
  load_state: "QUIET" | "FOCUSED" | "OVERLOAD";
  recommendation: string;
  components: {
    disruption_load: number;
    queue_load: number;
    density_load: number;
    uncertainty_load: number;
  };
}

interface SensibleDefaults {
  defaults: {
    hold_duration_min: number;
    recommended_platform: string;
    detour_route: string;
    target_speed_kmh: number;
    precedence_swap: boolean;
  };
  is_editable: boolean;
  rationale: string[];
  historical_learning?: {
    historical_acceptance_rate_pct: number;
    total_decisions_analyzed: number;
    confidence_in_defaults: string;
  };
  derived_from_context: {
    delay_severity: string;
    weather_impact: string;
    priority_weight: number;
  };
}

export const AttentionManagementHub: React.FC = () => {
  const [crli, setCrli] = useState<CRLIData>({
    crli_score: 28.5,
    load_state: "QUIET",
    recommendation: "Normal operations. Low mental pressure. Full manual review active.",
    components: { disruption_load: 12.5, queue_load: 7.0, density_load: 6.0, uncertainty_load: 3.0 }
  });

  const [settings, setSettings] = useState<AttentionSettings>({
    auto_approve_confidence_threshold: 85,
    interruption_sensitivity: "BALANCED",
    batch_review_interval_sec: 30,
    max_batch_size: 5,
    crli_overload_threshold: 75,
    enable_auto_approval: true,
    enable_smart_prefill: true,
    enable_dispatcher_learning: true
  });

  // Simulator Input State
  const [simDelay, setSimDelay] = useState<number>(14);
  const [simWeather, setSimWeather] = useState<string>("standard");
  const [simPriority, setSimPriority] = useState<number>(4);

  const [defaults, setDefaults] = useState<SensibleDefaults>({
    defaults: {
      hold_duration_min: 5,
      recommended_platform: "PF_2 (Fast Bypass)",
      detour_route: "SLOW_LINE_CROSSOVER",
      target_speed_kmh: 90,
      precedence_swap: true
    },
    is_editable: true,
    rationale: [
      "Hold duration (5m) derived from accumulated delay (14m) and weather headway buffer.",
      "Moderate delay (8-14m): applying slow-line crossover switch.",
      "Platform 'PF_2' pre-filled based on train priority (4/5) and class.",
      "Target speed (90 km/h) constrained by MPS (130 km/h) and safety envelopes."
    ],
    historical_learning: {
      historical_acceptance_rate_pct: 83.3,
      total_decisions_analyzed: 12,
      confidence_in_defaults: "HIGH"
    },
    derived_from_context: {
      delay_severity: "HIGH",
      weather_impact: "STANDARD",
      priority_weight: 4.0
    }
  });

  const [isSaved, setIsSaved] = useState(false);
  const [activeTab, setActiveTab] = useState<"defaults" | "triage" | "learning" | "settings">("defaults");

  const fetchAttentionData = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/nexus/attention/context-defaults");
      if (res.ok) {
        const data = await res.json();
        if (data.crli) setCrli(data.crli);
        if (data.editable_settings) setSettings(data.editable_settings);
        if (data.sample_defaults) setDefaults(data.sample_defaults);
      }
    } catch (err) {
      console.log("Using local attention context data", err);
    }
  };

  useEffect(() => {
    fetchAttentionData();
    const interval = setInterval(fetchAttentionData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleDeriveSimulatedDefaults = async (delay: number, weather: string, priority: number) => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/nexus/attention/derive-defaults", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_delay_min: delay, weather, train_priority: priority })
      });
      if (res.ok) {
        const data = await res.json();
        setDefaults(data);
      }
    } catch (err) {
      console.log("Error deriving defaults", err);
    }
  };

  const handleSaveSettings = async (updated: Partial<AttentionSettings>) => {
    const newSt = { ...settings, ...updated };
    setSettings(newSt);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);

    try {
      await fetch("http://127.0.0.1:8000/api/nexus/attention/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSt)
      });
    } catch (err) {
      console.error("Failed to sync attention settings", err);
    }
  };

  const getLoadColor = (state: string) => {
    if (state === "QUIET") return "text-emerald-400 border-emerald-500/30 bg-emerald-950/20";
    if (state === "FOCUSED") return "text-amber-400 border-amber-500/30 bg-amber-950/20";
    return "text-rose-400 border-rose-500/30 bg-rose-950/20";
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-purple-500/10 border border-purple-500/30 rounded-xl text-purple-400">
              <Brain className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                Attention & Focus Management Hub
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-950 border border-purple-500/40 text-purple-300 font-mono">
                  Default Behavior Engine
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Focus Control • Cognitive Review Load Meter (CRLI) • Context Pre-fill Engine • 100% Editable Controls
              </p>
            </div>
          </div>
        </div>

        {/* Cognitive Review Load Index (CRLI) Meter */}
        <div className={`px-4 py-3 rounded-xl border flex items-center space-x-4 ${getLoadColor(crli.load_state)}`}>
          <div className="text-right">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Review Load Index (CRLI)</div>
            <div className="text-2xl font-black font-mono tracking-tight">{crli.crli_score} / 100</div>
          </div>
          <div className="h-10 w-px bg-slate-700/50" />
          <div className="text-xs font-bold px-3 py-1 rounded-lg uppercase tracking-wider bg-slate-900/60 border border-slate-700">
            {crli.load_state} STATE
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab("defaults")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "defaults"
              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Context Pre-fills & Rationale</span>
        </button>

        <button
          onClick={() => setActiveTab("triage")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "triage"
              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>Interruption Triage Streams</span>
        </button>

        <button
          onClick={() => setActiveTab("learning")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "learning"
              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>Dispatcher Learning & Memory</span>
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "settings"
              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Editable Control Thresholds</span>
        </button>
      </div>

      {/* TAB 1: CONTEXT PRE-FILLS & RATIONALE SIMULATOR */}
      {activeTab === "defaults" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Interactive Context Input & Sensible Defaults Panel */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-purple-400" />
                Pre-filled Recovery Defaults (Editable)
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-950/60 text-emerald-400 border border-emerald-500/30 rounded">
                🟢 CONTEXT PRE-FILL ACTIVE
              </span>
            </div>

            {/* Live Context Controls */}
            <div className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800 space-y-3">
              <div className="text-[11px] font-bold text-purple-300 uppercase tracking-wider">
                Simulate Operational Context Input
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">Delay (Min)</label>
                  <input
                    type="number"
                    value={simDelay}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setSimDelay(v);
                      handleDeriveSimulatedDefaults(v, simWeather, simPriority);
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-cyan-300 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Priority</label>
                  <select
                    value={simPriority}
                    onChange={(e) => {
                      const p = Number(e.target.value);
                      setSimPriority(p);
                      handleDeriveSimulatedDefaults(simDelay, simWeather, p);
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-slate-200"
                  >
                    <option value={5}>5 (High Express)</option>
                    <option value={4}>4 (Express)</option>
                    <option value={3}>3 (Passenger)</option>
                    <option value={2}>2 (Freight)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Weather</label>
                  <select
                    value={simWeather}
                    onChange={(e) => {
                      const w = e.target.value;
                      setSimWeather(w);
                      handleDeriveSimulatedDefaults(simDelay, w, simPriority);
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-slate-200"
                  >
                    <option value="standard">Standard</option>
                    <option value="dense_fog">Dense Fog</option>
                    <option value="heavy_rain">Heavy Rain</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Derived Defaults Form */}
            <div className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-400 mb-1 font-medium">Hold Duration (Minutes)</label>
                <input
                  type="number"
                  value={defaults.defaults.hold_duration_min}
                  onChange={(e) =>
                    setDefaults({
                      ...defaults,
                      defaults: { ...defaults.defaults, hold_duration_min: Number(e.target.value) }
                    })
                  }
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-purple-300 font-mono text-sm focus:border-purple-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium font-sans">Recommended Platform Assignment</label>
                <input
                  type="text"
                  value={defaults.defaults.recommended_platform}
                  onChange={(e) =>
                    setDefaults({
                      ...defaults,
                      defaults: { ...defaults.defaults, recommended_platform: e.target.value }
                    })
                  }
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-xs focus:border-purple-500 outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Detour Path Strategy</label>
                <select
                  value={defaults.defaults.detour_route}
                  onChange={(e) =>
                    setDefaults({
                      ...defaults,
                      defaults: { ...defaults.defaults, detour_route: e.target.value }
                    })
                  }
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-xs focus:border-purple-500 outline-none"
                >
                  <option value="MAIN_CORRIDOR">Main Corridor (Standard)</option>
                  <option value="FAST_LINE_BYPASS">Fast-Line Bypass Detour</option>
                  <option value="SLOW_LINE_CROSSOVER">Slow-Line Crossover</option>
                </select>
              </div>
            </div>
          </div>

          {/* Context Rationale Explanation Box */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Context Derivation Rationale
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">Transparent explanation of why these parameters were pre-filled</p>
            </div>

            <div className="space-y-2.5">
              {defaults.rationale.map((item, idx) => (
                <div key={idx} className="flex items-start space-x-2.5 bg-slate-900/80 p-2.5 rounded-lg border border-slate-800/80">
                  <ChevronRight className="w-4 h-4 text-purple-400 mt-0.5 shrink-0" />
                  <span className="text-xs text-slate-300 leading-relaxed">{item}</span>
                </div>
              ))}
            </div>

            {defaults.historical_learning && (
              <div className="p-3 bg-purple-950/20 border border-purple-500/30 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-purple-300 font-bold text-xs">
                  <span>Dispatcher Acceptance Confidence</span>
                  <span className="font-mono text-emerald-400">{defaults.historical_learning.historical_acceptance_rate_pct}% Accepted</span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Based on {defaults.historical_learning.total_decisions_analyzed} historical human dispatcher recovery decisions.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INTERRUPTION TRIAGE */}
      {activeTab === "triage" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-emerald-950/20 border border-emerald-500/30 p-4 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-emerald-400 font-bold text-xs">
                <span>QUIET AUTO-EXECUTE</span>
                <Zap className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-300">Confidence &gt; {settings.auto_approve_confidence_threshold}% with 0 safety hazards</p>
              <div className="text-[10px] text-emerald-400/80 pt-2 flex items-center gap-1">
                <Check className="w-3 h-3" /> Runs in quiet background audit mode
              </div>
            </div>

            <div className="bg-amber-950/20 border border-amber-500/30 p-4 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-amber-400 font-bold text-xs">
                <span>BATCHED REVIEW QUEUE</span>
                <Layers className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-300">Routine advisories bundled every {settings.batch_review_interval_sec}s</p>
              <div className="text-[10px] text-amber-400/80 pt-2 flex items-center gap-1">
                <Layers className="w-3 h-3" /> One-click bulk approval
              </div>
            </div>

            <div className="bg-rose-950/20 border border-rose-500/30 p-4 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-rose-400 font-bold text-xs">
                <span>IMMEDIATE INTERRUPT</span>
                <AlertTriangle className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-300">Safety constraint trip or Out-of-Distribution hazard</p>
              <div className="text-[10px] text-rose-400/80 pt-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Spotlight focus drawer on map
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: DISPATCHER LEARNING & MEMORY */}
      {activeTab === "learning" && (
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="border-b border-slate-800 pb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-purple-400" />
              Dispatcher Default Acceptance & Override Memory
            </h3>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-500/40 px-2.5 py-0.5 rounded">
              83.3% Acceptance Rate
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                <div className="text-slate-400">Accepted AI Defaults</div>
                <div className="text-xl font-bold text-emerald-400 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-emerald-400" /> 10 Recovery Plans
                </div>
              </div>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                <div className="text-slate-400">Human Overridden Defaults</div>
                <div className="text-xl font-bold text-amber-400 flex items-center gap-2">
                  <XCircle className="w-5 h-5 text-amber-400" /> 2 Recovery Plans
                </div>
              </div>
            </div>

            <p className="text-slate-400 leading-relaxed text-[11px] pt-2">
              The Attention Engine continuously records dispatcher edits to default parameters (such as hold times or platform switches) and refines future default confidence bounds accordingly.
            </p>
          </div>
        </div>
      )}

      {/* TAB 4: EDITABLE CONTROL THRESHOLDS */}
      {activeTab === "settings" && (
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-purple-400" />
              Dispatcher Attention Control Panel
            </h3>
            {isSaved && <span className="text-xs text-emerald-400 font-bold animate-pulse">✓ Settings Saved</span>}
          </div>

          <div className="space-y-6 text-xs">
            {/* Auto Approve Threshold Slider */}
            <div className="space-y-2">
              <div className="flex justify-between font-medium">
                <span className="text-slate-300">Auto-Approval Confidence Threshold</span>
                <span className="font-mono text-purple-400 font-bold">{settings.auto_approve_confidence_threshold}%</span>
              </div>
              <input
                type="range"
                min="50"
                max="99"
                value={settings.auto_approve_confidence_threshold}
                onChange={(e) => handleSaveSettings({ auto_approve_confidence_threshold: Number(e.target.value) })}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-400"
              />
              <p className="text-[11px] text-slate-500">AI recovery actions with confidence higher than this limit auto-execute quietly.</p>
            </div>

            {/* Interruption Sensitivity */}
            <div className="space-y-2">
              <span className="text-slate-300 font-medium block">Interruption Sensitivity Profile</span>
              <div className="grid grid-cols-3 gap-3">
                {(["LOW", "BALANCED", "HIGH"] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => handleSaveSettings({ interruption_sensitivity: mode })}
                    className={`py-2 px-3 rounded-lg border font-mono text-xs font-bold transition ${
                      settings.interruption_sensitivity === mode
                        ? "bg-purple-500/20 border-purple-500 text-purple-300"
                        : "bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-800"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            {/* Toggles */}
            <div className="pt-2 grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex items-center space-x-3 p-3 bg-slate-900 border border-slate-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.enable_auto_approval}
                  onChange={(e) => handleSaveSettings({ enable_auto_approval: e.target.checked })}
                  className="rounded accent-purple-400"
                />
                <span className="text-slate-200">Enable Background Auto-Approvals</span>
              </label>

              <label className="flex items-center space-x-3 p-3 bg-slate-900 border border-slate-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.enable_smart_prefill}
                  onChange={(e) => handleSaveSettings({ enable_smart_prefill: e.target.checked })}
                  className="rounded accent-purple-400"
                />
                <span className="text-slate-200">Enable Smart Context Pre-filling</span>
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
