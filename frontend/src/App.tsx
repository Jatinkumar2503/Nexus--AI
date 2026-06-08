import { useState, useEffect } from 'react';
import { Shield, Activity, Play, Pause, Train } from 'lucide-react';
import { RailMap } from './components/RailMap';
import { api, type TrainState } from './services/api';
import './App.css';

function App() {
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [simTime, setSimTime] = useState<string>("10:00:00");
  const [systemStatus] = useState<"NORMAL" | "DISRUPTED">("NORMAL");
  const [trains, setTrains] = useState<TrainState[]>([]);

  // Fetch live train coordinates and simulation time
  useEffect(() => {
    let interval: any;

    const fetchSimState = async () => {
      try {
        const response = await api.getLiveTrains();
        setTrains(response.trains);
        setSimTime(response.simulation_time);
      } catch (err) {
        console.error("Failed to poll simulator states:", err);
      }
    };

    fetchSimState();

    if (isPlaying) {
      interval = setInterval(fetchSimState, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying]);

  // Derived KPI metrics
  const activeTrainsCount = trains.filter(t => t.status === "RUNNING" || t.status === "DWELLING").length;
  const delayedTrainsCount = trains.filter(t => t.delay_minutes > 0).length;
  const punctuality = activeTrainsCount > 0 
    ? Math.max(0, Math.min(100, 100 - (delayedTrainsCount / activeTrainsCount) * 100))
    : 100;

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

        {/* Live Simulation Clock & Controls */}
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2 bg-zinc-900/60 border border-border px-4 py-1.5 rounded-full backdrop-blur-sm">
            <button 
              onClick={() => setIsPlaying(!isPlaying)} 
              className="text-zinc-400 hover:text-white transition-colors"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 text-primary" />}
            </button>
            <span className="text-zinc-600">|</span>
            <div className="text-sm font-mono tracking-widest text-zinc-300">
              TIME: <span className="text-primary font-bold">{simTime}</span>
            </div>
          </div>

          {/* Status Indicator */}
          <div className="flex items-center space-x-2">
            <span className={`relative flex h-2.5 w-2.5`}>
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                systemStatus === "NORMAL" ? "bg-accent" : "bg-danger"
              }`}></span>
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                systemStatus === "NORMAL" ? "bg-accent" : "bg-danger"
              }`}></span>
            </span>
            <span className={`text-xs font-semibold tracking-wider ${
              systemStatus === "NORMAL" ? "text-accent" : "text-danger"
            }`}>
              SYSTEM {systemStatus}
            </span>
          </div>
        </div>
      </header>

      {/* Main Structural Layout */}
      <main className="flex flex-1 overflow-hidden relative">
        {/* Left Side: Rail Network Visualization Map */}
        <section className="flex-1 h-full relative border-r border-border bg-zinc-950/20">
          <RailMap trains={trains} />
        </section>

        {/* Right Side: Operational Metrics & Controller */}
        <aside className="w-96 h-full flex flex-col bg-zinc-950/45 backdrop-blur-lg overflow-y-auto border-l border-zinc-900">
          <div className="p-6 space-y-6">
            {/* KPI Metrics Cards */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold tracking-widest text-zinc-500 uppercase">
                Active Corridor Metrics
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-panel p-4 rounded-xl flex flex-col justify-between h-24">
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Punctuality</span>
                  <span className="text-2xl font-bold text-accent">{punctuality.toFixed(1)}%</span>
                </div>
                <div className="glass-panel p-4 rounded-xl flex flex-col justify-between h-24">
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Active Trains</span>
                  <span className="text-2xl font-bold text-primary">{activeTrainsCount}</span>
                </div>
              </div>
            </div>

            {/* Live Train Roster */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold tracking-widest text-zinc-500 uppercase">
                Live Train Fleet
              </h3>
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {trains.map((train) => (
                  <div key={train.train_id} className="glass-panel p-3.5 rounded-xl flex items-center justify-between border border-border/60 hover:border-primary/50 transition-colors">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg bg-zinc-900 border ${
                        train.status === "RUNNING" ? "border-accent/40" : "border-zinc-700"
                      }`}>
                        <Train className={`w-4 h-4 ${
                          train.status === "RUNNING" ? "text-accent animate-pulse" : "text-zinc-400"
                        }`} />
                      </div>
                      <div>
                        <div className="text-sm font-bold tracking-wide">{train.train_id}</div>
                        <div className="text-[10px] text-zinc-500 font-medium">
                          {train.service_type} • {train.direction.toUpperCase()}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-xs font-bold ${
                        train.status === "RUNNING" ? "text-primary" : 
                        train.status === "DWELLING" ? "text-accent" : "text-zinc-500"
                      }`}>
                        {train.status}
                      </div>
                      <div className="text-[10px] text-zinc-500 font-medium mt-0.5">
                        {train.speed_kmh.toFixed(0)} km/h
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Control Instructions */}
            <div className="glass-panel p-5 rounded-xl space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Control Actions
                </span>
                <Shield className="w-4 h-4 text-zinc-500" />
              </div>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Use the map interface to select a railway sector and inject track failures to simulate recovery alternatives.
              </p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default App;
