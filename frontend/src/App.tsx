import { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { RailMap } from './components/RailMap';
import { 
  api, 
  type TrainState, 
  type StationState, 
  type Disruption, 
  type SimulationMetrics, 
  type ScenarioOption 
} from './services/api';
import { audioService } from './services/audio';
import './App.css';

const getTrainStops = (trainId: string, serviceType: string, direction: string) => {
  let stops = ["MUM", "TNA", "VIR", "BOI", "VAP", "BIL", "SUR", "BHA", "VAD", "ANA", "ADI", "SAB"];
  if (serviceType === "Vande Bharat") {
    stops = ["MUM", "TNA", "SUR", "VAD", "ADI", "SAB"];
  } else if (serviceType === "Tejas Express") {
    stops = ["MUM", "TNA", "VAP", "SUR", "VAD", "ANA", "ADI", "SAB"];
  }
  return direction === "inbound" ? [...stops].reverse() : stops;
};

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

  // Disruption Injection Dialog state
  const [selectedStation, setSelectedStation] = useState<string | null>(null);
  const [selectedTrack, setSelectedTrack] = useState<{ fromNode: string; toNode: string } | null>(null);
  const [disruptionDuration, setDisruptionDuration] = useState<number>(60);
  const [disruptionDesc, setDisruptionDesc] = useState<string>("Track circuit signal failure");
  const [showInjectModal, setShowInjectModal] = useState<boolean>(false);

  // UI Tabs for Sidebar
  const [activeTab, setActiveTab] = useState<"trains" | "stations" | "logs">("trains");

  // Adaptive UI state
  const [uiFocusMode, setUiFocusMode] = useState<"cockpit" | "crisis">("cockpit");

  // Fetch complete simulation state
  const fetchSimState = async () => {
    try {
      const state = await api.getSimulationState();
      setTrains(state.trains);
      setStations(state.stations);
      setActiveDisruptions(state.active_disruptions);
      setMetrics(state.metrics);
      setNegotiationLogs(state.negotiation_logs);
      setSimTime(state.simulation_time);
    } catch (err) {
      console.error("Failed to poll simulator states:", err);
    }
  };

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
  }, [isPlaying, simSpeed]);

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
    }
  }, [activeDisruptions]);

  const fetchScenarios = async () => {
    setLoadingScenarios(true);
    try {
      const response = await api.compareScenarios();
      setScenarios(response.scenarios);
    } catch (err) {
      console.error("Failed to compare scenarios:", err);
    } finally {
      setLoadingScenarios(false);
    }
  };

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
  };

  const handleReset = async () => {
    audioService.playClick();
    setIsPlaying(false);
    await api.controlSimulation("reset");
    setScenarios([]);
    setSelectedStrategy(null);
    setSelectedStation(null);
    setSelectedTrack(null);
    setShowInjectModal(false);
    // Fetch initial state
    setTimeout(fetchSimState, 200);
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
      console.error("Failed to inject disruption:", err);
    }
  };

  const handleResolveScenario = async (strategyId: string) => {
    try {
      audioService.playSuccess();
      setSelectedStrategy(strategyId);
      await api.resolveScenario(strategyId);
      // Resume simulation running
      setIsPlaying(true);
      await api.controlSimulation("play", simSpeed);
    } catch (err) {
      console.error("Failed to resolve scenario:", err);
    }
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
          </div>
        </div>
      </header>

      {/* Main Structural Layout */}
      <main className="flex flex-col lg:flex-row flex-1 overflow-hidden relative">
        
        {/* Left Side: Rail Network Visualization Map */}
        <section className="flex-1 h-[55%] lg:h-full relative border-b lg:border-b-0 lg:border-r border-border bg-zinc-950/20">
          <RailMap 
            trains={trains} 
            activeDisruptions={activeDisruptions} 
            onStationSelect={handleMapStationSelect}
            onTrackSelect={handleMapTrackSelect}
          />
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
          <div className="flex border-b border-border/40 text-xs">
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("trains"); }}
              className={`flex-1 py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "trains" ? "border-primary text-white bg-primary/5" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Trains ({activeTrainsCount})
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("stations"); }}
              className={`flex-1 py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "stations" ? "border-primary text-white bg-primary/5" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Stations
            </button>
            <button 
              onClick={() => { audioService.playClick(); setActiveTab("logs"); }}
              className={`flex-1 py-3 text-center font-bold border-b-2 transition-all ${
                activeTab === "logs" ? "border-primary text-white bg-primary/5" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Logs ({negotiationLogs.length})
            </button>
          </div>

          {/* Tab Content Panel */}
          <div className="flex-1 overflow-y-auto p-4">
            
            {/* Tab 1: Live Train Fleet */}
            {activeTab === "trains" && (
              <div className="space-y-2">
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
      {hasActiveDisruption && (
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
            
            <div className="text-right text-[10px] text-zinc-500 flex items-center space-x-2 font-mono">
              <Radio className="w-3.5 h-3.5 text-danger animate-pulse" />
              <span>LOG: {activeDisruptions[0]?.description} (Duration: {activeDisruptions[0]?.duration} min)</span>
            </div>
          </div>

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
                const isStrategyActive = selectedStrategy === sc.id;
                return (
                  <div 
                    key={sc.id} 
                    className={`glass-panel p-4 rounded-xl flex flex-col justify-between border transition-all ${
                      isStrategyActive ? "border-accent bg-accent/5 ring-1 ring-accent" : 
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
                      className={`w-full py-2 rounded-lg text-[10px] font-bold tracking-wider uppercase mt-3 transition-all ${
                        isStrategyActive ? "bg-accent/20 text-accent cursor-default border border-accent/40" :
                        sc.is_legal ? "bg-primary hover:bg-primary/80 text-white hover:scale-[1.01]" : 
                        "bg-danger/80 hover:bg-danger text-white hover:scale-[1.01]"
                      }`}
                    >
                      {isStrategyActive ? "Strategy Active" : "Commit Strategy"}
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
