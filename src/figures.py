# src/figures.py
"""Gera as figuras usadas no relatório e na apresentação (reports/figs/)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .tools import seasonality_evidence, channel_variants

OUT = Path("reports/figs")

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"  # slot 1 - blue
SERIES_2 = "#eb6834"  # slot 2 - orange
CRIT = "#e34948"
GOOD = "#008300"


def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def seasonality_chart(path: str = "reports/figs/sazonalidade.png") -> str:
    ev = seasonality_evidence()
    serie = ev["serie"]
    days = [r["d"][-5:] for r in serie]
    n_rows = [r["n_rows"] for r in serie]
    ma = [r["ma7_prev"] for r in serie]

    fig, ax = plt.subplots(figsize=(9.2, 4.0), dpi=200)
    _style(ax)

    ax.plot(days, n_rows, color=SERIES_1, linewidth=2, label="Linhas/dia (staging)")
    ax.plot(days, ma, color=SERIES_2, linewidth=2, linestyle="--", label="Média móvel 7d")

    idx = {d: i for i, d in enumerate(days)}
    for day, color, label, dy in (
        ("07-09", GOOD, "09/07 — feriado SP\nqueda de NEGÓCIO\n(0 duplicatas)", -22),
        ("07-15", CRIT, "15/07 — double ingestion\nBUG de dados\n(26 duplicatas)", 12),
    ):
        if day not in idx:
            continue
        i = idx[day]
        ax.scatter([days[i]], [n_rows[i]], s=90, color=color, zorder=5,
                   edgecolors=SURFACE, linewidths=2)
        ax.annotate(
            label, xy=(days[i], n_rows[i]), xytext=(days[i], n_rows[i] + dy),
            ha="center", va="top" if dy < 0 else "bottom",
            fontsize=8.5, color=INK, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=color, linewidth=1.4),
        )

    ax.set_title("Julho/2025 — separando sazonalidade de negócio de bug de dados",
                 fontsize=12, color=INK, fontweight="bold", pad=14, loc="left")
    ax.set_ylabel("linhas/dia", fontsize=9, color=INK_2)
    ax.set_ylim(0, max(n_rows) * 1.42)
    ax.set_xticks(days[::3])
    leg = ax.legend(frameon=False, fontsize=9, loc="upper left", ncols=2)
    for t in leg.get_texts():
        t.set_color(INK_2)

    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def channel_chart(path: str = "reports/figs/canais.png") -> str:
    cv = channel_variants()
    variants = sorted(cv["variantes"], key=lambda v: v["n"], reverse=True)
    labels = [v["channel_raw"] for v in variants]
    values = [v["n"] for v in variants]
    colors = [
        SERIES_1 if v["channel_norm"] in cv["dominio_esperado"] else SERIES_2
        for v in variants
    ]

    fig, ax = plt.subplots(figsize=(9.2, 3.8), dpi=200)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], height=0.62)
    for bar, val in zip(bars, values[::-1]):
        ax.text(val + 12, bar.get_y() + bar.get_height() / 2, f"{val:,}".replace(",", "."),
                va="center", fontsize=8.5, color=INK_2)

    ax.set_title("Label drift: 11 rótulos brutos para 3 canais reais",
                 fontsize=12, color=INK, fontweight="bold", pad=14, loc="left")
    ax.set_xlim(0, max(values) * 1.18)
    handles = [
        plt.Line2D([], [], marker="s", linestyle="", markersize=9, color=SERIES_1,
                   label="já no domínio após normalização inicial"),
        plt.Line2D([], [], marker="s", linestyle="", markersize=9, color=SERIES_2,
                   label="fora do domínio — exige CASE WHEN no patch"),
    ]
    leg = ax.legend(handles=handles, frameon=False, fontsize=8.5, loc="lower right")
    for t in leg.get_texts():
        t.set_color(INK_2)

    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def gate_chart(path: str = "reports/figs/gate.png") -> str:
    """Duas execuções do DataEngineer: o gate quantitativo em ação."""
    labels = ["Staging\n(antes)", "Execução 1\npatch rejeitado", "Execução 2\npatch aprovado"]
    values = [1442, 3655, 0]
    colors = [INK_2, CRIT, GOOD]

    fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=200)
    _style(ax)
    bars = ax.bar(labels, values, color=colors, width=0.52)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 90, f"{val:,}".replace(",", "."),
                ha="center", fontsize=12, fontweight="bold", color=INK)

    ax.annotate("gate barrou\n(2,5× pior)", xy=(1, 3655), xytext=(1.42, 3050),
                fontsize=9, color=CRIT, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=CRIT, linewidth=1.4))

    ax.set_title("Linhas com canal fora do domínio — o gate em ação",
                 fontsize=12, color=INK, fontweight="bold", pad=14, loc="left")
    ax.set_ylabel("linhas", fontsize=9, color=INK_2)
    ax.set_ylim(0, 4400)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def main() -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [seasonality_chart(), channel_chart(), gate_chart()]
    for p in paths:
        print(f"[ok] {p}")
    return paths


if __name__ == "__main__":
    main()