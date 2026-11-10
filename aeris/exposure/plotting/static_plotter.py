"""
Plotting utilities for static mode.
"""

import logging
from pathlib import Path
from typing import Optional, Union

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..config import (
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
    import seaborn as sns

    sns.set_theme(context="notebook", style="whitegrid")
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


class StaticPlotter:
    """Plotting utilities for static mode."""

    def __init__(self, pollutant: str, output_dir: Optional[Union[str, Path]] = None):
        self.pollutant = pollutant
        self.output_dir = Path(output_dir) if output_dir else None

    def _save_path(self, filename: str) -> str:
        """Resolve plot path under output_dir when configured."""
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            return str(self.output_dir / filename)
        return filename

    @staticmethod
    def _distance_column(df: pd.DataFrame) -> Optional[str]:
        """Prefer primary_distance_m (IDW mode) then distance_m."""
        if "primary_distance_m" in df.columns:
            return "primary_distance_m"
        if "distance_m" in df.columns:
            return "distance_m"
        return None

    def plot_distance_qc(
        self, df_out: pd.DataFrame, distance_threshold_km: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Plot nearest-station distance per subject as a minimalist bar chart.
        - Single encoding (x-position) for distance
        - No colorbar, no per-bar text, no 1/5/10 guide lines
        - Bars are thin, neutral grey/black
        - X-axis ticks fixed to [1, 5, 10, 20, 25]
        - Figure size mirrors heatmap panels if available
        """
        logger.info("Building distance QC plot")

        dist_col = self._distance_column(df_out) if df_out is not None else None
        if df_out is None or df_out.empty or dist_col is None:
            logger.warning("No distance info available - skipping QC plot.")
            return df_out

        # One min distance per subject (km), sorted for visual scan of outliers.
        nearest_km = (
            df_out.groupby("subject_id")[dist_col].min().dropna() / 1000.0
        ).sort_values()
        if nearest_km.empty:
            logger.warning("No distances to plot - skipping.")
            return df_out

        n = len(nearest_km)
        vals = nearest_km.values

        # --- Figure size: match heatmap panels if provided; else fallback ---
        panel_size = None
        key = getattr(self, "distance_panel_key", None)  # optional: "a" or "b"
        if key == "a" and hasattr(self, "panel_figsize_a"):
            panel_size = self.panel_figsize_a
        elif key == "b" and hasattr(self, "panel_figsize_b"):
            panel_size = self.panel_figsize_b
        elif hasattr(self, "panel_figsize"):  # generic shared size
            panel_size = self.panel_figsize

        if panel_size is None:
            # Fallback: scale modestly with cohort size, but keep compact.
            fig_w = 10.0
            fig_h = max(3.8, 0.32 * n + 1.0)
            panel_size = (fig_w, fig_h)

        fig, ax = plt.subplots(figsize=panel_size)

        # --- Visuals: uniform grey/black bars, thinner height, no colorbar, no per-bar text, no ref lines ---
        bar_color = "#4a4a4a"  # neutral grey
        ax.barh(
            range(n),
            vals,
            height=0.38,  # thinner bars
            color=bar_color,
            edgecolor="black",
            linewidth=0.4,
            zorder=3,
        )

        # Y labels = subject IDs; invert so smallest distances at top.
        ax.set_yticks(range(n))
        ax.set_yticklabels(nearest_km.index.astype(str))
        ax.invert_yaxis()

        # Tick sizes to match your constants
        ax.tick_params(axis="y", labelsize=TICK_SIZE, pad=6)
        ax.tick_params(axis="x", labelsize=TICK_SIZE)

        # Subtle vertical gridlines to aid reading distances (keep minimal).
        ax.xaxis.grid(True, linestyle=":", alpha=0.35, zorder=0)

        # X-axis ticks: major every 5 km, minor every 1 km (minor ticks unlabeled)

        xmax = max(float(vals.max()) * 1.08, 25.0)
        ax.set_xlim(0.0, xmax)

        # visible tick marks (majors every 5 km, minors every 1 km)
        ax.tick_params(
            axis="x",
            which="major",
            bottom=True,
            top=False,
            direction="inout",
            length=8,
            width=1.2,
            color="black",
            labelsize=TICK_SIZE,
        )
        ax.tick_params(
            axis="x",
            which="minor",
            bottom=True,
            top=False,
            direction="inout",
            length=5,
            width=1.0,
            color="black",
        )

        ax.minorticks_on()
        ax.grid(axis="x", which="major", linestyle=":", alpha=0.35, zorder=0)
        # keep subtle vertical gridlines only for majors
        ax.grid(axis="x", which="major", linestyle=":", alpha=0.35, zorder=0)

        # Labels and title using your font constants
        ax.set_xlabel("Distance to nearest sensor (km)", labelpad=10, fontsize=LABEL_SIZE)
        ax.set_ylabel("Subject (ascending by nearest-station distance)", fontsize=LABEL_SIZE)
        ax.set_title(
            f"Nearest Monitoring Station by Participant — {pretty_pollutant(self.pollutant)}",
            pad=22,
            fontsize=TITLE_SIZE,
        )

        # Clean frame (no top/right spines).
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)

        fname = self._save_path(f"distance_plot_{self.pollutant}.png")
        fig.savefig(fname, dpi=300, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved distance QC plot → %s", fname)

        # ---- Optional distance filtering ----
        # If distance_threshold_km is provided, filter automatically; if None, don't filter
        if distance_threshold_km is None:
            logger.info("No distance filtering applied.")
            return df_out

        # Drop subjects whose nearest station exceeds threshold.
        drop_ids = nearest_km[nearest_km > distance_threshold_km].index
        if drop_ids.empty:
            logger.info("Great - everyone is within %.1f km.", distance_threshold_km)
            return df_out

        logger.info(
            "Excluding %d participants farther than %.1f km", len(drop_ids), distance_threshold_km
        )
        return df_out[~df_out["subject_id"].isin(drop_ids)]

    def plot_daily_heatmaps(self, per_subject_tidy: dict[str, list[pd.DataFrame]]) -> None:
        """
        Build two per-subject heatmaps after static run:
          • Availability: # hours with data each day (0-24), rows sorted by total hours (ascending).
          • Daily mean:   mean concentration per day, rows sorted by overall mean (ascending).
        Tries seaborn first for nicer visuals; falls back to Matplotlib if unavailable.
        """
        logger.info("Building daily heatmaps (availability + daily mean, sorted)")

        if not per_subject_tidy:
            logger.warning("No tidy per-subject data cached - skipping heatmaps.")
            return

        # Stack all tidy frames with subject_id attached, drop bad rows.
        stacks = []
        for sid, frames in per_subject_tidy.items():
            if not frames:
                continue
            dfc = pd.concat(frames, ignore_index=True)
            if dfc.empty:
                continue
            dfc["timestamp_utc"] = pd.to_datetime(dfc["timestamp_utc"], utc=True, errors="coerce")
            dfc = dfc.dropna(subset=["timestamp_utc", "value"])
            if dfc.empty:
                continue
            dfc["subject_id"] = str(sid)
            stacks.append(dfc)

        if not stacks:
            logger.warning("No usable per-subject tidy data - skipping heatmaps.")
            return

        # Build day/hour pivots; create consistent date axis range.
        all_df = pd.concat(stacks, ignore_index=True)
        all_df = all_df[all_df["parameter"].str.lower() == self.pollutant]
        if all_df.empty:
            logger.warning(
                "No measurement rows for pollutant %s - skipping heatmaps.", self.pollutant
            )
            return

        all_df["day"] = all_df["timestamp_utc"].dt.floor("D")
        subjects = sorted(all_df["subject_id"].unique(), key=lambda x: str(x))
        day_index = pd.date_range(all_df["day"].min(), all_df["day"].max(), freq="D")
        all_df["hour"] = all_df["timestamp_utc"].dt.floor("h")
        avail = (
            all_df.groupby(["subject_id", "day"])["hour"]
            .nunique()
            .unstack(1)
            .reindex(index=subjects, columns=day_index, fill_value=0)
            .clip(0, 24)
        )
        daily_mean = (
            all_df.groupby(["subject_id", "day"])["value"]
            .mean()
            .unstack(1)
            .reindex(index=subjects, columns=day_index)
        )

        # Sort rows for readability (low → high availability/mean).
        avail_row_order = avail.sum(axis=1).sort_values(ascending=True).index
        mean_row_order = daily_mean.mean(axis=1, skipna=True).sort_values(ascending=True).index

        avail_sorted = avail.loc[avail_row_order]
        mean_sorted = daily_mean.loc[mean_row_order]

        # Robust vmax against outliers for daily-mean colormap.
        flat_vals = mean_sorted.values.flatten()
        flat_vals = flat_vals[np.isfinite(flat_vals)]
        vmax = float(np.percentile(flat_vals, 98)) if flat_vals.size else 100.0
        if not np.isfinite(vmax) or vmax <= 0:
            vmax = 100.0

        # Unit label (if any) for colorbar.
        unit = None
        if "unit" in all_df.columns and not all_df["unit"].isna().all():
            unit = all_df["unit"].dropna().iloc[0]

        # Cap figure size so dpi*inches stays under matplotlib's 2^16 pixel limit.
        # Wide date spans (e.g. mixed months across a year) would otherwise create
        # enormous canvases and crash with "Image size ... is too large".
        max_w_in, max_h_in = 20.0, 15.0
        fig_w = min(max(10.0, len(day_index) * 0.25), max_w_in)
        fig_h_av = min(max(4.0, len(avail_sorted) * 0.35), max_h_in)
        fig_h_mu = min(max(4.0, len(mean_sorted) * 0.35), max_h_in)
        save_dpi = 150 if len(day_index) > 90 else 300

        # Prefer seaborn rendering, then fallback if import/plot fails.
        try:
            import seaborn as sns

            # Availability heatmap
            fig1, ax1 = plt.subplots(figsize=(fig_w, fig_h_av))
            sns.heatmap(
                avail_sorted,
                ax=ax1,
                cmap="Blues",
                vmin=0,
                vmax=24,
                cbar_kws={"label": "Hours with measurements (0-24)"},
                linewidths=0,
                square=False,
            )
            ax1.set_title(
                f"Available Hourly Measurements - {pretty_pollutant(self.pollutant)}",
                fontsize=TITLE_SIZE,
            )
            ax1.set_xlabel("Date")
            ax1.set_ylabel("Subject (ascending by total hours with data)")

            # ---- FIX TICKS AND ALIGNMENT ----
            ncols = len(day_index)
            nrows = avail_sorted.shape[0]
            xpos = np.arange(ncols) + 0.5
            ypos = np.arange(nrows) + 0.5

            # Label every few dates but tick every column
            step = max(1, ncols // 20)
            xlabels = [
                d.strftime("%b %d") if i % step == 0 else "" for i, d in enumerate(day_index)
            ]
            ax1.set_xlim(0, ncols)
            ax1.set_xticks(xpos)
            ax1.set_xticklabels(xlabels, rotation=90, ha="center")

            # Label every subject row
            ax1.set_ylim(nrows, 0)
            ax1.set_yticks(ypos)
            ax1.set_yticklabels([str(s) for s in avail_sorted.index])

            # Make tick marks visible
            ax1.tick_params(
                axis="x",
                which="major",
                bottom=True,
                top=False,
                direction="inout",
                length=7,
                width=1.2,
            )
            ax1.tick_params(
                axis="y",
                which="major",
                left=True,
                right=False,
                direction="inout",
                length=7,
                width=1.2,
            )

            # ---- UNIFORM GRID (equal-weight lines) ----
            # ensure limits are at integer boundaries
            ax1.set_xlim(0, ncols)
            ax1.set_ylim(nrows, 0)

            # draw one line per boundary so thickness is uniform
            for x in np.arange(0, ncols + 1):
                ax1.axvline(x, color="white", linewidth=0.5, zorder=3)
            for y in np.arange(0, nrows + 1):
                ax1.axhline(y, color="white", linewidth=0.5, zorder=3)

            fig1.subplots_adjust(bottom=0.18)

            cbar1 = ax1.collections[0].colorbar
            cbar1.set_label("Hours with measurements (0-24)", labelpad=10, size=CB_LABEL_SZ)
            cbar1.ax.tick_params(labelsize=CB_TICK_SZ)
            plt.tight_layout()
            fname1 = self._save_path(f"availability_heatmap_{self.pollutant}.png")
            fig1.savefig(fname1, dpi=save_dpi, bbox_inches="tight")
            plt.close(fig1)
            logger.info("Saved availability heatmap → %s", fname1)

            # Daily-mean heatmap
            fig2, ax2 = plt.subplots(figsize=(fig_w, fig_h_mu))
            sns.heatmap(
                mean_sorted,
                ax=ax2,
                cmap="RdYlGn_r",
                vmin=0,
                vmax=vmax,
                cbar_kws={"label": f"Daily mean concentration{f' ({unit})' if unit else ''}"},
                linewidths=0,
                square=False,
            )
            ax2.set_title(
                f"Daily Mean - {pretty_pollutant(self.pollutant)}",
                fontsize=TITLE_SIZE,
            )
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Subject (ascending by overall mean)")

            # ---- FIX TICKS AND ALIGNMENT ----
            ncols = len(day_index)
            nrows = mean_sorted.shape[0]
            xpos = np.arange(ncols) + 0.5
            ypos = np.arange(nrows) + 0.5

            # Label every few dates but tick every column
            step = max(1, ncols // 20)
            xlabels = [
                d.strftime("%b %d") if i % step == 0 else "" for i, d in enumerate(day_index)
            ]
            ax2.set_xlim(0, ncols)
            ax2.set_xticks(xpos)
            ax2.set_xticklabels(xlabels, rotation=90, ha="center")

            # Label every subject row
            ax2.set_ylim(nrows, 0)
            ax2.set_yticks(ypos)
            ax2.set_yticklabels([str(s) for s in mean_sorted.index])

            # Make tick marks visible
            ax2.tick_params(
                axis="x",
                which="major",
                bottom=True,
                top=False,
                direction="inout",
                length=7,
                width=1.2,
            )
            ax2.tick_params(
                axis="y",
                which="major",
                left=True,
                right=False,
                direction="inout",
                length=7,
                width=1.2,
            )

            # ---- UNIFORM GRID (equal-weight lines) ----
            ax2.set_xlim(0, ncols)
            ax2.set_ylim(nrows, 0)

            for x in np.arange(0, ncols + 1):
                ax2.axvline(x, color="white", linewidth=0.5, zorder=3)
            for y in np.arange(0, nrows + 1):
                ax2.axhline(y, color="white", linewidth=0.5, zorder=3)

            fig2.subplots_adjust(bottom=0.18)

            cbar2 = ax2.collections[0].colorbar
            cbar2.set_label(
                f"Daily mean concentration{f' ({unit})' if unit else ''}",
                labelpad=10,
                size=CB_LABEL_SZ,
            )
            cbar2.ax.tick_params(labelsize=CB_TICK_SZ)
            plt.tight_layout()
            fname2 = self._save_path(f"daily_mean_heatmap_{self.pollutant}.png")
            fig2.savefig(fname2, dpi=save_dpi, bbox_inches="tight")
            plt.close(fig2)
            logger.info("Saved daily mean heatmap → %s", fname2)

        except (ImportError, RuntimeError, TypeError, ValueError) as _sns_err:
            # Fallback to matplotlib (grid/image API) if seaborn is unavailable.
            logger.warning(
                "seaborn not available or failed (%s) - using matplotlib fallback.", _sns_err
            )

            # Availability
            fig1, ax1 = plt.subplots(figsize=(fig_w, fig_h_av))
            data1 = np.ma.masked_invalid(avail_sorted.values.astype(float))
            m1 = ax1.imshow(data1, aspect="auto", cmap="Blues", vmin=0, vmax=24)
            ax1.set_title(
                f"Available Hourly Measurements - {pretty_pollutant(self.pollutant)}",
                fontsize=TITLE_SIZE,
            )
            ax1.set_xlabel("Date")
            ax1.set_ylabel("Subject (ascending by total hours with data)")

            # center ticks at column centers
            xpos = np.arange(len(day_index)) + 0.5
            step = max(1, len(day_index) // 20)
            ax1.set_xlim(0, len(day_index))
            ax1.set_xticks(xpos)
            ax1.set_xticklabels(
                [d.strftime("%b %d") if i % step == 0 else "" for i, d in enumerate(day_index)],
                rotation=90,
            )

            # ensure tick marks render visibly
            ax1.xaxis.set_ticks_position("bottom")
            ax1.tick_params(
                axis="x",
                which="major",
                bottom=True,
                top=False,
                direction="inout",
                length=7,
                width=1.2,
            )
            fig1.subplots_adjust(bottom=0.18)

            ax1.tick_params(axis="x", which="major", length=4, direction="out")
            ax1.set_yticks(range(len(avail_sorted.index)))
            ax1.set_yticklabels(avail_sorted.index)
            cbar1 = plt.colorbar(m1, ax=ax1, fraction=0.03, pad=0.02)
            cbar1.set_label("Hours with measurements (0-24)", labelpad=10, size=CB_LABEL_SZ)
            cbar1.ax.tick_params(labelsize=CB_TICK_SZ)
            ax1.grid(which="major", color="white", linestyle="-", linewidth=0.3, alpha=0.15)
            plt.tight_layout()
            fname1 = self._save_path(f"availability_heatmap_{self.pollutant}.png")
            fig1.savefig(fname1, dpi=save_dpi, bbox_inches="tight")
            plt.close(fig1)
            logger.info("Saved availability heatmap → %s", fname1)

            # Daily mean
            fig2, ax2 = plt.subplots(figsize=(fig_w, fig_h_mu))
            data = np.ma.masked_invalid(mean_sorted.values.astype(float))
            im2 = ax2.imshow(data, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=vmax)
            ax2.set_title(f"Daily Mean by Subject and Day - {pretty_pollutant(self.pollutant)}")
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Subject (sorted by overall mean ↑)")
            xpos = np.arange(len(day_index))
            ax2.set_xticks(xpos)
            ax2.set_xticklabels(
                [d.strftime("%b %d") if i % step == 0 else "" for i, d in enumerate(day_index)],
                rotation=90,
            )
            ax2.tick_params(axis="x", which="major", length=4, direction="out")
            ax2.set_yticks(range(len(mean_sorted.index)))
            ax2.set_yticklabels(mean_sorted.index)
            cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.03, pad=0.02)
            cbar2.set_label(
                f"Daily mean concentration{f' ({unit})' if unit else ''}",
                labelpad=10,
                size=CB_LABEL_SZ,
            )
            cbar2.ax.tick_params(labelsize=CB_TICK_SZ)
            ax2.grid(which="major", color="white", linestyle="-", linewidth=0.3, alpha=0.15)
            plt.tight_layout()
            fname2 = self._save_path(f"daily_mean_heatmap_{self.pollutant}.png")
            fig2.savefig(fname2, dpi=save_dpi, bbox_inches="tight")
            plt.close(fig2)
            logger.info("Saved daily mean heatmap → %s", fname2)
