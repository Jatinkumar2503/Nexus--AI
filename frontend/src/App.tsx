import { lazy, Suspense, useCallback, useState, useEffect } from 'react';
import { 
  Shield, 
  Activity, 
  Play, 
  Pause, 
  RotateCcw, 
  Train, 
  AlertCircle, 
  CheckCircle, 
  X, 
  Radio, 
  Sliders, 
  AlertTriangle 
  ,History
} from 'lucide-react';
import { 
  api, 
  setDispatcherToken,
  type TrainState, 
  type StationState, 
  type Disruption, 
  type SimulationMetrics, 
  type ScenarioOption,
  type PlanRecord,
  type PlannerStatus
} from './services/api';
import { audioService } from './services/audio';
import './App.css';

import { NexusNeuralPanel } from './components/NexusNeuralPanel';
import { LiveTrainingMonitor } from './components/LiveTrainingMonitor';
import { AttentionManagementHub } from './components/AttentionManagementHub';


const RailMap = lazy(() => import('./components/RailMap').then(({ RailMap: Component }) => ({ default: Component })));

const getTrainStops = (_trainId: string, serviceType: string, direction: string) => {
  let stops = ["MUM", "TNA", "VIR", "BOI", "VAP", "BIL", "SUR", "BHA", "VAD", "ANA", "ADI", "SAB"];
  if (serviceType === "Vande Bharat") {
    stops = ["MUM", "TNA", "SUR", "VAD", "ADI", "SAB"];
  } else if (serviceType === "Tejas Express") {
    stops = ["MUM", "TNA", "VAP", "SUR", "VAD", "ANA", "ADI", "SAB"];
  }
  return direction === "inbound" ? [...stops].reverse() : stops;
};

const normalizeStrat = (s: string) => s === "reroute" || s === "reroute_and_prioritize" ? "detour" : s;

function App() {
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [simSpeed, setSimSpeed] = useState<number>(30.0);
  const [simTime, setSimTime] = useState<string>("10:00:00");
  const [trains, setTrains] = useState<TrainState[]>([]);
  const [stations, setStations] = useState<StationState[]>([]);
  const [activeDisruptions, setActiveDisruptions] = useState<Disruption[]>([]);
  const [metrics, setMetrics] = useState<SimulationMetrics>({
    total_passenger_delay_minutes: 0,
    total_energy_kwh: 0,
    crew_violation_count: 0,
    resilience_score: 100
  });
  const [negotiationLogs, setNegotiationLogs] = useState<string[]>([]);
  
  // Scenario states
  const [scenarios, setScenarios] = useState<ScenarioOption[]>([]);
  const [loadingScenarios, setLoadingScenarios] = useState<boolean>(false);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [committedStrategy, setCommittedStrategy] = useState<string | null>(null);
  const [commitSuccessNotification, setCommitSuccessNotification] = useState<{
    strategyName: string;
    cosmosCmd: string;
    time: string;
  } | null>(null);
  const [replayLoading, setReplayLoading] = useState<boolean>(false);
  const [whyNotMessage, setWhyNotMessage] = useState<Record<string, string>>({});
  const [decisionEvidence, setDecisionEvidence] = useState<Record<string, { rationale: string; tradeoffs: string[]; fallback: string; score: number }>>({});
  const [lifecyclePlan, setLifecyclePlan] = useState<PlanRecord | null>(null);
  const [replaySpeed, setReplaySpeed] = useState<number>(1);
  const [replayPaused, setReplayPaused] = useState<boolean>(false);
  const [replayActive, setReplayActive] = useState<boolean>(false);
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [replayEvents, setReplayEvents] = useState<Array<{ stage: string; message: string; timestamp: string }>>([]);
  const [plannerStatus, setPlannerStatus] = useState<PlannerStatus | null>(null);
  const [plannerConnected, setPlannerConnected] = useState(false);
  const [operationalError, setOperationalError] = useState<string | null>(null);
  const [memoryOutcomes, setMemoryOutcomes] = useState<Array<{ strategy?: string; simulation_time?: string }>>([]);
  const [mapReady, setMapReady] = useState(false);
  const [dispatcherToken, setDispatcherTokenValue] = useState('');
  const [dispatcherAccessEnabled, setDispatcherAccessEnabled] = useState(false);

  const reportError = useCallback((message: string, error: unknown) => {
    console.error(message, error);
    setOperationalError(message);
  }, []);

  const enableDispatcherAccess = () => {
    setDispatcherToken(dispatcherToken);
    setDispatcherAccessEnabled(Boolean(dispatcherToken.trim()));
  };

  // Disruption Injection Dialog state
  const [selectedStation, setSelectedStation] = useState<string | null>(null);
  const [selectedTrack, setSelectedTrack] = useState<{ fromNode: string; toNode: string } | null>(null);
  const [disruptionDuration, setDisruptionDuration] = useState<number>(60);
  const [disruptionDesc, setDisruptionDesc] = useState<string>("Track circuit signal failure");
  const [showInjectModal, setShowInjectModal] = useState<boolean>(false);

  // UI Tabs for Sidebar
  const [activeTab, setActiveTab] = useState<"trains" | "stations" | "logs" | "ai_dispatch" | "live_training" | "attention_hub">("attention_hub");

  const [selectedTrainId, setSelectedTrainId] = useState<string | null>(null);

  // Adaptive UI state
  const [uiFocusMode, setUiFocusMode] = useState<"cockpit" | "crisis">("cockpit");

  // Fetch complete simulation state
  const fetchSimState = useCallback(async () => {
    try {
      const state = await api.getSimulationState();
      setTrains(state.trains);
      setStations(state.stations);
      setActiveDisruptions(state.active_disruptions);
      setMetrics(state.metrics);
      setNegotiationLogs(state.negotiation_logs);
      setSimTime(state.simulation_time);
    } catch (err) {
      reportError("Live simulation connection failed. Retrying…", err);
    }
  }, [reportError]);

  const fetchScenarios = useCallback(async () => {
    setLoadingScenarios(true);
    try {
      const response = await api.compareScenarios();
      setScenarios(response.scenarios);
    } catch (err) {
      reportError("Scenario comparison failed.", err);
    } finally {
      setLoadingScenarios(false);
    }
  }, [reportError]);

  useEffect(() => {
    const timer = window.setTimeout(() => setMapReady(true), 250);
    return () => window.clearTimeout(timer);
  }, []);

  // Poll simulator state
  useEffect(() => {
    let interval: any;
    
    // Initial fetch
    fetchSimState();

    if (isPlaying) {
      interval = setInterval(fetchSimState, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchSimState, isPlaying, simSpeed]);

  useEffect(() => {
    const source = api.subscribePlannerEvents((event) => {
      setNegotiationLogs((logs) => [...logs, `[${event.stage.toUpperCase()}] ${event.message}`].slice(-200));
    });
    source.onopen = () => { setPlannerConnected(true); setOperationalError(null); };
    source.onerror = () => { setPlannerConnected(false); setOperationalError("Planner stream reconnecting…"); };
    return () => source.close();
  }, []);

  useEffect(() => {
    api.getRecoveryPreferences().then(({ preferences }) => {
      if (typeof preferences.simulation_speed === "number") setSimSpeed(preferences.simulation_speed);
      if (typeof preferences.replay_speed === "number") setReplaySpeed(preferences.replay_speed);
    }).catch(() => undefined);
  }, []);

  useEffect(() => { api.getPlannerStatus().then(setPlannerStatus).catch(() => undefined); }, []);
  useEffect(() => { api.getRecoveryMemory().then(({ outcomes }) => setMemoryOutcomes(outcomes)).catch((error) => reportError("Recovery memory is unavailable.", error)); }, [reportError]);

  useEffect(() => {
    if (!replayActive || replayPaused) return;
    if (replayIndex >= replayEvents.length) {
      setReplayActive(false);
      return;
    }

    const event = replayEvents[replayIndex];
    const timer = window.setTimeout(() => {
      setNegotiationLogs(logs => [...logs, `[REPLAY ${event.timestamp}] ${event.stage.toUpperCase()}: ${event.message}`]);
      setReplayIndex(index => index + 1);
    }, 450 / replaySpeed);
    return () => window.clearTimeout(timer);
  }, [replayActive, replayEvents, replayIndex, replayPaused, replaySpeed]);

  // If a disruption gets injected, fetch scenarios if not loaded yet
  useEffect(() => {
    if (activeDisruptions.length > 0) {
      if (scenarios.length === 0 && !loadingScenarios) {
        fetchScenarios();
        audioService.playWarning();
      }
    } else if (activeDisruptions.length === 0 && scenarios.length > 0) {
      // Clear scenarios if disruption resolved
      setScenarios([]);
      setSelectedStrategy(null);
      setCommittedStrategy(null);
    }
  }, [activeDisruptions, fetchScenarios, loadingScenarios, scenarios.length]);

  // Control action handlings
  const handlePlayPause = async () => {
    audioService.playClick();
    const nextPlay = !isPlaying;
    setIsPlaying(nextPlay);
    await api.controlSimulation(nextPlay ? "play" : "pause", simSpeed);
  };

  const handleSpeedChange = async (newSpeed: number) => {
    audioService.playClick();
    setSimSpeed(newSpeed);
    if (isPlaying) {
      await api.controlSimulation("play", newSpeed);
    }
    await api.setRecoveryPreferences({ simulation_speed: newSpeed, replay_speed: replaySpeed });
  };

  const handleReset = async () => {
    audioService.playClick();
    setIsPlaying(false);
    await api.controlSimulation("reset");
    setScenarios([]);
    setSelectedStrategy(null);
    setCommittedStrategy(null);
    setCommitSuccessNotification(null);
    setSelectedStation(null);
    setSelectedTrack(null);
    setShowInjectModal(false);
    // Fetch initial state
    setTimeout(fetchSimState, 200);
  };

  const handleReplayTimeline = async () => {
    setReplayPaused(false);
    setReplayLoading(true);
    try {
      const timeline = await api.getReplayTimeline();
      setNegotiationLogs([]);
      setActiveTab("logs");
      setReplayEvents(timeline.events);
      setReplayIndex(0);
      setReplayActive(timeline.events.length > 0);
    } catch (err) {
      reportError("Replay timeline could not be loaded.", err);
    } finally {
      setReplayLoading(false);
    }
  };

  const handleReplaySeek = (index: number) => {
    const boundedIndex = Math.max(0, Math.min(index, replayEvents.length));
    setReplayActive(boundedIndex < replayEvents.length);
    setReplayPaused(true);
    setReplayIndex(boundedIndex);
    setNegotiationLogs(replayEvents.slice(0, boundedIndex).map(event =>
      `[REPLAY ${event.timestamp}] ${event.stage.toUpperCase()}: ${event.message}`
    ));
  };

  const handleInjectDisruption = async () => {
    try {
      // Auto pause simulation on inject to allow dispatcher decision
      setIsPlaying(false);
      await api.controlSimulation("pause");

      await api.injectDisruption(
        selectedStation,
        selectedTrack ? `${selectedTrack.fromNode}->${selectedTrack.toNode}` : null,
        disruptionDuration,
        disruptionDesc
      );
      
      setShowInjectModal(false);
      // Re-fetch state
      await fetchSimState();
    } catch (err) {
      reportError("Unable to inject disruption.", err);
    }
  };

  const handleResolveScenario = async (strategyId: string) => {
    try {
      const target = normalizeStrat(strategyId);
      audioService.playSuccess();
      setSelectedStrategy(strategyId);
      setCommittedStrategy(target);

      if (lifecyclePlan && lifecyclePlan.id) {
        if (lifecyclePlan.status === "proposed") {
          await api.validateLifecyclePlan(lifecyclePlan.id);
        }
        if (lifecyclePlan.status !== "approved" && lifecyclePlan.status !== "committed") {
          await api.approveLifecyclePlan(lifecyclePlan.id);
        }
        const committed = await api.commitLifecyclePlan(lifecyclePlan.id);
        setLifecyclePlan(committed);
      } else {
        await api.approveScenario(target);
        await api.resolveScenario(target);
      }

      // Re-fetch Recovery Memory immediately
      try {
        const { outcomes } = await api.getRecoveryMemory();
        setMemoryOutcomes(outcomes);
      } catch {
        setMemoryOutcomes(prev => [...prev, { strategy: target, simulation_time: simTime }]);
      }

      // Find strategy human readable name
      const matchedScenario = scenarios.find(s => s.id === strategyId || normalizeStrat(s.id) === target);
      const stratName = matchedScenario ? matchedScenario.name : target.toUpperCase();

      // Build COSMOS command for notification display
      const edgeId = activeDisruptions[0]?.edge_id;
      const nodeId = activeDisruptions[0]?.node_id || (edgeId ? edgeId.split("->")[0] : "VAD");
      let cosmosCmd = `CMD/${target.toUpperCase()}/TR-VB-20901/${nodeId}`;
      if (target === "detour") cosmosCmd = `CMD/ROUTE/TR-VB-20901/${edgeId || "VAD_SLOW->AMA_SLOW"}/DETOUR`;
      else if (target === "short_turn") cosmosCmd = `CMD/TURN/TR-VB-20901/${nodeId}/SHORT_TURN`;
      else if (target === "do_nothing") cosmosCmd = `CMD/HOLD/TR-VB-20901/${nodeId}`;

      setCommitSuccessNotification({
        strategyName: stratName,
        cosmosCmd: cosmosCmd,
        time: simTime
      });

      // Collapse and close the disruption resolution drawer immediately
      setScenarios([]);
      setActiveDisruptions([]);

      // Resume simulation running
      setIsPlaying(true);
      await api.controlSimulation("play", simSpeed);
      setTimeout(fetchSimState, 300);
    } catch (err) {
      reportError("Plan commit could not be completed.", err);
    }
  };

  const handleGeneratePlan = async () => {
    if (!activeDisruptions[0]) return;
    try {
      const proposed = await api.createLifecyclePlan({ disruption: activeDisruptions[0], trains, stations });
      const validated = await api.validateLifecyclePlan(proposed.id);
      if (validated.status !== "validated") throw new Error("Planner recommendation did not pass validation.");
      setLifecyclePlan(validated);
      setSelectedStrategy(validated.plan.recommended_strategy);
    } catch (err) { reportError("Planner could not prepare a lifecycle plan.", err); }
  };

  const handleApprovePlan = async () => {
    if (!lifecyclePlan || lifecyclePlan.status !== "validated") return;
    try { setLifecyclePlan(await api.approveLifecyclePlan(lifecyclePlan.id)); } catch (err) { reportError("Dispatcher approval failed.", err); }
  };

  // Callbacks from map click events
  const handleMapStationSelect = (stationId: string) => {
    setSelectedStation(stationId);
    setSelectedTrack(null);
    setDisruptionDesc(`Signal and Interlocking failure at station platform ${stationId}`);
    setShowInjectModal(true);
  };

  const handleMapTrackSelect = (fromNode: string, toNode: string) => {
    setSelectedTrack({ fromNode, toNode });
    setSelectedStation(null);
    setDisruptionDesc(`Track circuit fault or blockage between ${fromNode} and ${toNode}`);
    setShowInjectModal(true);
  };

  const hasActiveDisruption = activeDisruptions.length > 0;
  const activeTrainsCount = trains.filter(t => t.status === "RUNNING" || t.status === "DWELLING").length;

  return (
    <div className="flex flex-col h-screen w-screen bg-background text-zinc-100 overflow-hidden font-sans">
      {/* Premium Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-black/40 backdrop-blur-md z-10">
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 border border-primary/30 shadow-glow">
            <Activity className="w-5 h-5 text-primary animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wider bg-gradient-to-r from-white via-zinc-200 to-zinc-500 bg-clip-text text-transparent">
              NEXUS
            </h1>
            <p className="text-[10px] text-zinc-500 tracking-widest uppercase font-semibold">
              Multi-Agent Rail Operations Simulator
            </p>
          </div>
        </div>

        {/* Live Simulation Clock & Speed Controls */}
        <div className="flex items-center space-x-6">
          {/* Speed settings */}
          <div className="flex items-center space-x-2 bg-zinc-900/60 border border-border px-3 py-1 rounded-full">
            <Sliders className="w-3.5 h-3.5 text-zinc-500" />
            <select 
              value={simSpeed}
              onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
              className="text-xs bg-transparent border-none text-zinc-300 focus:outline-none cursor-pointer"
            >
              <option value="1.0" className="bg-zinc-950">1x (Real-time)</option>
              <option value="10.0" className="bg-zinc-950">10x Speed</option>
              <option value="30.0" className="bg-zinc-950">30x Speed</option>
              <option value="60.0" className="bg-zinc-950">60x Speed</option>
            </select>
          </div>

          {/* Clock controls */}
          <div className="flex items-center space-x-3 bg-zinc-900/60 border border-border px-4 py-1.5 rounded-full backdrop-blur-sm">
            <button 
              onClick={handlePlayPause} 
              className="text-zinc-400 hover:text-white transition-colors"
              title={isPlaying ? "Pause Simulation" : "Start Simulation"}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 text-accent" />}
            </button>
            
            <button 
              onClick={handleReset} 
              className="text-zinc-400 hover:text-white transition-colors"
              title="Reset Simulation"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button onClick={handleReplayTimeline} className="text-zinc-400 hover:text-primary transition-colors" title="Load Recovery Replay Timeline">
              <History className={`w-4 h-4 ${replayLoading ? "animate-pulse" : ""}`} />
            </button>
            {replayActive && <button onClick={() => setReplayPaused(paused => !paused)} className="text-zinc-400 hover:text-warning text-[9px]">{replayPaused ? "RESUME REPLAY" : "PAUSE REPLAY"}</button>}
            {replayActive && <button onClick={() => { setReplayActive(false); setReplayPaused(false); setReplayIndex(0); }} className="text-zinc-400 hover:text-warning text-[9px]">STOP REPLAY</button>}
            <select value={replaySpeed} onChange={(event) => { const speed = Number(event.target.value); setReplaySpeed(speed); api.setRecoveryPreferences({ simulation_speed: simSpeed, replay_speed: speed }); }} className="bg-transparent text-[9px] text-zinc-400"><option value="0.5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select>

            {replayEvents.length > 0 && <label className="flex items-center gap-1 text-[9px] text-zinc-500" title="Seek through replay events"><span>REPLAY {replayIndex}/{replayEvents.length}</span><input aria-label="Replay position" type="range" min="0" max={replayEvents.length} value={replayIndex} onChange={(event) => handleReplaySeek(Number(event.target.value))} className="w-20 accent-primary" /></label>}
            <span className="text-zinc-700">|</span>
            <div className="text-sm font-mono tracking-widest text-zinc-300">
              TIME: <span className="text-primary font-bold">{simTime}</span>
            </div>
          </div>

          {/* Adaptive UI Focus Toggle */}
          <div className="flex items-center space-x-1 bg-zinc-950 border border-zinc-800 p-0.5 rounded-full">
            <button
              onClick={() => { audioService.playClick(); setUiFocusMode("cockpit"); }}
              className={`px-2.5 py-1 rounded-full text-[9px] font-bold tracking-wide transition-all duration-200 cursor-pointer ${
                uiFocusMode === "cockpit" 
                  ? "bg-primary/20 text-primary border border-primary/30" 
                  : "text-zinc-500 hover:text-zinc-300 border border-transparent"
              }`}
              title="Cockpit Full View: Displays network map, real-time timetable, station platform load, and all charts."
            >
              COCKPIT VIEW
            </button>
            <button
              onClick={() => { audioService.playClick(); setUiFocusMode("crisis"); }}
              className={`px-2.5 py-1 rounded-full text-[9px] font-extrabold tracking-wide transition-all duration-200 cursor-pointer ${
                uiFocusMode === "crisis" 
                  ? "bg-danger/25 text-danger border border-danger/30 animate-pulse" 
                  : "text-zinc-500 hover:text-zinc-300 border border-transparent"
              }`}
              title="Crisis Advisory Focus: Collapses secondary views to prioritize agent recommendations."
            >
              CRISIS FOCUS
            </button>
          </div>

          {/* Status Indicator */}
          <div className="flex items-center space-x-2">
            <span className={`relative flex h-2.5 w-2.5`}>
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                !hasActiveDisruption ? "bg-accent" : "bg-danger"
              }`}></span>
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                !hasActiveDisruption ? "bg-accent" : "bg-danger"
              }`}></span>
            </span>
            <span className={`text-xs font-semibold tracking-wider ${
              !hasActiveDisruption ? "text-accent" : "text-danger"
            }`}>
              {!hasActiveDisruption ? "SYSTEM NORMAL" : "DISRUPTION DETECTED"}
            </span>
            {plannerStatus && <span className="text-[9px] font-bold px-2 py-1 rounded border text-accent border-accent/40 bg-accent/10">
              {plannerStatus.mode === "enhanced" ? "OPENAI ENHANCED" : plannerStatus.mode === "auto" && plannerStatus.enhanced_available ? "AI AUTO READY" : "LOCAL RULE ENGINE"}
            </span>}
            <span className={`text-[9px] font-bold ${plannerConnected ? 'text-accent' : 'text-zinc-500'}`}>{plannerConnected ? 'LIVE EVENT STREAM CONNECTED' : 'EVENT STREAM RECONNECTING'}</span>
            <button type="button" onClick={() => setShowInjectModal(true)} className="rounded border border-danger/40 bg-danger/10 px-2 py-1 text-[9px] font-bold text-danger hover:text-white">INJECT INCIDENT</button>
            <label className="sr-only" htmlFor="dispatcher-token">Dispatcher token</label>
            <input id="dispatcher-token" type="password" value={dispatcherToken} onChange={(event) => setDispatcherTokenValue(event.target.value)} placeholder="Dispatcher token" className="w-28 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[9px] text-zinc-200 placeholder:text-zinc-600" />
            <button type="button" onClick={enableDispatcherAccess} className={`rounded border px-2 py-1 text-[9px] font-bold ${dispatcherAccessEnabled ? 'border-accent/40 bg-accent/10 text-accent' : 'border-zinc-700 text-zinc-400 hover:text-zinc-200'}`} title="Authorizes protected dispatcher actions for this browser session only">{dispatcherAccessEnabled ? 'DISPATCHER READY' : 'UNLOCK ACTIONS'}</button>
          </div>
        </div>
      </header>
      {operationalError && <button onClick={() => setOperationalError(null)} className="absolute top-16 z-50 left-1/2 -translate-x-1/2 rounded border border-warning/50 bg-zinc-950 px-3 py-2 text-xs text-warning shadow-lg">{operationalError} <span className="ml-2 text-zinc-400">DISMISS</span></button>}

      {/* Pop-up Notification Modal on Strategy Commitment */}
      {commitSuccessNotification && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 animate-fade-in max-w-md w-[90%]">
          <div className="glass-panel border-2 border-accent/60 bg-zinc-950/95 backdrop-blur-xl p-4 rounded-2xl shadow-glass shadow-accent/20 flex flex-col space-y-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-accent/20 rounded-xl border border-accent/40 text-accent">
                  <CheckCircle className="w-6 h-6 animate-pulse" />
                </div>
                <div>
                  <h4 className="text-xs font-black text-white tracking-wider uppercase">
                    Strategy Committed & Dispatched
                  </h4>
                  <p className="text-xs text-accent font-bold mt-0.5">
                    {commitSuccessNotification.strategyName}
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setCommitSuccessNotification(null)}
                className="text-zinc-500 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="bg-zinc-900/90 border border-zinc-800 p-2.5 rounded-xl font-mono text-[10px] space-y-1">
              <div className="flex items-center justify-between text-zinc-400">
                <span>COSMOS DISPATCH COMMAND:</span>
                <span className="text-zinc-500">{commitSuccessNotification.time}</span>
              </div>
              <div className="text-accent font-bold text-xs">
                {commitSuccessNotification.cosmosCmd}
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[9px] text-zinc-400 font-medium flex items-center gap-1.5">
                <span className="inline-block w-2 h-2 rounded-full bg-accent animate-ping"></span>
                Outcome recorded in Recovery Memory · Simulation Resumed
              </span>
              <button
                onClick={() => setCommitSuccessNotification(null)}
                className="px-3 py-1 bg-accent hover:bg-accent/80 text-zinc-950 text-[10px] font-extrabold rounded-lg transition-all cursor-pointer uppercase tracking-wider"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Structural Layout */}
      <main className="flex flex-col lg:flex-row flex-1 overflow-hidden relative">
        
        {/* Left Side: Rail Network Visualization Map */}
        <section className="flex-1 h-[55%] lg:h-full relative border-b lg:border-b-0 lg:border-r border-border bg-zinc-950/20">
          {committedStrategy && (
            <div className="absolute top-4 left-4 z-10 flex items-center space-x-3 bg-zinc-950/90 border-2 border-accent/60 p-3 rounded-2xl shadow-glass backdrop-blur-md animate-fade-in max-w-sm">
              <div className="p-2 bg-accent/20 rounded-xl text-accent border border-accent/40">
                <Activity className="w-5 h-5 animate-spin text-accent" />
              </div>
              <div className="flex-1">
                <div className="flex items-center space-x-2">
                  <span className="text-[9px] font-black uppercase text-accent tracking-widest">LIVE RECOVERY EXECUTION</span>
                  <span className="text-[8px] bg-accent text-zinc-950 px-1.5 py-0.5 font-extrabold rounded">ACTIVE</span>
                </div>
                <p className="text-xs font-bold text-white mt-0.5">
                  {committedStrategy === "detour" ? "Detour Rerouting via Western Slow Corridor" : committedStrategy === "short_turn" ? "Short-Turning & Bus Bridge Active" : "Naive Strategy Active"}
                </p>
                <p className="text-[9px] text-zinc-400 font-mono mt-0.5">
                  COSMOS Control: Train positions updating in real-time
                </p>
              </div>
              <button
                onClick={() => setCommittedStrategy(null)}
                className="text-zinc-500 hover:text-white p-1 rounded-lg text-xs font-bold"
                title="Dismiss Execution Status"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {mapReady ? (
            <Suspense fallback={<div className="w-full h-full grid place-items-center text-xs font-semibold tracking-wide text-zinc-500">LOADING CORRIDOR MAP…</div>}>
              <RailMap
                trains={trains}
                activeDisruptions={activeDisruptions}
                onStationSelect={handleMapStationSelect}
                onTrackSelect={handleMapTrackSelect}
              />
            </Suspense>
          ) : <div className="w-full h-full grid place-items-center text-xs font-semibold tracking-wide text-zinc-500">PREPARING CORRIDOR MAP…</div>}
        </section>

        <aside className={`transition-all duration-300 ${
          uiFocusMode === "crisis" 
            ? "hidden" 
            : "w-full lg:w-96 h-[45%] lg:h-full flex flex-col bg-zinc-950/45 backdrop-blur-lg border-t lg:border-t-0 lg:border-l border-zinc-900 overflow-hidden"
        }`}>
          
          {/* KPI Dashboard section */}
          <div className="p-5 border-b border-border/40 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold tracking-widest text-zinc-500 uppercase">
                Corridor Safety Cockpit
              </h3>
              {selectedStrategy && (
                <span className="text-[10px] bg-accent/15 border border-accent/30 text-accent font-semibold px-2 py-0.5 rounded">
                  {selectedStrategy.toUpperCase()} ACTIVE
                </span>
              )}
            </div>
            <div className="text-[10px] text-zinc-500">RECOVERY MEMORY: <span className="text-zinc-300 font-bold">{memoryOutcomes.length}</span> committed outcomes</div>

            {/* Global ORS Resilience Score Card */}
            <div className="glass-panel p-5 rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-transparent flex items-center justify-between relative overflow-hidden">
              <div className="space-y-1 z-10">
                <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
                  Network Resilience (ORS)
                </span>
                <div className="text-3xl font-black text-white tracking-tight">
                  {metrics.resilience_score.toFixed(1)}%
                </div>
                <div className="text-[9px] text-zinc-500 font-medium">
                  Weighed on delay, energy, and crew duty limits.
                </div>
              </div>
              <div className={`text-4xl font-extrabold z-10 ${
                metrics.resilience_score > 90 ? "text-accent" : 
                metrics.resilience_score > 70 ? "text-warning" : "text-danger"
              }`}>
                {metrics.resilience_score > 90 ? "A" : metrics.resilience_score > 70 ? "B" : "C"}
              </div>
              <div className="absolute right-0 bottom-0 opacity-5 -mr-4 -mb-4">
                <Shield className="w-32 h-32 text-primary" />
              </div>
            </div>

            {/* Other three dimensional metrics */}
            <div className="grid grid-cols-3 gap-2.5">
              <div className="glass-panel p-3 rounded-xl flex flex-col justify-between h-20 border border-zinc-800">
                <span className="text-[9px] text-zinc-500 font-bold uppercase">Delay Min</span>
                <span className="text-lg font-bold text-warning font-mono">{metrics.total_passenger_delay_minutes}</span>
              </div>
              <div className="glass-panel p-3 rounded-xl flex flex-col justify-between h-20 border border-zinc-800">
                <span className="text-[9px] text-zinc-500 font-bold uppercase">Energy kWh</span>
                <span className="text-lg font-bold text-primary font-mono">{metrics.total_energy_kwh}</span>
              </div>
              <div className="glass-panel p-3 rounded-xl flex flex-col justify-between h-20 border border-zinc-800">
                <span className="text-[9px] text-zinc-500 font-bold uppercase">Crew Viols</span>
                <span className={`text-lg font-bold font-mono ${metrics.crew_violation_count > 0 ? "text-danger" : "text-zinc-400"}`}>
                  {metrics.crew_violation_count}
                </span>
              </div>
            </div>
          </div>

          {/* Sidebar Tabs Controls */}
          <div className="flex border-b border-border/40 text-[11px] overflow-x-auto">
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("attention_hub"); }}
              className={`flex-1 min-w-[95px] py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "attention_hub" ? "border-purple-400 text-purple-300 bg-purple-500/10 shadow-sm" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              🧠 Attention Hub
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("live_training"); }}
              className={`flex-1 min-w-[90px] py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "live_training" ? "border-emerald-400 text-emerald-300 bg-emerald-500/10 shadow-sm" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              🔥 Live Training
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("ai_dispatch"); }}
              className={`flex-1 min-w-[85px] py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "ai_dispatch" ? "border-cyan-400 text-cyan-300 bg-cyan-500/10 shadow-sm" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              ⚡ AI Model
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("trains"); }}
              className={`flex-1 min-w-[70px] py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "trains" ? "border-primary text-white bg-primary/5" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Trains ({activeTrainsCount}/{trains.length})
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("stations"); }}
              className={`flex-1 min-w-[65px] py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "stations" ? "border-primary text-white bg-primary/5" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Stations
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("logs"); }}
              className={`flex-1 min-w-[65px] py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "logs" ? "border-primary text-white bg-primary/5" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Logs ({negotiationLogs.length})
            </button>
          </div>

          {/* Tab Content Panel */}
          <div className="flex-1 overflow-y-auto p-4">
            
            {/* Tab: Attention & Default Behavior Hub */}
            {activeTab === "attention_hub" && (
              <AttentionManagementHub />
            )}

            
            {/* Tab 1: Live Train Fleet */}
            {activeTab === "trains" && (
              <div className="space-y-2">
                {activeTrainsCount === 0 && trains.length > 0 && (
                  <div className="p-3.5 bg-zinc-900/90 border border-zinc-800 rounded-xl text-[10px] space-y-2.5 shadow-glass">
                    <div className="flex items-center justify-between text-zinc-300 font-bold">
                      <span className="flex items-center space-x-1.5 text-accent">
                        <CheckCircle className="w-3.5 h-3.5 text-accent" />
                        <span>All Timetable Runs Completed</span>
                      </span>
                      <span className="text-zinc-500 font-mono text-[9px]">{simTime}</span>
                    </div>
                    <p className="text-zinc-400 leading-relaxed text-[10px]">
                      All scheduled trains have completed their runs and arrived at final destination terminals. Click below to restart at 10:00 AM.
                    </p>
                    <button
                      onClick={handleReset}
                      className="w-full py-2 bg-primary/20 hover:bg-primary/30 border border-primary/40 text-primary hover:text-white rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center justify-center space-x-2 shadow-glow"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Restart Simulation (10:00 AM Baseline)</span>
                    </button>
                  </div>
                )}
                {trains.map((train) => (
                  <div key={train.train_id} className="glass-panel p-3 rounded-xl flex flex-col space-y-3 border border-border/60 hover:border-primary/50 transition-all">
                    {/* Top Row: Train ID & Core Info */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2.5">
                        <div className={`p-2 rounded-lg bg-zinc-900 border ${
                          train.status === "RUNNING" ? "border-accent/30" : 
                          train.status === "DELAYED" ? "border-danger/30 animate-pulse" : "border-zinc-700"
                        }`}>
                          <Train className={`w-4 h-4 ${
                            train.status === "RUNNING" ? "text-accent animate-pulse" : 
                            train.status === "DELAYED" ? "text-danger" : "text-zinc-500"
                          }`} />
                        </div>
                        <div>
                          <div className="text-sm font-bold tracking-wide flex items-center space-x-1.5">
                            <span>{train.train_id}</span>
                            {train.delay_minutes > 0 && (
                              <span className="text-[9px] bg-warning/10 border border-warning/35 text-warning px-1.5 py-0.5 rounded font-mono">
                                +{train.delay_minutes.toFixed(0)}m
                              </span>
                            )}
                            {train.crew_violated && (
                              <span className="text-[9px] bg-danger/10 border border-danger/35 text-danger px-1.5 py-0.5 rounded font-bold animate-pulse" title="Crew Shift Limit Warning!">
                                CREW LIMIT
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-zinc-500 font-medium">
                            {train.service_type} • {train.direction.toUpperCase()}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-xs font-bold uppercase tracking-wider ${
                          train.status === "RUNNING" ? "text-accent" : 
                          train.status === "DWELLING" ? "text-primary" : 
                          train.status === "DELAYED" ? "text-danger" : "text-zinc-500"
                        }`}>
                          {train.status}
                        </div>
                        <div className="text-[9px] text-zinc-500 font-mono mt-0.5 space-y-0.5">
                          <div>{train.speed_kmh.toFixed(0)} km/h</div>
                          <div>{train.energy_consumed_kwh.toFixed(0)} kWh</div>
                          {train.priority_tokens !== undefined && (
                            <div className="text-primary font-bold">🎫 {train.priority_tokens.toFixed(1)} tkn</div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Timeline row */}
                    {(() => {
                      const stops = getTrainStops(train.train_id, train.service_type, train.direction);
                      let currentIdx = stops.indexOf(train.current_node);
                      if (train.status === "TERMINATED") {
                        currentIdx = stops.length - 1;
                      } else if (currentIdx === -1) {
                        currentIdx = 0;
                      }

                      return (
                        <div className="flex items-center justify-between pt-1 px-1">
                          {stops.map((stop, sIdx) => {
                            const isPassed = sIdx < currentIdx;
                            const isCurrent = sIdx === currentIdx;
                            const isLast = sIdx === stops.length - 1;
                            return (
                              <div key={stop} className="flex items-center flex-1 last:flex-initial">
                                {/* Stop Node Dot */}
                                <div className="relative flex flex-col items-center">
                                  {isCurrent && (
                                    <div className="w-1.5 h-1.5 rounded-full bg-primary absolute animate-ping" />
                                  )}
                                  <div 
                                    className={`w-1.5 h-1.5 rounded-full border transition-all relative z-10 ${
                                      isPassed ? "bg-accent border-accent" :
                                      isCurrent ? "bg-primary border-primary scale-125" :
                                      "bg-zinc-800 border-zinc-700"
                                    }`}
                                    title={stop}
                                  />
                                  <span className="text-[7px] text-zinc-600 font-mono mt-1 scale-90 origin-top">
                                    {stop}
                                  </span>
                                </div>
                                {/* Connecting Line */}
                                {!isLast && (
                                  <div 
                                    className={`h-[1px] flex-1 mx-0.5 ${
                                      isPassed ? "bg-accent/60" : "bg-zinc-800"
                                    }`}
                                  />
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </div>
                ))}
              </div>
            )}

            {/* Tab 2: Station Interlocks */}
            {activeTab === "stations" && (
              <div className="space-y-2">
                {stations.map((st) => (
                  <div key={st.station_id} className="glass-panel p-3.5 rounded-xl border border-zinc-800/80 space-y-2">
                    <div className="flex items-center justify-between border-b border-zinc-800/60 pb-1.5">
                      <span className="text-sm font-bold">{st.name} ({st.station_id})</span>
                      <span className="text-[10px] text-zinc-500 font-semibold uppercase">
                        Platforms: {st.occupied_platforms.length}/{st.capacity}
                      </span>
                    </div>

                    <div className="flex flex-col space-y-1">
                      {/* Occupied list */}
                      <div className="flex items-center space-x-2 text-[10px]">
                        <span className="text-zinc-500 font-semibold uppercase w-16">Platforms:</span>
                        <div className="flex flex-wrap gap-1">
                          {st.occupied_platforms.length === 0 ? (
                            <span className="text-zinc-600 italic">Empty</span>
                          ) : (
                            st.occupied_platforms.map(tid => (
                              <span key={tid} className="bg-accent/10 border border-accent/30 text-accent px-1.5 py-0.5 rounded text-[9px] font-bold">
                                {tid}
                              </span>
                            ))
                          )}
                        </div>
                      </div>

                      {/* Station Queue */}
                      <div className="flex items-center space-x-2 text-[10px]">
                        <span className="text-zinc-500 font-semibold uppercase w-16">Queued:</span>
                        <div className="flex flex-wrap gap-1">
                          {st.queue.length === 0 ? (
                            <span className="text-zinc-600 italic">None</span>
                          ) : (
                            st.queue.map(tid => (
                              <span key={tid} className="bg-danger/10 border border-danger/30 text-danger px-1.5 py-0.5 rounded text-[9px] font-bold animate-pulse">
                                {tid}
                              </span>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Tab: Live Model Training Monitor */}
            {activeTab === "live_training" && (
              <LiveTrainingMonitor />
            )}

            {/* Tab 0: NEXUS AI Neural Foundation Model Panel */}
            {activeTab === "ai_dispatch" && (
              <NexusNeuralPanel
                liveTrains={trains}
                selectedTrainId={selectedTrainId}
                onSelectTrain={(tid) => setSelectedTrainId(tid)}
              />
            )}

            {/* Tab 3: Agent negotiation log */}
            {activeTab === "logs" && (
              <div className="space-y-1.5 font-mono text-[10px] text-zinc-400">
                {negotiationLogs.length === 0 ? (
                  <div className="text-center text-zinc-600 italic py-8">No operation log records</div>
                ) : (
                  [...negotiationLogs].reverse().map((log, idx) => {
                    const isDisruption = log.includes("DISRUPTION");
                    const isStrategy = log.includes("approved Recovery");
                    return (
                      <div 
                        key={idx} 
                        className={`p-2 rounded border leading-relaxed ${
                          isDisruption ? "bg-danger/10 border-danger/30 text-danger font-semibold" :
                          isStrategy ? "bg-accent/10 border-accent/30 text-accent font-semibold" :
                          "bg-zinc-900/40 border-zinc-800/40"
                        }`}
                      >
                        {log}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </aside>
      </main>

      {/* Disruption Injection Dialog Modal (Glassmorphism overlay) */}
      {showInjectModal && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-md z-30 animate-fade-in">
          <div className="glass-panel p-6 rounded-2xl w-[400px] border border-zinc-700/80 space-y-4 shadow-glass">
            
            <div className="flex items-center justify-between border-b border-border/40 pb-3">
              <h3 className="text-base font-bold flex items-center space-x-2 text-danger">
                <AlertTriangle className="w-5 h-5 animate-pulse text-danger" />
                <span>Inject Rail Blockage</span>
              </h3>
              <button 
                onClick={() => setShowInjectModal(false)}
                className="text-zinc-500 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3.5 text-xs">
              <div className="flex gap-2">
                {['signal_failure', 'monsoon_washout', 'substation_failure', 'severe_weather', 'maintenance_window', 'rolling_stock_failure', 'network_partition', 'cascading_incident'].map((preset) => <button key={preset} onClick={async () => { try { await api.injectScenarioPreset(preset); setShowInjectModal(false); await fetchSimState(); } catch (err) { reportError("Unable to inject scenario preset.", err); } }} className="text-[8px] px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-white">{preset.replaceAll('_', ' ')}</button>)}
              </div>
              {/* Target segment information */}
              <div className="bg-zinc-900/80 border border-zinc-800 p-3 rounded-xl">
                <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block mb-1">
                  Target Sector
                </span>
                <span className="text-sm font-semibold text-zinc-300">
                  {selectedStation ? `Station Node: ${selectedStation}` : selectedTrack ? `Track Segment: ${selectedTrack.fromNode} ➔ ${selectedTrack.toNode}` : ""}
                </span>
              </div>

              {/* Block duration input */}
              <div className="space-y-1">
                <label className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block">
                  Blockage Duration (Minutes)
                </label>
                <input 
                  type="number" 
                  value={disruptionDuration}
                  onChange={(e) => setDisruptionDuration(parseInt(e.target.value) || 0)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2 text-zinc-200 focus:outline-none focus:border-primary font-mono text-sm"
                />
              </div>

              {/* Description input */}
              <div className="space-y-1">
                <label className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block">
                  Failure Description / Reason
                </label>
                <textarea 
                  rows={2}
                  value={disruptionDesc}
                  onChange={(e) => setDisruptionDesc(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2 text-zinc-200 focus:outline-none focus:border-primary text-xs"
                />
              </div>
            </div>

            {/* Modal actions */}
            <div className="flex space-x-3 pt-2">
              <button 
                onClick={() => setShowInjectModal(false)}
                className="flex-1 bg-zinc-900 border border-zinc-800 py-2.5 rounded-xl text-xs font-bold text-zinc-400 hover:text-white transition-all"
              >
                Cancel
              </button>
              <button 
                onClick={handleInjectDisruption}
                className="flex-1 bg-danger hover:bg-danger/80 py-2.5 rounded-xl text-xs font-bold text-white transition-all shadow-glow hover:scale-[1.02]"
              >
                Inject Blockage
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Three-way Scenario Comparison Panel Overlay (Slides up when disruption active) */}
      {hasActiveDisruption && scenarios.length > 0 && !committedStrategy && (
        <div className={`absolute bottom-0 left-0 right-0 p-5 bg-zinc-950/95 backdrop-blur-xl border-t shadow-glass z-20 animate-slide-up flex flex-col space-y-4 max-h-[90vh] overflow-y-auto transition-all duration-300 ${
          uiFocusMode === "crisis" ? "lg:max-h-[420px] border-danger/40 ring-1 ring-danger/20" : "lg:max-h-[380px] border-zinc-900"
        }`}>
          
          <div className="flex items-center justify-between border-b border-border/40 pb-2">
            <div>
              <h3 className="text-sm font-extrabold tracking-wider flex items-center space-x-2 text-danger">
                <AlertCircle className="w-4 h-4 text-danger animate-pulse" />
                <span>ACTIVE DISRUPTION RESOLUTION REQUIRED</span>
              </h3>
              <p className="text-[10px] text-zinc-500 mt-0.5">
                Simulated downstream consequences for alternative service recovery strategies.
              </p>
            </div>
            
            {committedStrategy && (
              <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-accent/20 border border-accent/50 text-accent font-black text-[10px] tracking-wide animate-pulse">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>STRATEGY EXECUTING: {scenarios.find(s => s.id === committedStrategy || normalizeStrat(s.id) === committedStrategy)?.name || committedStrategy.toUpperCase()}</span>
              </div>
            )}

            <div className="text-right text-[10px] text-zinc-500 flex items-center space-x-2 font-mono">
              <Radio className="w-3.5 h-3.5 text-danger animate-pulse" />
              <span>LOG: {activeDisruptions[0]?.description} (Duration: {activeDisruptions[0]?.duration} min)</span>
            </div>
            {!lifecyclePlan && <button onClick={handleGeneratePlan} className="text-[9px] font-bold px-3 py-1.5 rounded border border-primary/40 text-primary hover:text-white">GENERATE & VALIDATE PLAN</button>}
            {lifecyclePlan?.status === "validated" && <button onClick={handleApprovePlan} className="text-[9px] font-bold px-3 py-1.5 rounded border border-warning/40 text-warning hover:text-white">DISPATCHER APPROVE</button>}
            {lifecyclePlan?.status === "approved" && <span className="text-[9px] font-bold text-accent">APPROVED: {lifecyclePlan.plan.recommended_strategy}</span>}
          </div>

          {lifecyclePlan && (
            <>
            <section className="grid grid-cols-1 gap-3 rounded-xl border border-primary/20 bg-primary/5 p-3 text-[10px] md:grid-cols-3">
              <div>
                <div className="font-bold text-primary">PLANNER MODE</div>
                <div className="mt-1 text-zinc-300">{lifecyclePlan.plan.planner_metadata?.mode === "enhanced" ? "OPENAI ENHANCED" : "LOCAL RULE ENGINE"}</div>
                <div className="text-zinc-500">{lifecyclePlan.plan.planner_metadata?.mode === "enhanced" ? `${lifecyclePlan.plan.planner_metadata?.model || "configured model"} · ${(lifecyclePlan.plan.planner_metadata?.tool_calls ?? 0)} approved tool calls` : lifecyclePlan.plan.planner_metadata?.fallback_reason || "Deterministic safety fallback"}</div>
              </div>
              <div>
                <div className="font-bold text-warning">RISK & CONFIDENCE</div>
                <div className="mt-1 text-zinc-300">{lifecyclePlan.plan.confidence_score.toFixed(0)}% confidence</div>
                <div className="text-zinc-500">{(lifecyclePlan.plan.risk_factors || []).join(" · ") || "No elevated risk factors"}</div>
              </div>
              <div>
                <div className="font-bold text-accent">RECOVERY TIMELINE</div>
                <div className="mt-1 text-zinc-300">{(lifecyclePlan.plan.recovery_timeline_minutes || []).map((minute) => "T+" + minute + "m").join(" → ")}</div>
                <div className="text-zinc-500">{lifecyclePlan.plan.expected_metrics.delay_minutes.toFixed(0)}m predicted delay · {lifecyclePlan.plan.expected_metrics.resilience_score.toFixed(0)}% resilience</div>
              </div>
              {(lifecyclePlan.plan.alternative_strategies || []).length > 0 && <div className="md:col-span-3 border-t border-primary/15 pt-2 text-zinc-400"><span className="font-bold text-zinc-300">ALTERNATIVES: </span>{lifecyclePlan.plan.alternative_strategies?.map((item) => item.strategy + " — " + item.tradeoff).join(" | ")}</div>}
            </section>
            <section className="mt-3 grid grid-cols-1 gap-3 rounded-xl border border-accent/20 bg-accent/5 p-3 text-[10px] md:grid-cols-2">
              <div><div className="font-bold text-accent">PREDICTED OUTCOME</div><div className="mt-1 text-zinc-300">{lifecyclePlan.plan.expected_metrics.delay_minutes.toFixed(0)}m delay · {lifecyclePlan.plan.expected_metrics.energy_kwh.toFixed(0)} kWh</div></div>
              <div><div className="font-bold text-primary">LIVE TWIN OUTCOME</div><div className="mt-1 text-zinc-300">{metrics.total_passenger_delay_minutes.toFixed(0)}m delay · {metrics.total_energy_kwh.toFixed(0)} kWh</div><div className="text-zinc-500">Delay variance {(metrics.total_passenger_delay_minutes - lifecyclePlan.plan.expected_metrics.delay_minutes).toFixed(0)}m</div></div>
            </section>
            <section className="mt-3 rounded-xl border border-primary/20 bg-zinc-950/50 p-3 text-[10px]">
              <div className="font-bold text-primary">LIVE AI EXECUTION TRACE</div>
              <div className="mt-2 space-y-1 text-zinc-400">{negotiationLogs.filter((log) => /planner|tool|validator/i.test(log)).slice(-5).map((log, index) => <div key={index} className="border-l border-primary/40 pl-2">{log}</div>) || <div>No planner events captured yet.</div>}</div>
            </section>
            </>
          )}

          {!loadingScenarios && scenarios.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950/50">
              <table className="w-full text-left text-[10px] font-mono">
                <thead className="text-zinc-500 uppercase border-b border-zinc-800">
                  <tr><th className="px-3 py-2">Decision matrix</th><th className="px-3 py-2">Delay</th><th className="px-3 py-2">Energy</th><th className="px-3 py-2">Crew</th><th className="px-3 py-2">ORS</th></tr>
                </thead>
                <tbody>{scenarios.map((sc) => <tr key={`matrix-${sc.id}`} className={selectedStrategy === sc.id ? "bg-accent/10 text-accent" : "text-zinc-300 border-t border-zinc-900"}>
                  <td className="px-3 py-2 font-bold">{sc.name}</td><td className="px-3 py-2">{sc.delay_minutes.toFixed(0)}m</td><td className="px-3 py-2">{sc.energy_cost_kwh.toFixed(0)} kWh</td><td className="px-3 py-2">{sc.crew_violations_count}</td><td className="px-3 py-2">{sc.resilience_score.toFixed(0)}%</td>
                </tr>)}</tbody>
              </table>
            </div>
          )}

          {/* Three side-by-side cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 flex-1">
            {loadingScenarios ? (
              <div className="col-span-3 flex flex-col items-center justify-center py-10 space-y-3">
                <div className="w-8 h-8 border-3 border-danger border-t-transparent rounded-full animate-spin"></div>
                <p className="text-xs text-zinc-500 font-semibold tracking-wider uppercase animate-pulse">
                  Agentic Scenario Engine Simulating Trajectories...
                </p>
              </div>
            ) : (
              scenarios.map((sc) => {
                const isStrategyActive = (
                  committedStrategy === sc.id || 
                  committedStrategy === normalizeStrat(sc.id) ||
                  (selectedStrategy === sc.id && (lifecyclePlan?.status === "committed" || committedStrategy !== null))
                );
                return (
                  <div 
                    key={sc.id} 
                    className={`glass-panel p-4 rounded-xl flex flex-col justify-between border transition-all ${
                      isStrategyActive ? "border-accent/80 bg-accent/10 ring-2 ring-accent/50 shadow-glow" : 
                      sc.is_legal ? "border-zinc-800 hover:border-zinc-700" : "border-danger/45 bg-danger/5"
                    }`}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black tracking-wide text-zinc-200">{sc.name}</span>
                        <div className="flex items-center space-x-1">
                          {sc.is_pareto_optimal ? (
                            <span className="text-[9px] font-extrabold px-1.5 py-0.5 rounded font-mono bg-primary/15 text-primary border border-primary/25 animate-pulse" title="Pareto Optimal Strategy: Not dominated by any other strategy across delay, energy, and crew compliance.">
                              PARETO: OPTIMAL
                            </span>
                          ) : (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded font-mono bg-zinc-800 text-zinc-500 border border-zinc-700/50" title="Sub-optimal Strategy: Dominated by another option in all metrics.">
                              SUB-OPTIMAL
                            </span>
                          )}
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded font-mono ${
                            sc.resilience_score > 90 ? "bg-accent/15 text-accent border border-accent/25" :
                            sc.resilience_score > 70 ? "bg-warning/15 text-warning border border-warning/25" :
                            "bg-danger/15 text-danger border border-danger/25"
                          }`}>
                            ORS: {sc.resilience_score.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      <p className="text-[10px] text-zinc-500 leading-relaxed font-medium">{sc.description}</p>
                      
                      {/* Visual SVG Comparison Chart */}
                      <div className="space-y-1.5 pt-2 border-t border-border/30 mt-2">
                        <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider block">
                          Scenario Profile Chart
                        </span>
                        <div className="space-y-1 text-[8px] font-mono">
                          {/* ORS Bar */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400">ORS Resilience</span>
                            <span className="text-white font-bold">{sc.resilience_score.toFixed(0)}%</span>
                          </div>
                          <div className="w-full h-1 bg-zinc-900 rounded-full overflow-hidden">
                            <div 
                              className={`h-full rounded-full transition-all duration-500 ${
                                sc.resilience_score > 90 ? "bg-accent" :
                                sc.resilience_score > 70 ? "bg-warning" : "bg-danger"
                              }`}
                              style={{ width: `${sc.resilience_score}%` }}
                            />
                          </div>

                          {/* Delay Bar */}
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-zinc-400">Delay Factor</span>
                            <span className="text-zinc-300">{sc.delay_minutes.toFixed(0)}m</span>
                          </div>
                          <div className="w-full h-1 bg-zinc-900 rounded-full overflow-hidden">
                            <div 
                              className="h-full rounded-full bg-warning transition-all duration-500"
                              style={{ width: `${Math.min(100, (sc.delay_minutes / 240) * 100)}%` }}
                            />
                          </div>

                          {/* Energy Bar */}
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-zinc-400">Energy Draw</span>
                            <span className="text-zinc-300">{sc.energy_cost_kwh.toFixed(0)} kWh</span>
                          </div>
                          <div className="w-full h-1 bg-zinc-900 rounded-full overflow-hidden">
                            <div 
                              className="h-full rounded-full bg-primary transition-all duration-500"
                              style={{ width: `${Math.min(100, (sc.energy_cost_kwh / 3000) * 100)}%` }}
                            />
                          </div>

                          {/* Crew Violations text indicator */}
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-zinc-400">Crew Compliance</span>
                            <span className={sc.crew_violations_count > 0 ? "text-danger font-bold animate-pulse" : "text-accent"}>
                              {sc.crew_violations_count > 0 ? `${sc.crew_violations_count} VIOLATIONS` : "100% OK"}
                            </span>
                          </div>
                        </div>
                      </div>
                      {/* Explanation box */}
                      <div className="bg-black/40 border border-zinc-800/80 p-2 rounded-lg text-[9px] text-zinc-400 leading-relaxed mt-2 italic flex items-start space-x-1.5">
                        <CheckCircle className="w-3 h-3 text-primary shrink-0 mt-0.5" />
                        <span>{sc.explainer}</span>
                      </div>
                      <button onClick={async () => { try { const evidence = await api.whyNotScenario(sc.id); setWhyNotMessage(messages => ({ ...messages, [sc.id]: evidence.reason })); } catch { setWhyNotMessage(messages => ({ ...messages, [sc.id]: "Evidence is currently unavailable." })); } }} className="text-[8px] text-primary hover:text-white font-bold mt-1">WHY NOT THIS OPTION?</button>
                      {whyNotMessage[sc.id] && <p className="mt-1 text-[8px] text-warning leading-relaxed">{whyNotMessage[sc.id]}</p>}
                      <button onClick={async () => { try { const [explanation, confidence] = await Promise.all([api.getScenarioExplanation(sc.id), api.getScenarioConfidence(sc.id)]); setDecisionEvidence(items => ({ ...items, [sc.id]: { rationale: explanation.rationale, tradeoffs: explanation.tradeoffs, fallback: explanation.fallback, score: confidence.score } })); } catch { /* evidence remains unavailable */ } }} className="ml-3 text-[8px] text-accent hover:text-white font-bold">VIEW EVIDENCE</button>
                      {decisionEvidence[sc.id] && <div className="mt-2 p-2 rounded border border-primary/20 bg-primary/5 text-[8px] text-zinc-300"><div className="text-primary font-bold">CONFIDENCE {(decisionEvidence[sc.id].score * 100).toFixed(0)}%</div><p>{decisionEvidence[sc.id].rationale}</p><p>Trade-offs: {decisionEvidence[sc.id].tradeoffs.join(" · ")}</p><p>Fallback: {decisionEvidence[sc.id].fallback}</p></div>}

                      {/* COSMOS command box */}
                      {(() => {
                        const edgeId = activeDisruptions[0]?.edge_id;
                        const nodeId = activeDisruptions[0]?.node_id || (edgeId ? edgeId.split("->")[0] : "SUR");
                        const match = sc.explainer.match(/(VB-\d+|TJ-\d+|LC-\d+)/);
                        const targetTrain = match ? match[1] : "VB-20901";
                        
                        let cosmosCmd = "";
                        if (sc.id === "do_nothing") {
                          cosmosCmd = `CMD/HOLD/TR-${targetTrain}/${nodeId}`;
                        } else if (sc.id === "detour") {
                          cosmosCmd = `CMD/ROUTE/TR-${targetTrain}/${edgeId || "SUR->BHA"}/DETOUR`;
                        } else if (sc.id === "short_turn") {
                          cosmosCmd = `CMD/TURN/TR-${targetTrain}/${nodeId}/SHORT_TURN`;
                        }
                        
                        return (
                          <div className="mt-3 bg-zinc-900 border border-zinc-800 p-2 rounded-lg flex items-center justify-between font-mono text-[9px] text-zinc-300">
                            <div className="flex flex-col">
                              <span className="text-[7px] text-zinc-500 uppercase tracking-widest font-bold">COSMOS Command Stream</span>
                              <span className="text-primary font-bold">{cosmosCmd}</span>
                            </div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(cosmosCmd);
                                audioService.playClick();
                                alert("COSMOS Command copied to clipboard!");
                              }}
                              className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white rounded transition-all cursor-pointer font-sans text-[8px] font-bold border border-zinc-700"
                            >
                              COPY
                            </button>
                          </div>
                        );
                      })()}
                    </div>

                    <button 
                      onClick={() => handleResolveScenario(sc.id)}
                      disabled={isStrategyActive}
                      className={`w-full py-2.5 rounded-lg text-[10px] font-extrabold tracking-wider uppercase mt-3 transition-all flex items-center justify-center space-x-1.5 ${
                        isStrategyActive ? "bg-accent/25 text-accent cursor-default border-2 border-accent/60 shadow-glow" :
                        sc.is_legal ? "bg-primary hover:bg-primary/80 text-white hover:scale-[1.01]" : 
                        "bg-danger/80 hover:bg-danger text-white hover:scale-[1.01]"
                      }`}
                    >
                      {isStrategyActive ? (
                        <>
                          <CheckCircle className="w-3.5 h-3.5 text-accent animate-pulse" />
                          <span>STRATEGY ACTIVE & EXECUTED</span>
                        </>
                      ) : (
                        "Commit Strategy"
                      )}
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
