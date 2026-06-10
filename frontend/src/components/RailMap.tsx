import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { api, type TopologyResponse, type TrainState, type Disruption } from '../services/api';

interface RailMapProps {
  trains?: TrainState[];
  activeDisruptions?: Disruption[];
  onStationSelect?: (stationId: string) => void;
  onTrackSelect?: (fromNode: string, toNode: string) => void;
}

export const RailMap: React.FC<RailMapProps> = ({ 
  trains = [], 
  activeDisruptions = [], 
  onStationSelect, 
  onTrackSelect 
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const popupInstance = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState<boolean>(false);
  const [topology, setTopology] = useState<TopologyResponse | null>(null);

  // Initialize Map
  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [72.84, 21.20], // Centered on Western India
      zoom: 6.8,
      minZoom: 4,
      maxZoom: 12,
      attributionControl: false
    });

    mapInstance.current = map;

    popupInstance.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'nexus-map-tooltip'
    });

    map.on('load', async () => {
      try {
        const data = await api.getTopology();
        setTopology(data);

        // 1. Set up track source and layers with empty data initially
        map.addSource('outbound-tracks', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] }
        });

        map.addLayer({
          id: 'outbound-tracks-layer',
          type: 'line',
          source: 'outbound-tracks',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': [
              'match',
              ['get', 'status'],
              'blocked', '#ef4444', // Neon/glowing red
              '#3b82f6' // Tech blue
            ],
            'line-width': [
              'match',
              ['get', 'status'],
              'blocked', 5,
              3.5
            ],
            'line-opacity': 0.9
          }
        });

        map.addSource('inbound-tracks', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] }
        });

        map.addLayer({
          id: 'inbound-tracks-layer',
          type: 'line',
          source: 'inbound-tracks',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': [
              'match',
              ['get', 'status'],
              'blocked', '#ef4444',
              '#1d4ed8'
            ],
            'line-width': [
              'match',
              ['get', 'status'],
              'blocked', 5,
              2.5
            ],
            'line-opacity': 0.8,
            'line-dasharray': [2, 2]
          }
        });

        // 2. Draw stations
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

  // Update track blocking visual states dynamically
  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !mapLoaded || !topology) return;

    // Helper to generate geojson features
    const outboundFeatures = topology.edges
      .filter(e => e.direction === "outbound")
      .map(edge => {
        const fromStation = topology.nodes[edge.from_node];
        const toStation = topology.nodes[edge.to_node];
        if (fromStation && toStation) {
          const key = `${edge.from_node}->${edge.to_node}`;
          const isBlocked = activeDisruptions.some(
            d => d.edge_id === key || d.node_id === edge.from_node || d.node_id === edge.to_node
          );
          return {
            type: 'Feature' as const,
            properties: {
              from_node: edge.from_node,
              to_node: edge.to_node,
              status: isBlocked ? 'blocked' : 'open'
            },
            geometry: {
              type: 'LineString' as const,
              coordinates: [
                [fromStation.coords[1], fromStation.coords[0]],
                [toStation.coords[1], toStation.coords[0]]
              ]
            }
          };
        }
        return null;
      }).filter((f): f is Exclude<typeof f, null> => f !== null);

    const inboundFeatures = topology.edges
      .filter(e => e.direction === "inbound")
      .map(edge => {
        const fromStation = topology.nodes[edge.from_node];
        const toStation = topology.nodes[edge.to_node];
        if (fromStation && toStation) {
          const key = `${edge.from_node}->${edge.to_node}`; // Directed key
          const isBlocked = activeDisruptions.some(
            d => d.edge_id === key || d.node_id === edge.from_node || d.node_id === edge.to_node
          );
          return {
            type: 'Feature' as const,
            properties: {
              from_node: edge.from_node,
              to_node: edge.to_node,
              status: isBlocked ? 'blocked' : 'open'
            },
            geometry: {
              type: 'LineString' as const,
              coordinates: [
                [fromStation.coords[1], fromStation.coords[0]],
                [toStation.coords[1], toStation.coords[0]]
              ]
            }
          };
        }
        return null;
      }).filter((f): f is Exclude<typeof f, null> => f !== null);

    const outSource = map.getSource('outbound-tracks') as maplibregl.GeoJSONSource;
    if (outSource) outSource.setData({ type: 'FeatureCollection', features: outboundFeatures });

    const inSource = map.getSource('inbound-tracks') as maplibregl.GeoJSONSource;
    if (inSource) inSource.setData({ type: 'FeatureCollection', features: inboundFeatures });

  }, [activeDisruptions, mapLoaded, topology]);

  // Effect to update train positions dynamically
  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !mapLoaded) return;

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
            'DELAYED', '#ef4444', // Red
            '#ef4444' // Default
          ],
          'circle-opacity': 0.35,
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
          'circle-radius': 6.5,
          'circle-color': [
            'match',
            ['get', 'status'],
            'RUNNING', '#eab308',
            'DWELLING', '#10b981',
            'WAITING', '#71717a',
            'DELAYED', '#ef4444',
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

      // Hover popups for trains
      map.on('mouseenter', 'train-dots', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        const coordinates = (e.features?.[0]?.geometry as any).coordinates.slice();
        const props = e.features?.[0]?.properties;
        if (!props) return;

        const html = `
          <div class="p-2.5 font-sans text-xs bg-zinc-950/95 border border-zinc-800 rounded-xl shadow-glass text-zinc-100 min-w-[150px] space-y-1">
            <div class="flex items-center justify-between border-b border-zinc-800 pb-1 font-bold">
              <span class="text-primary">${props.id}</span>
              <span class="${props.status === 'DELAYED' ? 'text-danger font-semibold' : 'text-accent'}">${props.status}</span>
            </div>
            <div class="text-[10px] space-y-0.5 text-zinc-400 font-medium">
              <div>Type: <span class="text-zinc-200 font-bold">${props.type}</span></div>
              <div>Passengers: <span class="text-zinc-200 font-bold">${props.passengers}</span></div>
              <div>Delay: <span class="text-warning font-bold">${Number(props.delay).toFixed(0)}m</span></div>
            </div>
          </div>
        `;

        while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
          coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
        }

        popupInstance.current
          ?.setLngLat(coordinates)
          .setHTML(html)
          .addTo(map);
      });

      map.on('mouseleave', 'train-dots', () => {
        map.getCanvas().style.cursor = '';
        popupInstance.current?.remove();
      });

    } else {
      const source = map.getSource(sourceId) as maplibregl.GeoJSONSource;
      source.setData(geojsonData);
    }
  }, [trains, mapLoaded]);

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
        'circle-radius': 10,
        'circle-color': '#3b82f6',
        'circle-opacity': 0.15,
        'circle-stroke-width': 1.2,
        'circle-stroke-color': '#3b82f6',
        'circle-stroke-opacity': 0.4
      }
    });

    map.addLayer({
      id: 'station-dots',
      type: 'circle',
      source: 'stations',
      paint: {
        'circle-radius': 5.5,
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

    // Handle station click
    map.on('click', 'station-dots', (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['station-dots'] });
      if (features.length > 0) {
        const stationId = features[0].properties?.id;
        if (stationId && onStationSelect) {
          onStationSelect(stationId);
        }
      }
    });

    // Handle track clicks
    const handleTrackClick = (e: any, layerId: string) => {
      const features = map.queryRenderedFeatures(e.point, { layers: [layerId] });
      if (features.length > 0 && onTrackSelect) {
        const props = features[0].properties;
        if (props?.from_node && props?.to_node) {
          onTrackSelect(props.from_node, props.to_node);
        }
      }
    };

    map.on('click', 'outbound-tracks-layer', (e) => handleTrackClick(e, 'outbound-tracks-layer'));
    map.on('click', 'inbound-tracks-layer', (e) => handleTrackClick(e, 'inbound-tracks-layer'));

    // Hover popups for stations
    map.on('mouseenter', 'station-dots', (e) => {
      map.getCanvas().style.cursor = 'pointer';
      const coordinates = (e.features?.[0]?.geometry as any).coordinates.slice();
      const props = e.features?.[0]?.properties;
      if (!props) return;

      const html = `
        <div class="p-2.5 font-sans text-xs bg-zinc-950/95 border border-zinc-800 rounded-xl shadow-glass text-zinc-100 min-w-[150px] space-y-1">
          <div class="border-b border-zinc-800 pb-1 font-bold text-primary">
            ${props.name} (${props.id})
          </div>
          <div class="text-[10px] text-zinc-400 font-medium">
            <div>Platforms: <span class="text-zinc-200 font-bold">${props.platforms}</span></div>
            <div class="text-[9px] text-zinc-500 mt-1 italic">Click station to disrupt</div>
          </div>
        </div>
      `;

      while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
        coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
      }

      popupInstance.current
        ?.setLngLat(coordinates)
        .setHTML(html)
        .addTo(map);
    });

    map.on('mouseleave', 'station-dots', () => {
      map.getCanvas().style.cursor = '';
      popupInstance.current?.remove();
    });

    // Hover popups for tracks
    const handleTrackMouseEnter = (e: any, layerId: string) => {
      map.getCanvas().style.cursor = 'pointer';
      const props = e.features?.[0]?.properties;
      if (!props) return;

      const isBlocked = props.status === 'blocked';
      const html = `
        <div class="p-2.5 font-sans text-xs bg-zinc-950/95 border border-zinc-800 rounded-xl shadow-glass text-zinc-100 min-w-[170px] space-y-1">
          <div class="border-b border-zinc-800 pb-1 font-bold flex items-center justify-between">
            <span class="text-zinc-200">Track Segment</span>
            <span class="${isBlocked ? 'text-danger font-bold animate-pulse' : 'text-accent'}">
              ${isBlocked ? 'BLOCKED' : 'OPEN'}
            </span>
          </div>
          <div class="text-[10px] text-zinc-400 font-medium">
            <div>From: <span class="text-zinc-200 font-bold">${props.from_node}</span></div>
            <div>To: <span class="text-zinc-200 font-bold">${props.to_node}</span></div>
            <div class="text-[9px] text-zinc-500 mt-1 italic">Click track to disrupt segment</div>
          </div>
        </div>
      `;

      popupInstance.current
        ?.setLngLat(e.lngLat)
        .setHTML(html)
        .addTo(map);
    };

    map.on('mouseenter', 'outbound-tracks-layer', (e) => handleTrackMouseEnter(e, 'outbound-tracks-layer'));
    map.on('mouseleave', 'outbound-tracks-layer', () => {
      map.getCanvas().style.cursor = '';
      popupInstance.current?.remove();
    });

    map.on('mouseenter', 'inbound-tracks-layer', (e) => handleTrackMouseEnter(e, 'inbound-tracks-layer'));
    map.on('mouseleave', 'inbound-tracks-layer', () => {
      map.getCanvas().style.cursor = '';
      popupInstance.current?.remove();
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
