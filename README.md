- collectors for free public datasets, each turned into a factor and tested against stock returns
- the one i chased: tsa publishes daily airport checkpoint counts, free, next morning, and airlines trade on passenger demand. can you see the recovery in throughput before the stock moves?
- inspired by [katona, painter, patatoukas & zeng, "on the capital market consequences of big data: evidence from outer space"](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3222741): count cars in retailer lots from satellite, trade ahead of earnings. tsa counts are the same shape, a public physical-activity proxy for a sector's revenue
- data: daily tsa throughput back to 2019 plus the jets airline etf, aligned weekly
- other sources wired up: opentable diners, fred building permits, usgs earthquakes, uk grid carbon, box office, cloudflare traffic, zillow rents. airlines went furthest

![tsa throughput and jets, 2019 to 2021, both crater in march 2020 and recover together](docs/figures/throughput_vs_jets.png)

- levels correlate 0.83, looks tradeable, isn't

![weekly jets returns vs throughput growth shifted by k weeks, peak at three weeks](docs/figures/lead_lag.png)

- cross-correlation peaks at +3 weeks: jets moves about three weeks before throughput, the stock led the data (jets doubled on vaccine news in late 2020 while checkpoints were still empty; throughput kept climbing after jets peaked in 2021)

![rank ic of throughput growth vs later jets returns, near zero at every horizon](docs/figures/forward_ic.png)

- forward rank ic wanders around zero across 1 to 13 week horizons, no edge in the obvious direction
- the count is real and tracks the business, it just lands after the market prices it, same conclusion as the satellite paper
- repro: `scripts/throughput_vs_airlines.py` pulls both series and rebuilds the three figures, collectors and factors under `src/`
