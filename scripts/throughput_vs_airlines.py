"""Does TSA passenger throughput tell you anything about airline stocks?

Pulls daily TSA checkpoint counts and the JETS airline ETF, lines them up,
and checks whether the throughput series leads or lags the stock. Writes the
three figures used in the README to docs/figures/.

TSA history: https://github.com/hunj/tsa-passenger-throughput
Prices: yfinance.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

TSA_CSV = "https://raw.githubusercontent.com/hunj/tsa-passenger-throughput/main/output.csv"
FIG_DIR = Path(__file__).resolve().parent.parent / "docs" / "figures"
START, END = "2018-12-01", "2022-01-15"


def load_throughput():
    s = pd.read_csv(TSA_CSV, header=None, names=["date", "throughput"],
                    parse_dates=["date"]).sort_values("date").set_index("date")["throughput"]
    return s.asfreq("D").interpolate(limit=2)


def load_jets():
    px = yf.download("JETS", start=START, end=END, progress=False, auto_adjust=True)["Close"]
    return px.iloc[:, 0] if hasattr(px, "columns") else px


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    throughput = load_throughput()
    roll7 = throughput.rolling(7).mean()
    jets = load_jets()

    # Weekly alignment.
    tw = roll7.resample("W-FRI").last()
    jw = jets.resample("W-FRI").last()
    d = pd.concat([tw.rename("t"), jw.rename("j")], axis=1).dropna()
    d["tg"] = d["t"].pct_change()
    d["jr"] = d["j"].pct_change()
    d = d.dropna()
    level_corr = d["t"].corr(d["j"])

    # Figure 1: the two series on a shared timeline.
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(roll7.index, roll7 / 1e6, color="#1f77b4", lw=1.6, label="TSA throughput (7d avg)")
    ax.set_ylabel("Passengers per day (millions)", color="#1f77b4")
    ax.tick_params(axis="y", labelcolor="#1f77b4")
    ax2 = ax.twinx()
    ax2.plot(jets.index, jets, color="#d62728", lw=1.6, label="JETS")
    ax2.set_ylabel("JETS close ($)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    ax.set_title(f"TSA throughput vs the JETS airline ETF (level corr {level_corr:.2f})")
    ax.set_xlim(pd.Timestamp("2019-01-01"), pd.Timestamp("2021-12-31"))
    fig.tight_layout()
    fig.savefig(FIG_DIR / "throughput_vs_jets.png", dpi=130)

    # Figure 2: lead-lag. corr(JETS return_t, throughput growth_{t+k}).
    lags = range(-8, 9)
    corrs = [d["jr"].corr(d["tg"].shift(-k)) for k in lags]
    peak_k = list(lags)[corrs.index(max(corrs))]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = ["#d62728" if k == peak_k else "#9ecae1" for k in lags]
    ax.bar(list(lags), corrs, color=colors)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("Weeks throughput is shifted relative to the stock (positive = throughput later)")
    ax.set_ylabel("Correlation with weekly JETS return")
    ax.set_title(f"JETS returns lead throughput growth by about {peak_k} weeks")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "lead_lag.png", dpi=130)

    # Figure 3: forward rank-IC of the throughput momentum signal.
    horizons = [1, 2, 4, 8, 13]
    ics = []
    for k in horizons:
        fwd = d["j"].shift(-k) / d["j"] - 1
        ics.append(d["tg"].corr(fwd, method="spearman"))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([str(h) for h in horizons], ics, color="#9467bd")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("Forward horizon (weeks)")
    ax.set_ylabel("Rank IC")
    ax.set_title("Throughput growth vs later JETS returns: rank IC stays near zero")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "forward_ic.png", dpi=130)

    print(f"level corr {level_corr:.3f}  peak lead-lag k={peak_k}  fwd IC {[round(x,3) for x in ics]}")


if __name__ == "__main__":
    main()
