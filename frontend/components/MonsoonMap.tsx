"use client";

import type { FeatureCollection, Position } from "geojson";
import type { LatLngBoundsExpression } from "leaflet";
import { GeoJSON, MapContainer, Rectangle, Tooltip } from "react-leaflet";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import type { Level, Region } from "@/lib/types";
import { LEVEL_COLOR, LEVEL_LABEL } from "./status";

interface Props {
  regions: Region[];
  selected: string | null;
  onSelect: (id: string) => void;
  /** Which classification colours the map: live conditions, or the last completed season. */
  levelOf: (region: Region) => Level;
}

function bounds(region: Region): LatLngBoundsExpression {
  const ring = region.geometry.coordinates[0];
  const lons = ring.map((c) => c[0]);
  const lats = ring.map((c) => c[1]);
  return [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ];
}

// Natural Earth country outlines, bundled with the app: no tile server, API key or third-party request.
const topology = world as unknown as Topology;
const countries = feature(topology, topology.objects.countries) as unknown as FeatureCollection;

// A ring that crosses the antimeridian (Russia, Fiji) would otherwise be drawn as a
// streak across the whole map. Shifting its western points east keeps it in one piece.
function unwrap(ring: Position[]): Position[] {
  const lons = ring.map((p) => p[0]);
  if (Math.max(...lons) - Math.min(...lons) <= 180) return ring;
  return ring.map(([lon, lat]) => [lon < 0 ? lon + 360 : lon, lat]);
}
for (const { geometry } of countries.features) {
  if (geometry.type === "Polygon") geometry.coordinates = geometry.coordinates.map(unwrap);
  if (geometry.type === "MultiPolygon") {
    geometry.coordinates = geometry.coordinates.map((polygon) => polygon.map(unwrap));
  }
}

const WORLD: LatLngBoundsExpression = [
  [-60, -180],
  [80, 180],
];
// Frames all six regions.
const VIEW: LatLngBoundsExpression = [
  [-38, -80],
  [50, 155],
];

export default function MonsoonMap({ regions, selected, onSelect, levelOf }: Props) {
  return (
    <MapContainer
      className="map"
      bounds={VIEW}
      maxBounds={WORLD}
      maxBoundsViscosity={1}
      zoomSnap={0.25}
      minZoom={0.75}
      maxZoom={5}
      scrollWheelZoom={false}
      attributionControl={false}
    >
      <GeoJSON data={countries} interactive={false} pathOptions={{ className: "land" }} />
      {regions.map((region) => {
        const level = levelOf(region);
        const muted = level === "off_season" || level === "unknown";
        const isSelected = region.id === selected;
        return (
          <Rectangle
            key={`${region.id}-${level}-${isSelected}`}
            bounds={bounds(region)}
            pathOptions={{
              color: LEVEL_COLOR[level],
              weight: isSelected ? 3.5 : 2,
              dashArray: muted ? "5 5" : undefined,
              fillColor: LEVEL_COLOR[level],
              fillOpacity: muted ? 0.12 : isSelected ? 0.5 : 0.35,
            }}
            eventHandlers={{ click: () => onSelect(region.id) }}
          >
            <Tooltip
              permanent
              interactive
              direction="top"
              offset={[0, -2]}
              className="region-label"
              eventHandlers={{ click: () => onSelect(region.id) }}
            >
              {region.name.replace(" (India)", "")}
              <small>{LEVEL_LABEL[level]}</small>
            </Tooltip>
          </Rectangle>
        );
      })}
    </MapContainer>
  );
}
