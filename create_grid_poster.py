#!/usr/bin/env python3
"""
GridToPoster
============
Create beautiful country-level electrical transmission grid posters from
OpenStreetMap `power=line` features.

This is a focused rewrite of a city street-network poster workflow: instead of
fetching roads around a city point, it geocodes a country boundary, downloads
OpenStreetMap power-line geometries inside that boundary, styles them by voltage,
and renders a print-ready poster.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover - optional progress-bar dependency
    def tqdm(iterable, *args, **kwargs):
        return iterable

import geopandas as gpd
import pandas as pd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from matplotlib import patheffects
from matplotlib.font_manager import FontProperties
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon, box
from shapely.ops import unary_union

CACHE_DIR = Path("cache")
POSTERS_DIR = Path("posters")
THEMES_DIR = Path("themes")
FILE_ENCODING = "utf-8"
MM_PER_INCH = 25.4

PAPER_SIZES: dict[str, tuple[float, float]] = {
    # ISO 216 A-series (portrait, width × height in mm)
    "a5": (148.0, 210.0),
    "a4": (210.0, 297.0),
    "a3": (297.0, 420.0),
    "a2": (420.0, 594.0),
    "a1": (594.0, 841.0),
    "a0": (841.0, 1189.0),
    # ANSI / North American sizes
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
    "tabloid": (279.4, 431.8),
}

NATURAL_EARTH_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_50m_admin_0_countries.geojson"
)
NATURAL_EARTH_PATH = CACHE_DIR / "ne_50m_admin_0_countries.geojson"
CONTINENT_NAMES = {
    "africa",
    "antarctica",
    "asia",
    "europe",
    "north america",
    "oceania",
    "south america",
}

# Aggregate region names that combine multiple Natural Earth continents.
CONTINENT_AGGREGATES: dict[str, frozenset[str]] = {
    "global": frozenset({"africa", "asia", "europe", "north america", "south america"}),
}

CACHE_DIR.mkdir(exist_ok=True)
POSTERS_DIR.mkdir(exist_ok=True)
THEMES_DIR.mkdir(exist_ok=True)

DEFAULT_THEMES: dict[str, dict[str, str]] = {
    "electric_midnight": {
        "name": "Electric Midnight",
        "description": "Deep navy background with cool transmission glow.",
        "bg": "#06111F",
        "text": "#EAF4FF",
        "subtext": "#8FB7D8",
        "boundary": "#1D3C5A",
        "line_unknown": "#355B7C",
        "line_low": "#6FA4C8",
        "line_mid": "#A7D8FF",
        "line_high": "#F6E7A7",
        "line_extra": "#FFFFFF",
        "fade": "#06111F",
    },
    "paper_grid": {
        "name": "Paper Grid",
        "description": "Warm gallery-print styling for dense networks.",
        "bg": "#F4EFE6",
        "text": "#1D1D1D",
        "subtext": "#6B625A",
        "boundary": "#D9CCBA",
        "line_unknown": "#CAB99D",
        "line_low": "#7F9A8B",
        "line_mid": "#436F75",
        "line_high": "#A65C2E",
        "line_extra": "#5B2016",
        "fade": "#F4EFE6",
    },
    "blackout": {
        "name": "Blackout",
        "description": "High-contrast black-and-white technical poster.",
        "bg": "#050505",
        "text": "#FFFFFF",
        "subtext": "#A5A5A5",
        "boundary": "#252525",
        "line_unknown": "#454545",
        "line_low": "#888888",
        "line_mid": "#D8D8D8",
        "line_high": "#FFFFFF",
        "line_extra": "#FFFFFF",
        "fade": "#050505",
    },
}


@dataclass(frozen=True)
class Theme:
    name: str
    description: str
    bg: str
    text: str
    subtext: str
    boundary: str
    line_unknown: str
    line_low: str
    line_mid: str
    line_high: str
    line_extra: str
    fade: str

    @classmethod
    def from_dict(cls, raw: dict[str, str]) -> "Theme":
        required = {
            "name",
            "description",
            "bg",
            "text",
            "subtext",
            "boundary",
            "line_unknown",
            "line_low",
            "line_mid",
            "line_high",
            "line_extra",
            "fade",
        }
        missing = sorted(required.difference(raw))
        if missing:
            raise ValueError(f"Theme is missing keys: {', '.join(missing)}")
        return cls(**{key: raw[key] for key in required})


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized or "poster"


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str).encode(FILE_ENCODING)
    return hashlib.sha256(raw).hexdigest()[:24]


def cache_get(key: str) -> Any | None:
    path = CACHE_DIR / f"{key}.pkl"
    if not path.exists():
        return None
    with path.open("rb") as handle:
        return pickle.load(handle)


def cache_set(key: str, value: Any) -> None:
    path = CACHE_DIR / f"{key}.pkl"
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def ensure_builtin_themes() -> None:
    """Write bundled themes to disk only when they do not already exist."""
    for theme_id, data in DEFAULT_THEMES.items():
        path = THEMES_DIR / f"{theme_id}.json"
        if not path.exists():
            path.write_text(json.dumps(data, indent=2), encoding=FILE_ENCODING)


def list_themes() -> None:
    ensure_builtin_themes()
    print("Available themes:\n")
    for path in sorted(THEMES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding=FILE_ENCODING))
        except json.JSONDecodeError:
            print(f"- {path.stem}: invalid JSON")
            continue
        print(f"- {path.stem}: {data.get('name', path.stem)}")
        if data.get("description"):
            print(f"  {data['description']}")


def load_theme(theme_id: str) -> Theme:
    ensure_builtin_themes()
    path = THEMES_DIR / f"{theme_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Theme '{theme_id}' not found in {THEMES_DIR}/")
    return Theme.from_dict(json.loads(path.read_text(encoding=FILE_ENCODING)))


def _load_natural_earth_countries() -> gpd.GeoDataFrame:
    if not NATURAL_EARTH_PATH.exists():
        import urllib.request

        print(f"Downloading Natural Earth admin-0 dataset → {NATURAL_EARTH_PATH}")
        urllib.request.urlretrieve(NATURAL_EARTH_URL, NATURAL_EARTH_PATH)
    return gpd.read_file(NATURAL_EARTH_PATH)


def _continent_boundary(continent: str) -> gpd.GeoDataFrame:
    countries = _load_natural_earth_countries()
    key = continent.lower()
    aggregate = CONTINENT_AGGREGATES.get(key)
    if aggregate is not None:
        match = countries["CONTINENT"].str.lower().isin(aggregate)
    else:
        match = countries["CONTINENT"].str.lower() == key

    if key == "global":
        # Oceania is excluded from the aggregate above; pull in Australia, Papua
        # New Guinea, and New Zealand explicitly so the poster covers them
        # without dragging in the wider Pacific.
        match = match | countries["ISO_A3"].isin(["AUS", "PNG", "NZL"])

    subset = countries[match]
    if subset.empty:
        raise RuntimeError(f"No countries found for continent '{continent}' in Natural Earth")
    merged = unary_union(subset.geometry)

    if key == "global":
        # Clip the global aggregate to a tight bounding box:
        #   • north - Alaska's northernmost point (~71.4°N), to drop the empty
        #     Canadian Arctic, Greenland's interior, and Svalbard.
        #   • east - New Zealand's easternmost main-island longitude (~178.5°E),
        #     to drop Russia's far-eastern Chukotka sliver that otherwise pushes
        #     the viewport out to the antimeridian.
        us = countries[countries["ISO_A3"] == "USA"]
        nz = countries[countries["ISO_A3"] == "NZL"]
        if us.empty or nz.empty:
            raise RuntimeError(
                "Natural Earth dataset is missing USA or NZL - cannot build global clip"
            )
        north_lat = float(us.total_bounds[3])
        east_lon = float(nz.total_bounds[2])
        merged = merged.intersection(box(-180, -90, east_lon, north_lat))

    return gpd.GeoDataFrame({"name": [continent]}, geometry=[merged], crs=countries.crs)


def keep_main_landmass(geometry: Any) -> Any:
    """Drop disjoint polygons that are far from the main landmass.

    Geocoded country boundaries include overseas territories - e.g. Aruba and
    Curaçao for the Netherlands, French Guiana and Réunion for France. We keep
    the largest polygon plus any polygon whose envelope intersects a 3×-inflated
    bounding box of the largest one. This preserves close-by islands such as
    Northern Ireland, Corsica, or Japan's main islands.
    """
    if not isinstance(geometry, MultiPolygon):
        return geometry

    polygons = list(geometry.geoms)
    if len(polygons) <= 1:
        return geometry

    largest = max(polygons, key=lambda p: p.area)
    minx, miny, maxx, maxy = largest.bounds
    width = max(maxx - minx, 0.01)
    height = max(maxy - miny, 0.01)
    region = box(minx - width, miny - height, maxx + width, maxy + height)

    kept = [p for p in polygons if region.intersects(p)]
    if len(kept) == 1:
        return kept[0]
    return MultiPolygon(kept)


def load_boundary_from_geojson(path: Path, name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise RuntimeError(f"Boundary file '{path}' contains no features")
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        raise RuntimeError(f"Boundary file '{path}' contains no polygonal geometry")
    if gdf.crs is None:
        print(f"Boundary file '{path}' has no CRS - assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    merged = unary_union(gdf.geometry)
    return gpd.GeoDataFrame({"name": [name]}, geometry=[merged], crs="EPSG:4326")


def get_country_boundary(country: str, mainland_only: bool = True, use_cache: bool = True) -> gpd.GeoDataFrame:
    key = cache_key("boundary_v3", country, mainland_only)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached boundary for {country}")
            return cached

    if country.lower() in CONTINENT_NAMES or country.lower() in CONTINENT_AGGREGATES:
        print(f"Building continent boundary from Natural Earth: {country}")
        boundary = _continent_boundary(country)
    else:
        print(f"Geocoding country boundary: {country}")
        boundary = ox.geocode_to_gdf(country)
        boundary = boundary[boundary.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if boundary.empty:
            raise RuntimeError(f"Could not resolve a country boundary for '{country}'")
        if mainland_only:
            merged = unary_union(boundary.geometry)
            filtered = keep_main_landmass(merged)
            before = len(merged.geoms) if isinstance(merged, MultiPolygon) else 1
            after = len(filtered.geoms) if isinstance(filtered, MultiPolygon) else 1
            if after < before:
                print(
                    f"Mainland-only: dropped {before - after} outlying polygon(s); "
                    "pass --include-outlying to keep them"
                )
            boundary = gpd.GeoDataFrame(
                {"name": [country]}, geometry=[filtered], crs=boundary.crs
            )

    cache_set(key, boundary)
    return boundary


def power_tag_values(include_minor_lines: bool, include_cables: bool) -> list[str]:
    values = ["line"]
    if include_minor_lines:
        values.append("minor_line")
    if include_cables:
        values.append("cable")
    return values


def make_query_tiles(
    boundary: gpd.GeoDataFrame,
    tile_size_km: float,
    render_crs: str,
    sea_buffer_km: float = 0.0,
) -> gpd.GeoDataFrame:
    """Split a large country boundary into smaller projected tiles for Overpass."""
    if tile_size_km <= 0:
        raise ValueError("tile_size_km must be greater than zero")

    boundary_projected = boundary.to_crs(render_crs)
    country_geom = unary_union(boundary_projected.geometry)
    if not isinstance(country_geom, (Polygon, MultiPolygon)):
        raise RuntimeError("Boundary geometry is not polygonal")

    if sea_buffer_km > 0:
        # Inflate the land polygon by a sea margin so tiles cover water between
        # islands and short stretches of coast. Without this, power=cable ways
        # on the seabed (inter-island and cross-border interconnectors) are
        # never fetched from Overpass.
        country_geom = country_geom.buffer(sea_buffer_km * 1000)

    minx, miny, maxx, maxy = country_geom.bounds
    tile_size_m = tile_size_km * 1000
    tiles = []

    x_steps = np.arange(minx, maxx, tile_size_m)
    y_steps = np.arange(miny, maxy, tile_size_m)

    for x0 in x_steps:
        for y0 in y_steps:
            candidate = box(x0, y0, min(x0 + tile_size_m, maxx), min(y0 + tile_size_m, maxy))
            if not candidate.intersects(country_geom):
                continue
            clipped = candidate.intersection(country_geom)
            if not clipped.is_empty:
                tiles.append(clipped)

    if not tiles:
        raise RuntimeError("Could not create query tiles from the country boundary")

    return gpd.GeoDataFrame(geometry=tiles, crs=render_crs).to_crs("EPSG:4326")


def fetch_power_features(
    country: str,
    boundary: gpd.GeoDataFrame,
    include_minor_lines: bool = False,
    include_cables: bool = False,
    tile_size_km: float = 200,
    render_crs: str = "EPSG:8857",
    sea_buffer_km: float = 0.0,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    values = power_tag_values(include_minor_lines, include_cables)
    key = cache_key("power_features", country, values, tile_size_km, render_crs, sea_buffer_km)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached power features for {country}")
            return cached

    tiles = make_query_tiles(
        boundary,
        tile_size_km=tile_size_km,
        render_crs=render_crs,
        sea_buffer_km=sea_buffer_km,
    )
    print(f"Downloading OSM power features: power={values} across {len(tiles):,} tiles")

    frames: list[gpd.GeoDataFrame] = []
    for tile_number, tile_geom in enumerate(tiles.geometry, start=1):
        print(f"  Tile {tile_number:,}/{len(tiles):,}")
        try:
            features = ox.features_from_polygon(tile_geom, tags={"power": values})
        except Exception as exc:
            print(f"  Warning: skipping tile {tile_number:,} after Overpass error: {exc}")
            continue

        if features.empty:
            continue

        features = features.reset_index()
        line_features = features[features.geometry.type.isin(["LineString", "MultiLineString"])]
        if line_features.empty:
            continue

        keep_cols = [
            col
            for col in ["element", "element_type", "osmid", "id", "power", "voltage", "name", "operator", "geometry"]
            if col in line_features.columns
        ]
        frames.append(gpd.GeoDataFrame(line_features[keep_cols], geometry="geometry", crs="EPSG:4326"))

    if not frames:
        raise RuntimeError(
            f"No line geometries found for power={values} in {country}. "
            "Try a smaller --tile-size-km or rerun later if Overpass is busy."
        )

    combined = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")
    id_cols = [col for col in ["element", "element_type", "osmid", "id"] if col in combined.columns]
    if id_cols:
        combined = combined.drop_duplicates(subset=id_cols)
    else:
        combined = combined.drop_duplicates(subset=["geometry"])

    keep_cols = [col for col in ["power", "voltage", "name", "operator", "geometry"] if col in combined.columns]
    combined = combined[keep_cols]
    cache_set(key, combined)
    return combined


def parse_voltage_to_kv(value: Any) -> float | None:
    """Parse OSM voltage tags into kV, using pragmatic cleanup for poster styling."""
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (list, tuple, set)):
        parsed = [parse_voltage_to_kv(item) for item in value]
        parsed = [item for item in parsed if item is not None]
        return max(parsed) if parsed else None

    text = str(value).lower().replace(" ", "")
    tokens = re.split(r"[;,/|]+", text)
    values: list[float] = []
    for token in tokens:
        if not token:
            continue
        multiplier = 1.0
        if token.endswith("kv"):
            multiplier = 1.0
            token = token[:-2]
        elif token.endswith("v"):
            multiplier = 0.001
            token = token[:-1]

        token = token.replace(",", ".")
        match = re.search(r"\d+(?:\.\d+)?", token)
        if not match:
            continue

        number = float(match.group(0))
        if multiplier == 1.0 and number > 1200:
            # OSM voltage is usually in volts, e.g. 380000; convert to kV.
            number = number / 1000.0
        else:
            number = number * multiplier
        values.append(number)

    return max(values) if values else None


def compute_line_styles(
    lines: gpd.GeoDataFrame,
    theme: Theme,
    *,
    linewidth_scale: float = 1.0,
    fade_unknown: bool = False,
) -> dict[str, np.ndarray]:
    """Vectorized per-row (color, linewidth, alpha) for the whole frame.

    Lets render_poster batch segments into one matplotlib call per style group
    instead of one call per segment.
    """
    kv = lines["voltage_kv"].astype("float64").to_numpy()
    n = len(lines)
    colors = np.full(n, theme.line_unknown, dtype=object)
    linewidths = np.full(n, 0.30)
    alphas = np.full(n, 0.55)

    mask = kv >= 60
    colors[mask] = theme.line_low
    linewidths[mask] = 0.48
    alphas[mask] = 0.75
    mask = kv >= 150
    colors[mask] = theme.line_mid
    linewidths[mask] = 0.72
    alphas[mask] = 0.86
    mask = kv >= 300
    colors[mask] = theme.line_high
    linewidths[mask] = 1.05
    alphas[mask] = 0.92
    mask = kv >= 500
    colors[mask] = theme.line_extra
    linewidths[mask] = 1.35
    alphas[mask] = 0.95

    is_cable = np.zeros(n, dtype=bool)
    if "power" in lines.columns:
        power = lines["power"].to_numpy()
        minor = power == "minor_line"
        colors[minor] = theme.line_low
        linewidths[minor] = 0.50
        alphas[minor] = 0.75

        # Cables (underground/submarine) are often HVDC interconnectors and
        # frequently lack voltage tags — make them legible regardless.
        is_cable = power == "cable"
        no_voltage = is_cable & np.isnan(kv)
        colors[no_voltage] = theme.line_mid
        linewidths[is_cable] = np.maximum(linewidths[is_cable] * 1.6, 0.85)
        alphas[is_cable] = np.maximum(alphas[is_cable], 0.9)

    if fade_unknown:
        # Untagged-voltage lines are mostly noise at continent/global extent —
        # fade them strongly so they recede without disappearing. Cables are
        # exempt because HVDC interconnectors frequently lack a voltage tag.
        unknown = np.isnan(kv) & ~is_cable
        alphas[unknown] *= 0.35

    if linewidth_scale != 1.0:
        # Keep the heaviest tier within a sensible real-world width on the
        # paper; floor at 0.15 pt so hairlines stay visible.
        linewidths = np.maximum(linewidths * linewidth_scale, 0.15)

    return {"_color": colors, "_linewidth": linewidths, "_alpha": alphas}


def prepare_lines(
    lines: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    output_crs: str,
    cable_sea_buffer_km: float = 0.0,
) -> gpd.GeoDataFrame:
    boundary_projected = boundary.to_crs(output_crs)
    lines_projected = lines.to_crs(output_crs)

    if "power" in lines_projected.columns and cable_sea_buffer_km > 0:
        is_cable = lines_projected["power"] == "cable"
    else:
        is_cable = pd.Series(False, index=lines_projected.index)

    def _safe_clip(frame: gpd.GeoDataFrame, mask: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        try:
            return gpd.clip(frame, mask)
        except Exception:
            # Clipping may fail with invalid upstream geometries. A poster can
            # still be rendered without clipping because the Overpass polygon
            # query already constrained the result set.
            return frame

    parts: list[gpd.GeoDataFrame] = []
    land_lines = lines_projected[~is_cable]
    if not land_lines.empty:
        parts.append(_safe_clip(land_lines, boundary_projected))
    cable_lines = lines_projected[is_cable]
    if not cable_lines.empty:
        cable_mask = gpd.GeoDataFrame(
            geometry=boundary_projected.geometry.buffer(cable_sea_buffer_km * 1000),
            crs=output_crs,
        )
        parts.append(_safe_clip(cable_lines, cable_mask))

    clipped = gpd.GeoDataFrame(
        pd.concat(parts, ignore_index=True) if parts else lines_projected.iloc[0:0],
        geometry="geometry",
        crs=output_crs,
    )

    clipped = clipped.explode(ignore_index=True)
    clipped = clipped[clipped.geometry.type.isin(["LineString", "MultiLineString"])]
    clipped = clipped[~clipped.geometry.is_empty]
    if clipped.empty:
        raise RuntimeError("Power-line geometries became empty after projection/clipping")

    clipped["voltage_kv"] = clipped.get("voltage", None).apply(parse_voltage_to_kv)
    clipped["sort_voltage"] = clipped["voltage_kv"].fillna(0)
    return clipped.sort_values("sort_voltage")


def set_country_extent(ax: plt.Axes, boundary: gpd.GeoDataFrame, width: float, height: float, padding: float) -> None:
    minx, miny, maxx, maxy = boundary.total_bounds
    xmid = (minx + maxx) / 2
    ymid = (miny + maxy) / 2
    xspan = max(maxx - minx, 1.0)
    yspan = max(maxy - miny, 1.0)

    xspan *= 1 + padding
    yspan *= 1 + padding

    poster_aspect = width / height
    data_aspect = xspan / yspan

    if data_aspect > poster_aspect:
        yspan = xspan / poster_aspect
    else:
        xspan = yspan * poster_aspect

    ax.set_xlim(xmid - xspan / 2, xmid + xspan / 2)
    ax.set_ylim(ymid - yspan / 2, ymid + yspan / 2)


def add_gradient_fade(ax: plt.Axes, color: str, where: str, zorder: int = 10) -> None:
    vals = np.linspace(0, 1, 256).reshape(-1, 1)
    gradient = np.hstack((vals, vals))
    rgb = mcolors.to_rgb(color)
    rgba = np.zeros((256, 4))
    rgba[:, :3] = rgb

    if where == "bottom":
        rgba[:, 3] = np.linspace(1, 0, 256)
        y0, y1 = 0.00, 0.28
    elif where == "top":
        rgba[:, 3] = np.linspace(0, 1, 256)
        y0, y1 = 0.72, 1.00
    else:
        raise ValueError("where must be 'top' or 'bottom'")

    cmap = mcolors.ListedColormap(rgba)
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    yspan = ylim[1] - ylim[0]
    ax.imshow(
        gradient,
        extent=[xlim[0], xlim[1], ylim[0] + yspan * y0, ylim[0] + yspan * y1],
        aspect="auto",
        cmap=cmap,
        zorder=zorder,
        origin="lower",
    )


def spaced_upper(text: str) -> str:
    return " ".join(text.upper()) if len(text) <= 20 else text.upper()


def output_path(country: str, theme_id: str, fmt: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return POSTERS_DIR / f"{slugify(country)}_grid_{theme_id}_{timestamp}.{fmt}"


def render_poster(
    country: str,
    display_country: str,
    boundary: gpd.GeoDataFrame,
    lines: gpd.GeoDataFrame,
    theme: Theme,
    width: float,
    height: float,
    outputs: list[tuple[Path, str]],
    dpi: int,
    include_metadata: bool,
    title_size: float | None = None,
    include_minor_lines: bool = False,
    subtitle: str | None = None,
    padding: float = 0.10,
    large_scale: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(width, height), facecolor=theme.bg)
    ax.set_facecolor(theme.bg)
    ax.set_position((0, 0, 1, 1))
    ax.axis("off")

    boundary.plot(ax=ax, facecolor="none", edgecolor=theme.boundary, linewidth=0.7, alpha=0.9, zorder=1)

    linewidth_scale = 1.0
    halo_extra_pt = 0.0
    if large_scale:
        # boundary is already in the projected (meter-based) CRS at this point.
        minx, miny, maxx, maxy = boundary.total_bounds
        x_span_km = max((maxx - minx), 1.0) / 1000.0
        y_span_km = max((maxy - miny), 1.0) / 1000.0
        km_per_pt = max(x_span_km / (width * 72.0), y_span_km / (height * 72.0))
        target_ground_km = 8.0
        heaviest_lw_pt = 1.35
        linewidth_scale = min(1.0, target_ground_km / (heaviest_lw_pt * km_per_pt))
        halo_extra_pt = 0.4
        print(
            f"Large-scale mode: km/pt ≈ {km_per_pt:.1f}, "
            f"linewidth scale = {linewidth_scale:.2f}, halo = {halo_extra_pt:.2f} pt"
        )

    styled = lines.assign(**compute_line_styles(
        lines,
        theme,
        linewidth_scale=linewidth_scale,
        fade_unknown=large_scale,
    ))
    grouped = styled.groupby(["_color", "_linewidth", "_alpha"], sort=False)
    group_iter = tqdm(
        grouped,
        total=grouped.ngroups,
        desc="Rendering line groups",
        unit="group",
        leave=True,
    )
    for (color, linewidth, alpha), group in group_iter:
        zorder = 2 + group["sort_voltage"].max() / 1000.0
        plot_kwargs: dict[str, Any] = dict(
            ax=ax,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            zorder=zorder,
        )
        if halo_extra_pt > 0:
            # Fully-opaque bg-colored stroke under each line creates visual
            # separation at dense crossings; the original colored line is
            # drawn on top by withStroke.
            plot_kwargs["path_effects"] = [
                patheffects.withStroke(
                    linewidth=linewidth + halo_extra_pt * 2,
                    foreground=theme.bg,
                    alpha=1.0,
                )
            ]
        group.plot(**plot_kwargs)

    ax.set_aspect("equal", adjustable="box")
    set_country_extent(ax, boundary, width, height, padding=padding)

    add_gradient_fade(ax, theme.fade, "bottom", zorder=10)
    add_gradient_fade(ax, theme.fade, "top", zorder=10)

    scale = min(width, height) / 12
    title_pt = title_size if title_size is not None else 48 * scale
    font_main = FontProperties(family="DejaVu Sans", weight="bold", size=title_pt)
    font_sub = FontProperties(family="DejaVu Sans", weight="normal", size=15 * scale)
    font_meta = FontProperties(family="DejaVu Sans Mono", weight="normal", size=8.5 * scale)

    total_length_km = float(lines.geometry.length.sum()) / 1000.0
    high_voltage_length_km = float(lines.loc[lines["voltage_kv"].fillna(0) >= 150].geometry.length.sum()) / 1000.0
    if subtitle is None:
        subtitle = "ELECTRICAL GRID" if include_minor_lines else "ELECTRICAL TRANSMISSION GRID"
    metadata = f"{datetime.now().year} · {total_length_km:,.0f} km of power lines"
    if high_voltage_length_km:
        metadata += f" · {high_voltage_length_km:,.0f} km ≥150 kV"

    ax.text(
        0.5,
        0.130,
        spaced_upper(display_country),
        transform=ax.transAxes,
        ha="center",
        va="center",
        color=theme.text,
        fontproperties=font_main,
        zorder=20,
    )
    ax.text(
        0.5,
        0.090,
        subtitle,
        transform=ax.transAxes,
        ha="center",
        va="center",
        color=theme.subtext,
        fontproperties=font_sub,
        zorder=20,
    )
    if include_metadata:
        ax.text(
            0.5,
            0.064,
            metadata,
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=theme.subtext,
            alpha=0.85,
            fontproperties=font_meta,
            zorder=20,
        )

    ax.plot(
        [0.39, 0.61],
        [0.112, 0.112],
        transform=ax.transAxes,
        color=theme.text,
        linewidth=0.8 * scale,
        alpha=0.85,
        zorder=20,
    )
    ax.text(
        0.985,
        0.018,
        "© OpenStreetMap contributors, MapYourGrid, Open Energy Transition · CC BY 4.0",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        color=theme.subtext,
        alpha=0.65,
        fontproperties=font_meta,
        zorder=20,
    )

    for output_file, fmt in outputs:
        save_kwargs: dict[str, Any] = {
            "format": fmt,
            "facecolor": theme.bg,
            "bbox_inches": None,
            "pad_inches": 0,
        }
        if fmt == "png":
            save_kwargs["dpi"] = dpi

        output_file.parent.mkdir(exist_ok=True)
        fig.savefig(output_file, **save_kwargs)
        print(f"Saved poster: {output_file}")
    plt.close(fig)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create country electrical transmission grid posters from OpenStreetMap power=line data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--country", "-C", required=False, help="Country or region name resolvable by Nominatim")
    parser.add_argument(
        "--boundary-geojson",
        type=Path,
        help="Load the boundary polygon(s) from a local GeoJSON file instead of geocoding via Nominatim. "
             "All polygonal features in the file are dissolved into a single boundary.",
    )
    parser.add_argument("--display-country", help="Text to print on the poster")
    parser.add_argument(
        "--subtitle",
        help="Override the poster subtitle (default: 'ELECTRICAL TRANSMISSION GRID', "
             "or 'ELECTRICAL GRID' with --include-minor-lines)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.10,
        help="Fractional padding around the boundary bounds. Lower = more zoomed in "
             "(e.g. 0 = tight fit, -0.05 = crop slightly into the bounds, 0.20 = looser).",
    )
    parser.add_argument(
        "--large-scale",
        action="store_true",
        help="Tune styling for continent/global posters: scale linewidths so the "
             "heaviest line stays roughly 8 km wide on the ground, halo each line "
             "against the background so dense crossings remain legible, and drop "
             "power=minor_line / strongly fade unknown-voltage clutter.",
    )
    parser.add_argument("--theme", "-t", default="paper_grid", help="Theme ID from themes/")
    parser.add_argument("--list-themes", action="store_true", help="List available themes and exit")
    parser.add_argument("--include-minor-lines", action="store_true", help="Also fetch power=minor_line")
    parser.add_argument(
        "--include-cables",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch power=cable features (underground/submarine). Pass --no-include-cables to skip.",
    )
    parser.add_argument(
        "--cable-sea-buffer-km",
        type=float,
        default=200.0,
        help="When --include-cables is on, inflate the boundary by this many kilometers "
             "over water so submarine cables between islands and to neighboring countries "
             "are queried from Overpass and survive coastline clipping. Set to 0 to disable.",
    )
    parser.add_argument(
        "--include-outlying",
        action="store_true",
        help="Keep overseas territories and other polygons far from the main landmass. "
             "By default only the mainland (and nearby islands) is rendered.",
    )
    parser.add_argument(
        "--paper-size",
        choices=sorted(PAPER_SIZES),
        help="Preset paper size in portrait orientation. Overrides --width and --height. "
             "Use --landscape to flip orientation.",
    )
    parser.add_argument("--width", "-W", type=float, default=297.0, help="Poster width in millimeters (default: A3 short side)")
    parser.add_argument("--height", "-H", type=float, default=420.0, help="Poster height in millimeters (default: A3 long side)")
    parser.add_argument(
        "--landscape",
        action="store_true",
        help="Render in landscape (horizontal) orientation. Swaps width and height if width < height.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Raster output DPI")
    parser.add_argument(
        "--title-size",
        type=float,
        default=None,
        help="Title font size in points. Defaults to an auto-scaled value based on poster size.",
    )
    parser.add_argument(
        "--tile-size-km",
        type=float,
        default=200,
        help="Overpass query tile size in kilometers. Use smaller values for very large countries or busy servers.",
    )
    parser.add_argument(
        "--format",
        "-f",
        nargs="+",
        choices=["png", "svg", "pdf"],
        default=["png", "svg"],
        help="Output format(s). Pass multiple values to write the poster in several formats at once.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path. When set, only a single file is written and its format is inferred from the extension.",
    )
    parser.add_argument(
        "--crs",
        default="EPSG:3857",
        help="Projection used for rendering. EPSG:3857 Pseudo-Mercator works well for country posters.",
    )
    parser.add_argument("--hide-metadata", action="store_true", help="Do not print segment counts on poster")
    parser.add_argument(
        "--export-geojson",
        nargs="?",
        const="",
        default=None,
        help="Also save all transmission lines as a single GeoJSON (WGS84). "
             "Optionally pass a path; otherwise written next to the poster.",
    )
    parser.add_argument("--verbose-osmnx", action="store_true", help="Print OSMnx request logs")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore cached boundaries and OSM power features on this run. "
             "Fresh results are still written to the cache for future runs.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)

    if args.list_themes:
        list_themes()
        return 0
    if not args.country:
        print("Error: --country is required unless --list-themes is used", file=sys.stderr)
        return 2

    ox.settings.use_cache = not args.no_cache
    ox.settings.log_console = bool(args.verbose_osmnx)
    ox.settings.requests_timeout = 180
    # Keep OSMnx's own guard reasonably high: we explicitly tile the country
    # boundary below, so this setting is only a secondary safety net.
    ox.settings.max_query_area_size = max(ox.settings.max_query_area_size, (args.tile_size_km * 1000) ** 2 * 2)

    theme = load_theme(args.theme)
    display_country = args.display_country or args.country

    if args.paper_size:
        width_mm, height_mm = PAPER_SIZES[args.paper_size]
    else:
        width_mm, height_mm = args.width, args.height
    if args.landscape and width_mm < height_mm:
        width_mm, height_mm = height_mm, width_mm
    width, height = width_mm / MM_PER_INCH, height_mm / MM_PER_INCH

    if args.boundary_geojson:
        print(f"Loading boundary from {args.boundary_geojson}")
        boundary_wgs84 = load_boundary_from_geojson(args.boundary_geojson, args.country)
    else:
        boundary_wgs84 = get_country_boundary(
            args.country,
            mainland_only=not args.include_outlying,
            use_cache=not args.no_cache,
        )
    cable_buffer_km = args.cable_sea_buffer_km if args.include_cables else 0.0
    raw_lines = fetch_power_features(
        country=args.country,
        boundary=boundary_wgs84,
        include_minor_lines=args.include_minor_lines,
        include_cables=args.include_cables,
        tile_size_km=args.tile_size_km,
        render_crs=args.crs,
        sea_buffer_km=cable_buffer_km,
        use_cache=not args.no_cache,
    )

    boundary_projected = boundary_wgs84.to_crs(args.crs)
    lines_projected = prepare_lines(
        raw_lines, boundary_wgs84, args.crs, cable_sea_buffer_km=cable_buffer_km
    )

    if args.large_scale and "power" in lines_projected.columns:
        before = len(lines_projected)
        lines_projected = lines_projected[lines_projected["power"] != "minor_line"].copy()
        dropped = before - len(lines_projected)
        if dropped:
            print(f"Large-scale mode: dropped {dropped:,} minor_line segments")

    if args.output:
        fmt = (args.output.suffix.lstrip(".") or args.format[0]).lower()
        if fmt not in {"png", "svg", "pdf"}:
            print(f"Error: cannot infer output format from {args.output} (suffix '{args.output.suffix}')", file=sys.stderr)
            return 2
        outputs = [(args.output, fmt)]
    else:
        outputs = [(output_path(args.country, args.theme, f), f) for f in args.format]

    if args.export_geojson is not None:
        if args.export_geojson:
            geojson_path = Path(args.export_geojson)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            geojson_path = POSTERS_DIR / f"{slugify(args.country)}_grid_{timestamp}.geojson"
        geojson_path.parent.mkdir(parents=True, exist_ok=True)
        export = lines_projected.to_crs("EPSG:4326").drop(columns=["sort_voltage"], errors="ignore")
        export.to_file(geojson_path, driver="GeoJSON")
        print(f"Saved GeoJSON: {geojson_path}")

    print(f"Rendering {len(lines_projected):,} line segments with theme '{theme.name}'")
    render_poster(
        country=args.country,
        display_country=display_country,
        boundary=boundary_projected,
        lines=lines_projected,
        theme=theme,
        width=width,
        height=height,
        outputs=outputs,
        dpi=args.dpi,
        include_metadata=not args.hide_metadata,
        title_size=args.title_size,
        include_minor_lines=args.include_minor_lines,
        subtitle=args.subtitle,
        padding=args.padding,
        large_scale=args.large_scale,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
