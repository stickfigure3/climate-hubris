import type { Area } from "./types";

/**
 * Map boxes sized by food production.
 *
 * Each region or subregion is drawn as a square whose area is proportional to the cereals
 * it grows, centred on the box its rainfall is measured over. Squares that would overlap are
 * nudged apart, so a box marks roughly where a place is and exactly how much it grows.
 *
 * Layout runs in Web Mercator "degrees" (longitude, and latitude stretched the way the map
 * stretches it), so a square here is a square on screen and equal areas look equal.
 */

export interface Box {
  id: string;
  /** Centre and side length in Mercator degrees. */
  x: number;
  y: number;
  side: number;
}

export type Bounds = [[number, number], [number, number]];

const mercator = (lat: number) => (180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const latitude = (y: number) => (360 / Math.PI) * Math.atan(Math.exp((y * Math.PI) / 180)) - 90;

interface Extent {
  west: number;
  east: number;
  south: number;
  north: number;
}

/** The area's rainfall box in Mercator degrees. */
function extent(area: Area): Extent {
  const ring = area.geometry.coordinates[0];
  const lons = ring.map((c) => c[0]);
  const lats = ring.map((c) => c[1]);
  return {
    west: Math.min(...lons),
    east: Math.max(...lons),
    south: mercator(Math.min(...lats)),
    north: mercator(Math.max(...lats)),
  };
}

/** Push overlapping squares apart along the axis that needs the smaller move, biggest stays put most. */
function separate(boxes: Box[], home: Box[], gap: number): Box[] {
  const out = boxes.map((b) => ({ ...b }));
  for (let pass = 0; pass < 400; pass++) {
    // A weak pull home keeps the layout geographic; it is switched off at the end so no overlap survives.
    const pull = pass < 300 ? 0.02 : 0;
    out.forEach((b, i) => {
      b.x += (home[i].x - b.x) * pull;
      b.y += (home[i].y - b.y) * pull;
    });
    let moved = false;
    for (let i = 0; i < out.length; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const a = out[i];
        const b = out[j];
        const reach = (a.side + b.side) / 2 + gap;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const overlapX = reach - Math.abs(dx);
        const overlapY = reach - Math.abs(dy);
        if (overlapX <= 0 || overlapY <= 0) continue;
        moved = true;
        const shareA = b.side ** 2 / (a.side ** 2 + b.side ** 2);
        if (overlapX < overlapY) {
          const sign = dx >= 0 ? 1 : -1;
          a.x -= sign * overlapX * shareA;
          b.x += sign * overlapX * (1 - shareA);
        } else {
          const sign = dy >= 0 ? 1 : -1;
          a.y -= sign * overlapY * shareA;
          b.y += sign * overlapY * (1 - shareA);
        }
      }
    }
    if (!moved && pull === 0) break;
  }
  return out;
}

/**
 * Squares for a set of areas. The largest producer gets `maxSide`; the others scale by the
 * square root of their production, and none shrinks below `minSide` so it can still be clicked.
 * Without `maxSide`, the squares together fill `fill` of the ground the areas cover.
 */
export function layout(areas: Area[], options: { maxSide?: number; minSide?: number; fill?: number } = {}): Box[] {
  if (areas.length === 0) return [];
  const extents = areas.map(extent);
  const width = Math.max(...extents.map((e) => e.east)) - Math.min(...extents.map((e) => e.west));
  const height = Math.max(...extents.map((e) => e.north)) - Math.min(...extents.map((e) => e.south));
  const largest = Math.max(...areas.map((a) => a.food_mt), 1e-9);
  const total = areas.reduce((sum, a) => sum + a.food_mt, 0) || 1;
  const maxSide = options.maxSide ?? Math.sqrt(((options.fill ?? 0.4) * width * height * largest) / total);
  const minSide = options.minSide ?? Math.min(width, height) * 0.07;

  const home = areas.map((area, i) => ({
    id: area.id,
    x: (extents[i].west + extents[i].east) / 2,
    y: (extents[i].south + extents[i].north) / 2,
    side: Math.max(minSide, maxSide * Math.sqrt(area.food_mt / largest)),
  }));
  return separate(home, home, Math.min(width, height) * 0.012);
}

export function bounds(box: Box): Bounds {
  const half = box.side / 2;
  return [
    [latitude(box.y - half), box.x - half],
    [latitude(box.y + half), box.x + half],
  ];
}

/** The frame that holds every box, for zooming the map to a region's subregions. */
export function frame(boxes: Box[]): Bounds {
  const all = boxes.map(bounds);
  return [
    [Math.min(...all.map((b) => b[0][0])), Math.min(...all.map((b) => b[0][1]))],
    [Math.max(...all.map((b) => b[1][0])), Math.max(...all.map((b) => b[1][1]))],
  ];
}
