"use client";

import type { FeatureCollection, Position } from "geojson";
import { divIcon, type LatLngBoundsExpression } from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, Marker, Rectangle, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import { bounds, frame, layout, type Box } from "@/lib/boxes";
import { number } from "@/lib/format";
import type { Area, Level, Region, Subregion } from "@/lib/types";
import { LEVEL_COLOR, LEVEL_LABEL } from "./status";

interface Props {
  regions: Region[];
  /** The region zoomed into, with its subregions once they have loaded; null for the world view. */
  focus: { region: Region; subregions: Subregion[] | null } | null;
  selected: string | null;
  onSelectRegion: (id: string) => void;
  onSelectSubregion: (id: string) => void;
  onBack: () => void;
  /** Which classification colours the map: live conditions, or the last completed season. */
  levelOf: (area: Area) => Level;
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
// Side, in degrees of longitude, of the largest and smallest region squares on the world view.
const REGION_MAX_SIDE = 26;
const REGION_MIN_SIDE = 6;

/** Moves the map when the view changes; the map itself is only created once. */
function Fit({ to }: { to: LatLngBoundsExpression }) {
  const map = useMap();
  const key = JSON.stringify(to);
  useEffect(() => {
    map.flyToBounds(to, { padding: [28, 28], duration: 0.6 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);
  return null;
}

// Leaflet's divIcon takes markup, so names from the API are escaped before they go in.
const escapeHtml = (text: string) =>
  text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);

// A subregion's name is written inside its square once the square is this wide on screen.
const LABEL_MIN_PX = 44;

/**
 * Names inside the subregion squares. A label is exactly as wide as its square, so
 * neighbours cannot run into each other; squares too small to hold one answer on hover.
 */
function BoxLabels({ areas, boxes }: { areas: Area[]; boxes: Box[] }) {
  const map = useMap();
  // Pixel sizes depend on the zoom, and are wrong while a zoom animation is running.
  const [zoom, setZoom] = useState<number | null>(map.getZoom());
  useMapEvents({ zoomstart: () => setZoom(null), zoomend: () => setZoom(map.getZoom()) });
  if (zoom === null) return null;

  return (
    <>
      {areas.map((area, i) => {
        const [[south, west], [north, east]] = bounds(boxes[i]);
        const side = Math.round(map.project([south, east], zoom).x - map.project([south, west], zoom).x);
        if (side < LABEL_MIN_PX) return null;
        const fontSize = side < 58 ? 9 : side < 76 ? 10 : 11.5;
        // A word that cannot fit on one line would be cut in half; leave that square to its hover label.
        const longestWord = Math.max(...area.name.split(/\s+/).map((word) => word.length));
        if (longestWord * fontSize * 0.62 > side - 6) return null;
        const mt = number(area.food_mt, area.food_mt < 10 ? 1 : 0);
        const icon = divIcon({
          className: "box-label",
          iconSize: [side, side],
          html: `<div style="font-size:${fontSize}px"><b>${escapeHtml(area.name)}</b>${
            side < 58 ? "" : `<small>${mt} Mt</small>`
          }</div>`,
        });
        return (
          <Marker
            key={`${area.id}-${side}`}
            position={[(south + north) / 2, (west + east) / 2]}
            icon={icon}
            interactive={false}
            keyboard={false}
          />
        );
      })}
    </>
  );
}

export default function MonsoonMap({ regions, focus, selected, onSelectRegion, onSelectSubregion, onBack, levelOf }: Props) {
  const regionBoxes = useMemo(
    () => layout(regions, { maxSide: REGION_MAX_SIDE, minSide: REGION_MIN_SIDE }),
    [regions],
  );
  const subregions = focus?.subregions ?? null;
  const subregionBoxes = useMemo(() => (subregions ? layout(subregions) : []), [subregions]);

  const zoomed = focus !== null && subregions !== null && subregionBoxes.length > 0;
  const areas: Area[] = zoomed ? subregions : regions;
  const boxes = zoomed ? subregionBoxes : regionBoxes;

  return (
    <div className="map-frame">
      <MapContainer
        className="map"
        bounds={VIEW}
        maxBounds={WORLD}
        maxBoundsViscosity={1}
        zoomSnap={0.25}
        minZoom={0.75}
        maxZoom={7}
        scrollWheelZoom={false}
        attributionControl={false}
      >
        <Fit to={zoomed ? frame(subregionBoxes) : VIEW} />
        <GeoJSON data={countries} interactive={false} pathOptions={{ className: "land" }} />
        {areas.map((area, i) => {
          const level = levelOf(area);
          const muted = level === "off_season" || level === "unknown";
          const isSelected = area.id === selected;
          const select = () => (zoomed ? onSelectSubregion(area.id) : onSelectRegion(area.id));
          return (
            <Rectangle
              key={`${area.id}-${level}-${isSelected}`}
              bounds={bounds(boxes[i])}
              pathOptions={{
                color: LEVEL_COLOR[level],
                weight: isSelected ? 3.5 : 2,
                dashArray: muted ? "5 5" : undefined,
                fillColor: LEVEL_COLOR[level],
                fillOpacity: muted ? 0.12 : isSelected ? 0.5 : 0.35,
              }}
              eventHandlers={{ click: select }}
            >
              {/* Regions carry a standing label; subregions are named inside their squares and answer on hover. */}
              <Tooltip
                key={zoomed ? "hover" : "label"}
                permanent={!zoomed}
                interactive={!zoomed}
                sticky={zoomed}
                direction="top"
                offset={[0, -2]}
                className="region-label"
                eventHandlers={{ click: select }}
              >
                {area.name.replace(" (India)", "")}
                <small>
                  {LEVEL_LABEL[level]} · {number(area.food_mt, area.food_mt < 10 ? 1 : 0)} Mt
                </small>
              </Tooltip>
            </Rectangle>
          );
        })}
        {zoomed ? <BoxLabels areas={areas} boxes={boxes} /> : null}
      </MapContainer>
      {focus ? (
        <button className="button map-back" onClick={onBack}>
          ← All regions
        </button>
      ) : null}
      {focus && !zoomed ? <div className="map-note">Loading subregions…</div> : null}
    </div>
  );
}
