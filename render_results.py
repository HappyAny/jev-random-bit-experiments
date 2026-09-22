"""Render the observed results with matplotlib; no generative imagery or API calls."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent


def main():
    rows = json.loads((ROOT / "derived/summary.json").read_text(encoding="utf-8"))["conditions"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    fig = plt.figure(figsize=(14, 8), facecolor="#f5f3ed")
    fig.text(.055, .92, "2,000 requests. 1,999 zeros. 1 one.", fontsize=30, weight="bold", color="#152b37")
    fig.text(.055, .864, "TypeSafe Jev 1.13.0  |  Fair-bit prompt via Choice  |  22 September 2026", fontsize=14, color="#50636d")
    ax = fig.add_axes([.225, .27, .385, .48], facecolor="#f5f3ed")
    for index, row in enumerate(rows):
        y = len(rows) - 1 - index
        ax.plot([row["p0_min"], row["p0_max"]], [y,y], color="#bbcbc9", linewidth=8, solid_capstyle="round")
        ax.scatter(row["p0_mean"], y, s=75, color="#126d64", zorder=3)
        ax.text(.77, y, f'{row["p0_mean"]:.5f}', va="center", fontsize=12, color="#152b37")
    ax.axvline(.5, color="#a85245", linestyle="--", linewidth=1.4)
    ax.set_yticks(range(len(rows)), labels=[row["label"] for row in reversed(rows)], fontsize=13)
    ax.tick_params(axis="y", length=0, pad=15)
    ax.set_xlim(.46,.85)
    ax.set_ylim(-.55,len(rows)-.45)
    ax.set_xticks([.5,.6,.7], labels=["0.50","0.60","0.70"], fontsize=11)
    ax.set_xlabel("Returned P(0): dot = mean; line = observed min-max", fontsize=11, labelpad=14)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="x", colors="#50636d")
    fig.text(.676,.792,"CALLS",fontsize=12,weight="bold",color="#50636d")
    fig.text(.771,.792,"ZEROS",fontsize=12,weight="bold",color="#50636d")
    fig.text(.878,.792,"ONES",fontsize=12,weight="bold",color="#50636d")
    for index,row in enumerate(rows):
        y = .27 + .48 * ((len(rows)-1-index+.55) / (len(rows)+.1))
        for x, key in [(.676,"n"),(.771,"zeros"),(.886,"ones")]:
            fig.text(x,y,f'{row[key]:,}',fontsize=17,va="center",color="#a85245" if key == "ones" and row[key] else "#152b37",weight="bold" if key == "ones" else "normal")
    fig.text(.055,.145,"Choice returns the highest-probability option. It does not sample from the distribution.",fontsize=15,color="#152b37",weight="bold")
    fig.text(.055,.10,"One model, fixed option order, sequential conditions. Descriptive counts; no claim about internal entropy.",fontsize=11,color="#50636d")
    fig.text(.055,.06,"Code + raw data: github.com/HappyAny/jev-random-bit-experiments",fontsize=12,color="#126d64")
    output = ROOT / "figures"
    output.mkdir(exist_ok=True)
    for extension in ["png","svg"]:
        fig.savefig(output / ("results."+extension),dpi=160,facecolor=fig.get_facecolor())
    svg = output / "results.svg"
    svg.write_bytes(("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n").encode("utf-8"))
    plt.close(fig)
    print("Wrote figures/results.png and figures/results.svg")


if __name__ == "__main__":
    main()
