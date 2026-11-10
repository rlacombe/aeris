"""
Plotting utilities for dynamic mode.
"""

import logging
import math
from pathlib import Path
from typing import Optional, Union

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..config import (
    ALLOWED_POLLUTANTS,
    BASE_FONTSZ,
    CB_LABEL_SZ,
    CB_TICK_SZ,
    LABEL_SIZE,
    LEGEND_SIZE,
    TICK_SIZE,
    TITLE_SIZE,
)
from ..utils import pretty_pollutant

# Configure matplotlib
mpl.rcParams.update(
    {
        "figure.dpi": 300,
        "figure.facecolor": "white",
        "axes.edgecolor": "black",
        "axes.linewidth": 0.8,
        "axes.titleweight": "bold",
        "axes.titlesize": TITLE_SIZE,
        "axes.labelsize": LABEL_SIZE,
        "axes.grid": False,
        "font.family": "sans-serif",
        "font.size": BASE_FONTSZ,
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "legend.fontsize": LEGEND_SIZE,
        "figure.titlesize": TITLE_SIZE,
    }
)

logger = logging.getLogger(__name__)

# Optional imports with fallback
try:
    import contextily as ctx
    import geopandas as gpd

    HAS_GEO = True
except ImportError:
    HAS_GEO = False


class DynamicPlotter:
    """Plotting utilities for dynamic mode."""

    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        self.output_dir = Path(output_dir) if output_dir else None

    def _save_path(self, filename: str) -> str:
        """Resolve plot path under output_dir when configured."""
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            return str(self.output_dir / filename)
        return filename

    def plot_route_map(self, df_points: pd.DataFrame, pol: str, unit_lbl: Optional[str]) -> None:
        """
        Plot route map for a single pollutant.

        Args:
            df_points: DataFrame with GPS points and pollutant values
            pol: Pollutant name
            unit_lbl: Unit label for the pollutant
        """
        col = pol.lower()
        dfp = df_points.dropna(subset=[col]).copy()
        if len(dfp) < 2:
            logger.warning("Not enough valid points to draw a route for %s.", pol.upper())
            return

        # Sort by timestamp
        if "timestamp_utc" in dfp.columns:
            dfp = dfp.sort_values("timestamp_utc")

        # Extract coordinates and values
        xs = pd.to_numeric(dfp["longitude"], errors="coerce").to_numpy()
        ys = pd.to_numeric(dfp["latitude"], errors="coerce").to_numpy()
        vals = pd.to_numeric(dfp[col], errors="coerce").to_numpy()

        finite_vals = vals[np.isfinite(vals)]
        if finite_vals.size == 0:
            logger.warning("No finite values to color route for %s.", pol.upper())
            return

        # Color scaling
        vmin = float(np.percentile(finite_vals, 2))
        vmax = float(np.percentile(finite_vals, 98))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
            vmin, vmax = float(np.nanmin(finite_vals)), float(np.nanmax(finite_vals))
        norm = plt.Normalize(vmin, vmax)
        cmap = "RdYlGn_r"

        # Handle geospatial projection if available
        x_plot, y_plot = xs, ys
        can_project = HAS_GEO
        if can_project:
            try:
                gdf = gpd.GeoDataFrame(
                    dfp,
                    geometry=gpd.points_from_xy(dfp["longitude"], dfp["latitude"]),
                    crs="EPSG:4326",
                ).to_crs(epsg=3857)
                x_plot = gdf.geometry.x.to_numpy()
                y_plot = gdf.geometry.y.to_numpy()
            except (ImportError, ValueError, RuntimeError) as e:
                can_project = False
                logger.warning(
                    "Geospatial projection failed (%s). Falling back to lon/lat axes.", e
                )

        # Create plot
        fig, ax = plt.subplots(figsize=(9.5, 8))

        # Plot route line
        ax.plot(
            x_plot,
            y_plot,
            linestyle=(0, (6, 4)),
            color="black",
            linewidth=1.6,
            alpha=0.9,
            zorder=2,
        )

        # Plot colored points
        point_size = 90
        ax.scatter(
            x_plot,
            y_plot,
            c=vals,
            cmap=cmap,
            norm=norm,
            s=point_size,
            linewidths=0.6,
            edgecolors="black",
            alpha=0.95,
            zorder=3,
        )

        # Add start/end markers
        START_COLOR = "#2ca02c"
        END_COLOR = "#d62728"
        ring_scale = 2.2
        ring_lw = 2.0

        ax.scatter(
            [x_plot[0]],
            [y_plot[0]],
            s=point_size * ring_scale,
            facecolors="none",
            edgecolors=START_COLOR,
            linewidths=ring_lw,
            zorder=4,
        )
        ax.scatter(
            [x_plot[-1]],
            [y_plot[-1]],
            s=point_size * ring_scale,
            facecolors="none",
            edgecolors=END_COLOR,
            linewidths=ring_lw,
            zorder=4,
        )

        # Add start/end labels
        self._add_leader_label(ax, x_plot[0], y_plot[0], x_plot[1], y_plot[1], "Start", START_COLOR)
        self._add_leader_label(
            ax,
            x_plot[-1],
            y_plot[-1],
            x_plot[-1] - (x_plot[-2] - x_plot[-1]),
            y_plot[-1] - (y_plot[-2] - y_plot[-1]),
            "End",
            END_COLOR,
        )

        # Add direction arrows
        self._add_direction_arrows(ax, x_plot, y_plot, can_project)

        # Set extent and basemap
        if can_project:
            xmin, xmax = float(np.nanmin(x_plot)), float(np.nanmax(x_plot))
            ymin, ymax = float(np.nanmin(y_plot)), float(np.nanmax(y_plot))
            pad_x = max(500.0, (xmax - xmin) * 0.06)
            pad_y = max(500.0, (ymax - ymin) * 0.06)
            ax.set_xlim(xmin - pad_x, xmax + pad_x)
            ax.set_ylim(ymin - pad_y, ymax + pad_y)
            if HAS_GEO:
                try:
                    ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)
                except (ImportError, RuntimeError) as e:
                    logger.warning("Basemap fetch failed (%s). Rendering without basemap.", e)
            ax.set_axis_off()
        else:
            ax.set_xlim(min(xs), max(xs))
            ax.set_ylim(min(ys), max(ys))
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")

        # Add colorbar
        mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        cbar = plt.colorbar(mappable, ax=ax, fraction=0.03, pad=0.02)
        unit_text = f" ({unit_lbl})" if unit_lbl else ""
        cbar.set_label(
            f"{pretty_pollutant(pol)} concentration{unit_text}", labelpad=10, size=CB_LABEL_SZ
        )
        cbar.ax.tick_params(labelsize=CB_TICK_SZ)

        ax.set_title(f"Pollution Along Route — {pretty_pollutant(pol)}", pad=10, weight="bold")

        plt.tight_layout()
        fname = self._save_path(f"route_plot_{pol.lower()}.png")
        fig.savefig(fname, dpi=300, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved route plot → %s", fname)

    def _add_leader_label(
        self, ax, x0: float, y0: float, x1: float, y1: float, text: str, color: str
    ) -> None:
        """Add leader line label to plot."""
        dx, dy = (x1 - x0), (y1 - y0)
        if dx == 0 and dy == 0:
            dx, dy = 1.0, 0.0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        off_x = 16 * (1 if nx >= 0 else -1)
        off_y = 16 * (1 if ny >= 0 else -1)
        ha = "left" if off_x > 0 else "right"
        va = "bottom" if off_y > 0 else "top"
        ax.annotate(
            text,
            xy=(x0, y0),
            xytext=(off_x, off_y),
            textcoords="offset points",
            fontsize=BASE_FONTSZ,
            fontweight="bold",
            color=color,
            ha=ha,
            va=va,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor=color, alpha=0.9),
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=1.2,
                alpha=0.9,
                shrinkA=6,
                shrinkB=8,
            ),
            zorder=5,
        )

    def _add_direction_arrows(
        self, ax, x_plot: np.ndarray, y_plot: np.ndarray, can_project: bool
    ) -> None:
        """Add direction arrows along the route."""
        seg_dx = np.diff(x_plot)
        seg_dy = np.diff(y_plot)
        seg_len = np.hypot(seg_dx, seg_dy)
        total_len = float(np.sum(seg_len)) if seg_len.size else 0.0

        if total_len > 0:
            n_arrows = max(8, min(16, len(x_plot) - 1))
            targets = np.linspace(0.15 * total_len, 0.85 * total_len, n_arrows)
            cum = np.cumsum(seg_len)

            # Arrow sizing
            if can_project:
                arrow_len = 0.03 * max(
                    (np.nanmax(x_plot) - np.nanmin(x_plot)), (np.nanmax(y_plot) - np.nanmin(y_plot))
                )
                width = 0.0015
            else:
                arrow_len = 0.03 * max(
                    (np.nanmax(x_plot) - np.nanmin(x_plot)), (np.nanmax(y_plot) - np.nanmin(y_plot))
                )
                width = 0.0025

            qx, qy, qu, qv = [], [], [], []
            for t in targets:
                i = int(np.searchsorted(cum, t))
                i = max(0, min(i, len(seg_dx) - 1))
                if seg_len[i] == 0:
                    continue

                dx, dy = seg_dx[i], seg_dy[i]
                L = math.hypot(dx, dy)
                ux, uy = (dx / L, dy / L) if L else (1.0, 0.0)

                prev_cum = 0.0 if i == 0 else cum[i - 1]
                frac = (t - prev_cum) / seg_len[i]
                frac = max(0.1, min(0.9, frac))

                base_x = x_plot[i] + frac * dx
                base_y = y_plot[i] + frac * dy

                qx.append(base_x)
                qy.append(base_y)
                qu.append(ux * arrow_len)
                qv.append(uy * arrow_len)

            if qx:
                ax.quiver(
                    qx,
                    qy,
                    qu,
                    qv,
                    angles="xy",
                    scale_units="xy",
                    scale=1,
                    width=width,
                    headwidth=10,
                    headlength=10,
                    headaxislength=8,
                    color="black",
                    alpha=0.85,
                    zorder=2.7,
                )

    def plot_boxplots(self, df_all: pd.DataFrame, units_map: dict[str, Optional[str]]) -> None:
        """
        Create boxplots for all pollutants.

        Args:
            df_all: DataFrame with all pollutant measurements
            units_map: Mapping of pollutant codes to unit labels
        """
        if df_all.empty:
            logger.warning("No data available for boxplots.")
            return

        pol_cols = [p for p in ALLOWED_POLLUTANTS if p in df_all.columns]
        if not pol_cols:
            logger.warning("No pollutant columns found for boxplots.")
            return

        # Prepare data
        data_map: dict[str, np.ndarray] = {}
        for pol in pol_cols:
            s = pd.to_numeric(df_all[pol], errors="coerce").dropna()
            if not s.empty:
                data_map[pol] = s.to_numpy(dtype=float)

        if not data_map:
            logger.warning("No non-NaN measurements in raw data; skipping boxplots.")
            return

        # Color scheme
        ACCENTS = {
            "pm25": "#4E79A7",  # blue
            "pm10": "#59A14F",  # green
            "so2": "#F28E2B",  # orange
            "no2": "#E15759",  # red
            "co": "#B07AA1",  # purple
            "o3": "#76B7B2",  # teal
        }

        def accent(pol: str) -> str:
            return ACCENTS.get(pol.lower(), "#4E79A7")

        # Create layout
        n = len(data_map)
        ncols = min(3, n)
        nrows = math.ceil(n / ncols)
        fig_w = max(4.2 * ncols, 8.0)
        fig_h = max(3.8 * nrows, 4.0)

        fig, axes = plt.subplots(nrows, ncols, figsize=(fig_w, fig_h), squeeze=False)
        rng = np.random.default_rng(0)

        ordered = list(data_map.keys())
        for ax, pol in zip(axes.flat, ordered):
            vals = data_map[pol]
            m = len(vals)
            col = accent(pol)
            box_fc = col
            jitter_clr = (0, 0, 0, 0.28)

            # Set y-axis limits
            finite = vals[np.isfinite(vals)]
            if finite.size:
                lo = np.nanpercentile(finite, 1.0)
                hi = np.nanpercentile(finite, 99.0)
                pad = 0.06 * (hi - lo if hi > lo else (np.nanstd(finite) or 1.0))
                ymin = np.nanmin([lo, np.min(finite)]) - pad
                ymax = np.nanmax([hi, np.max(finite)]) + pad
                if np.isfinite(ymin) and np.isfinite(ymax) and ymin < ymax:
                    ax.set_ylim(ymin, ymax)

            # Create boxplot
            ax.boxplot(
                [vals],
                widths=0.5,
                patch_artist=True,
                whis=1.5,
                boxprops=dict(facecolor=box_fc + "33", edgecolor=col, linewidth=1.3),
                medianprops=dict(color="#111111", linewidth=1.9),
                whiskerprops=dict(color="#444444", linewidth=1.0),
                capprops=dict(color="#444444", linewidth=1.0),
                flierprops=dict(
                    marker="o",
                    markersize=4.0,
                    markerfacecolor="none",
                    markeredgecolor="#666666",
                    alpha=0.7,
                    linewidth=0.8,
                ),
            )

            # Add mean marker
            try:
                mean_val = float(np.mean(vals))
                ax.scatter(
                    [1.0],
                    [mean_val],
                    marker="D",
                    s=28,
                    facecolors="white",
                    edgecolors=col,
                    linewidths=1.0,
                    zorder=3,
                )
            except (ValueError, TypeError):
                pass

            # Add jittered points
            show = vals if m <= 1200 else vals[rng.choice(m, size=1200, replace=False)]
            xj = 1 + rng.normal(0, 0.024, size=len(show))
            ax.plot(
                xj,
                show,
                marker="o",
                linestyle="",
                alpha=0.28,
                markersize=4.0,
                color=jitter_clr,
                zorder=2,
            )

            # Configure axes
            ax.set_xlim(0.72, 1.28)
            ax.set_xticks([])
            unit = units_map.get(pol) or "native units"
            ax.set_title(pretty_pollutant(pol), pad=8, weight="bold", color="#111111")
            ax.set_ylabel(unit)
            ax.grid(axis="y", linestyle=":", linewidth=0.8, color=(0, 0, 0, 0.1))

            # Add colored border
            for side in ("top", "right", "bottom", "left"):
                ax.spines[side].set_visible(False)
            import matplotlib.patches as mpatches

            border = mpatches.Rectangle(
                (0, 0),
                1,
                1,
                transform=ax.transAxes,
                fill=False,
                linewidth=1.6,
                edgecolor=col,
                joinstyle="round",
                zorder=10,
            )
            ax.add_patch(border)

            # Add n label
            ax.text(
                0.02,
                0.96,
                f"n={m}",
                transform=ax.transAxes,
                fontsize=BASE_FONTSZ,
                va="top",
                ha="left",
                color="#333333",
            )

        # Hide unused axes
        for j in range(len(ordered), nrows * ncols):
            axes.flat[j].set_visible(False)

        # Title and layout
        fig.suptitle("Subject Exposure Distribution", weight="bold", y=0.98)
        fig.tight_layout(rect=[0, 0, 1, 0.95])

        # Save
        fname_png = self._save_path("subject_boxplots_all_pollutants.png")
        fig.savefig(fname_png, dpi=300, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved subject boxplots → %s", fname_png)
