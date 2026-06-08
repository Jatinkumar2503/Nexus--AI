import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { api, type TopologyResponse, type TrackEdge, type TrainState } from '../services/api';

interface RailMapProps {
  trains?: TrainState[];
  onStationSelect?: (stationId: string) => void;
  onTrackSelect?: (fromNode: string, toNode: string) => void;
}

export const RailMap: React.FC<RailMapProps> = ({ trains = [], onStationSelect, onTrackSelect }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState<boolean>(false);

  // Effect to initialize the map
  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [137.5, 35.2], // Centered on Tokaido Shinkansen route
      zoom: 6.8,
      minZoom: 5,
      maxZoom: 12,
      attributionControl: false
    });

    mapInstance.current = map;

    map.on('load', async () => {
      try {
        const data = await api.getTopology();

        // Render network graph
        drawTracks(map, data);
        drawStations(map, data);

        setMapLoaded(true);
      } catch (err) {
        console.error("Failed to load map topology data:", err);
        setMapLoaded(true);
      }
    });

    return () => {
      map.remove();
    };
  }, []);

  // Effect to update train positions dynamically
  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !mapLoaded) return;

    // Build GeoJSON features for active trains
    const features = trains.map((train) => ({
      type: 'Feature' as const,
      properties: {
        id: train.train_id,
        type: train.service_type,
        status: train.status,
        delay: train.delay_minutes,
        passengers: train.passenger_count
      },
      geometry: {
        type: 'Point' as const,
        coordinates: [train.coordinates[1], train.coordinates[0]] // [Longitude, Latitude]
      }
    }));

    const geojsonData = {
      type: 'FeatureCollection' as const,
      features: features
    };

    const sourceId = 'trains-source';

    // If source doesn't exist, create it and register the layers
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geojsonData
      });

      // Train outer pulsing/glowing ring
      map.addLayer({
        id: 'train-glows',
        type: 'circle',
        source: sourceId,
        paint: {
          'circle-radius': 11,
          'circle-color': [
            'match',
            ['get', 'status'],
            'RUNNING', '#eab308', // Glowing yellow
            'DWELLING', '#10b981', // Neon green at stations
            'WAITING', '#a1a1aa', // Gray
            '#ef4444' // Red if delayed/stopped
          ],
          'circle-opacity': 0.3,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#ffffff',
          'circle-stroke-opacity': 0.5
        }
      });

      // Core train dots
      map.addLayer({
        id: 'train-dots',
        type: 'circle',
        source: sourceId,
        paint: {
          'circle-radius': 6,
          'circle-color': [
            'match',
            ['get', 'status'],
            'RUNNING', '#eab308',
            'DWELLING', '#10b981',
            'WAITING', '#71717a',
            '#ef4444'
          ],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      });

      // Train ID labels
      map.addLayer({
        id: 'train-labels',
        type: 'symbol',
        source: sourceId,
        layout: {
          'text-field': ['get', 'id'],
          'text-size': 9,
          'text-offset': [0, -1.5],
          'text-anchor': 'bottom',
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold']
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': '#09090b',
          'text-halo-width': 2
        }
      });
    } else {
      // Source already exists, just update data payload (extremely fast HMR-like updates)
      const source = map.getSource(sourceId) as maplibregl.GeoJSONSource;
      source.setData(geojsonData);
    }
  }, [trains, mapLoaded]);

  // Draws rail track segments as vector lines on the map
  const drawTracks = (map: maplibregl.Map, data: TopologyResponse) => {
    const outboundCoords: number[][][] = [];
    const inboundCoords: number[][][] = [];

    data.edges.forEach((edge: TrackEdge) => {
      const fromStation = data.nodes[edge.from_node];
      const toStation = data.nodes[edge.to_node];

      if (fromStation && toStation) {
        const fromCoords = [fromStation.coords[1], fromStation.coords[0]];
        const toCoords = [toStation.coords[1], toStation.coords[0]];

        if (edge.direction === "outbound") {
          outboundCoords.push([fromCoords, toCoords]);
        } else {
          inboundCoords.push([fromCoords, toCoords]);
        }
      }
    });

    map.addSource('outbound-tracks', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'MultiLineString',
          coordinates: outboundCoords
        }
      }
    });

    map.addLayer({
      id: 'outbound-tracks-layer',
      type: 'line',
      source: 'outbound-tracks',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#3b82f6',
        'line-width': 3.5,
        'line-opacity': 0.85
      }
    });

    map.addSource('inbound-tracks', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'MultiLineString',
          coordinates: inboundCoords
        }
      }
    });

    map.addLayer({
      id: 'inbound-tracks-layer',
      type: 'line',
      source: 'inbound-tracks',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#1d4ed8',
        'line-width': 2.5,
        'line-opacity': 0.7,
        'line-dasharray': [2, 2]
      }
    });
  };

  // Draws stations as circles and text labels
  const drawStations = (map: maplibregl.Map, data: TopologyResponse) => {
    const features = Object.entries(data.nodes).map(([code, info]) => ({
      type: 'Feature' as const,
      properties: {
        id: code,
        name: info.name,
        platforms: info.platforms
      },
      geometry: {
        type: 'Point' as const,
        coordinates: [info.coords[1], info.coords[0]]
      }
    }));

    map.addSource('stations', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: features
      }
    });

    map.addLayer({
      id: 'station-glows',
      type: 'circle',
      source: 'stations',
      paint: {
        'circle-radius': 9,
        'circle-color': '#3b82f6',
        'circle-opacity': 0.2,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#3b82f6',
        'circle-stroke-opacity': 0.4
      }
    });

    map.addLayer({
      id: 'station-dots',
      type: 'circle',
      source: 'stations',
      paint: {
        'circle-radius': 5,
        'circle-color': '#ffffff',
        'circle-stroke-width': 3,
        'circle-stroke-color': '#09090b'
      }
    });

    map.addLayer({
      id: 'station-labels',
      type: 'symbol',
      source: 'stations',
      layout: {
        'text-field': ['get', 'name'],
        'text-size': 10,
        'text-offset': [0, 1.4],
        'text-anchor': 'top',
        'text-max-width': 8
      },
      paint: {
        'text-color': '#a1a1aa',
        'text-halo-color': '#09090b',
        'text-halo-width': 1.5
      }
    });

    map.on('click', 'station-dots', (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['station-dots'] });
      if (features.length > 0) {
        const stationId = features[0].properties?.id;
        console.log(`Station selected: ${stationId}`);
        if (stationId && onStationSelect) {
          onStationSelect(stationId);
        }
      }
    });

    // Handle track click if requested
    map.on('click', 'outbound-tracks-layer', (e) => {
      if (onTrackSelect && e.features && e.features.length > 0) {
        // Simple track click handler logic can go here
      }
    });

    map.on('mouseenter', 'station-dots', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'station-dots', () => {
      map.getCanvas().style.cursor = '';
    });
  };

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
