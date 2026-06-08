import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

interface RailMapProps {
  onStationSelect?: (stationId: string) => void;
  onTrackSelect?: (fromNode: string, toNode: string) => void;
}

export const RailMap: React.FC<RailMapProps> = ({ onStationSelect, onTrackSelect }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState<boolean>(false);

  useEffect(() => {
    if (!mapContainer.current) return;

    // Initialize MapLibre GL Map with CartoDB Dark Matter free map style
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [137.5, 35.2], // Center coordinate near Shizuoka/Nagoya (covers Tokyo to Osaka line)
      zoom: 6.8,
      minZoom: 5,
      maxZoom: 12,
      attributionControl: false
    });

    mapInstance.current = map;

    map.on('load', () => {
      setMapLoaded(true);
      console.log("MapLibre GL Map initialized successfully.");
    });

    // Clean up map resources on component unmount
    return () => {
      map.remove();
    };
  }, []);

  return (
    <div className="w-full h-full relative bg-zinc-950">
      <div ref={mapContainer} className="w-full h-full" />
      
      {!mapLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm z-20">
          <div className="text-center space-y-3">
            <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-sm text-zinc-400 font-medium tracking-wide">Loading Vector Map Layers...</p>
          </div>
        </div>
      )}
    </div>
  );
};
