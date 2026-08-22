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
  Edit3
} from "lucide-react";


interface AttentionSettings {
  auto_approve_confidence_threshold: number;
  interruption_sensitivity: "LOW" | "BALANCED" | "HIGH";
  batch_review_interval_sec: number;
  max_batch_size: number;
  crli_overload_threshold: number;
  enable_auto_approval: boolean;
  enable_smart_prefill: boolean;
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
    recommendation: "Normal operations. Full manual review capability active.",
    components: { disruption_load: 12.5, queue_load: 7.0, density_load: 6.0, uncertainty_load: 3.0 }
  });

  const [settings, setSettings] = useState<AttentionSettings>({
    auto_approve_confidence_threshold: 85,
    interruption_sensitivity: "BALANCED",
    batch_review_interval_sec: 30,
    max_batch_size: 5,
    crli_overload_threshold: 75,
    enable_auto_approval: true,
    enable_smart_prefill: true
  });

  const [defaults, setDefaults] = useState<SensibleDefaults>({
    defaults: {
      hold_duration_min: 4,
      recommended_platform: "PF_2",
      detour_route: "MAIN_CORRIDOR",
      target_speed_kmh: 90,
      precedence_swap: true
    },
    is_editable: true,
    rationale: [
      "Hold duration (4m) derived from accumulated delay (12m) and weather state.",
      "Maintaining scheduled Main Corridor path.",
      "Platform PF_2 assigned based on train priority rank (4/5)."
    ],
    derived_from_context: {
      delay_severity: "MODERATE",
      weather_impact: "STANDARD",
      priority_weight: 4.0
    }
  });

  const [isSaved, setIsSaved] = useState(false);
  const [activeTab, setActiveTab] = useState<"defaults" | "triage" | "settings">("defaults");

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
      console.log("Using local mock attention context data", err);
    }
  };

  useEffect(() => {
    fetchAttentionData();
    const interval = setInterval(fetchAttentionData, 5000);
    return () => clearInterval(interval);
  }, []);

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
            <div className="p-2.5 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
              <Brain className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                Attention & Focus Manager
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-950 border border-cyan-500/40 text-cyan-400 font-mono">
                  Default Behavior Engine
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Automated Focus Control • Cognitive Review Load Meter • 100% Editable Context Defaults
              </p>
            </div>
          </div>
        </div>

        {/* Cognitive Review Load Index (CRLI) Meter */}
        <div className={`px-4 py-3 rounded-xl border flex items-center space-x-4 ${getLoadColor(crli.load_state)}`}>
          <div className="text-right">
            <div className="text-xs font-mono uppercase tracking-wider text-slate-400">Cognitive Load Index (CRLI)</div>
            <div className="text-2xl font-black font-mono tracking-tight">{crli.crli_score} / 100</div>
          </div>
          <div className="h-10 w-px bg-slate-700/50" />
          <div className="text-xs font-bold px-3 py-1 rounded-lg uppercase tracking-wider bg-slate-900/60 border border-slate-700">
            {crli.load_state} STATE
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab("defaults")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "defaults"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Context Defaults & Rationale</span>
        </button>

        <button
          onClick={() => setActiveTab("triage")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "triage"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>Interruption Triage & Batch Queue</span>
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === "settings"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:bg-slate-800"
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Editable Thresholds Control</span>
        </button>
      </div>

      {/* TAB 1: CONTEXT DEFAULTS & RATIONALE */}
      {activeTab === "defaults" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Derived Sensible Defaults Form (Editable) */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-cyan-400" />
                Pre-filled Action Defaults (Editable)
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-950/60 text-emerald-400 border border-emerald-500/30 rounded">
                🟢 SMART CONTEXT PRE-FILL ACTIVE
              </span>
            </div>

            <div className="space-y-4 text-xs">
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
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-cyan-300 font-mono text-sm focus:border-cyan-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Recommended Platform Assignment</label>
                <select
                  value={defaults.defaults.recommended_platform}
                  onChange={(e) =>
                    setDefaults({
                      ...defaults,
                      defaults: { ...defaults.defaults, recommended_platform: e.target.value }
                    })
                  }
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm focus:border-cyan-500 outline-none"
                >
                  <option value="PF_1">Platform 1 (Local Line)</option>
                  <option value="PF_2">Platform 2 (Express Corridor)</option>
                  <option value="PF_3">Platform 3 (Fast Loop)</option>
                  <option value="PF_4">Platform 4 (Freight Yard)</option>
                </select>
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
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm focus:border-cyan-500 outline-none"
                >
                  <option value="MAIN_CORRIDOR">Main Corridor (Standard)</option>
                  <option value="FAST_LINE_BYPASS">Fast-Line Bypass Detour</option>
                  <option value="SLOW_LINE_SWITCH">Slow-Line Crossover</option>
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
              <p className="text-[11px] text-slate-400 mt-0.5">Why these parameters were automatically selected as defaults</p>
            </div>

            <div className="space-y-2.5">
              {defaults.rationale.map((item, idx) => (
                <div key={idx} className="flex items-start space-x-2.5 bg-slate-900/80 p-2.5 rounded-lg border border-slate-800/80">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <span className="text-xs text-slate-300 leading-relaxed">{item}</span>
                </div>
              ))}
            </div>

            <div className="pt-2 flex items-center justify-between text-[11px] font-mono text-slate-400 bg-slate-900/40 p-2.5 rounded-lg border border-slate-800">
              <span>Severity: <strong className="text-amber-400">{defaults.derived_from_context.delay_severity}</strong></span>
              <span>Weather: <strong className="text-cyan-400">{defaults.derived_from_context.weather_impact}</strong></span>
              <span>Priority: <strong className="text-emerald-400">{defaults.derived_from_context.priority_weight}/5</strong></span>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: INTERRUPTION TRIAGE */}
      {activeTab === "triage" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-emerald-950/20 border border-emerald-500/30 p-4 rounded-xl space-y-1">
              <div className="flex items-center justify-between text-emerald-400 font-bold text-xs">
                <span>QUIET AUTO-EXECUTE</span>
                <Zap className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-300">Confidence &gt; {settings.auto_approve_confidence_threshold}% with 0 safety hazards</p>
              <div className="text-[10px] text-emerald-400/80 pt-2">Quiet background audit logging</div>
            </div>

            <div className="bg-amber-950/20 border border-amber-500/30 p-4 rounded-xl space-y-1">
              <div className="flex items-center justify-between text-amber-400 font-bold text-xs">
                <span>BATCHED REVIEW QUEUE</span>
                <Layers className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-300">Routine advisories bundled every {settings.batch_review_interval_sec}s</p>
              <div className="text-[10px] text-amber-400/80 pt-2">Reduces notification interruption fatigue</div>
            </div>

            <div className="bg-rose-950/20 border border-rose-500/30 p-4 rounded-xl space-y-1">
              <div className="flex items-center justify-between text-rose-400 font-bold text-xs">
                <span>IMMEDIATE INTERRUPT</span>
                <AlertTriangle className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-300">Safety constraint trip or Out-of-Distribution hazard</p>
              <div className="text-[10px] text-rose-400/80 pt-2">Spotlight focus drawer on map</div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: EDITABLE THRESHOLDS CONTROL */}
      {activeTab === "settings" && (
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-cyan-400" />
              Dispatcher Attention Control Panel
            </h3>
            {isSaved && <span className="text-xs text-emerald-400 font-bold animate-pulse">✓ Settings Saved</span>}
          </div>

          <div className="space-y-6 text-xs">
            {/* Auto Approve Threshold Slider */}
            <div className="space-y-2">
              <div className="flex justify-between font-medium">
                <span className="text-slate-300">Auto-Approval Confidence Threshold</span>
                <span className="font-mono text-cyan-400 font-bold">{settings.auto_approve_confidence_threshold}%</span>
              </div>
              <input
                type="range"
                min="60"
                max="98"
                value={settings.auto_approve_confidence_threshold}
                onChange={(e) => handleSaveSettings({ auto_approve_confidence_threshold: Number(e.target.value) })}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
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
                        ? "bg-cyan-500/20 border-cyan-500 text-cyan-300"
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
                  className="rounded accent-cyan-400"
                />
                <span className="text-slate-200">Enable Background Auto-Approvals</span>
              </label>

              <label className="flex items-center space-x-3 p-3 bg-slate-900 border border-slate-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.enable_smart_prefill}
                  onChange={(e) => handleSaveSettings({ enable_smart_prefill: e.target.checked })}
                  className="rounded accent-cyan-400"
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
