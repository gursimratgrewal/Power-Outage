# Power-Outage

## [outage-duration-prediction](outage-duration-prediction/)

**When a grid disturbance is first reported, will it still be unresolved 24 hours later?**

That's a crew-allocation question. An event resolved inside a shift is routine; one that
runs past a day becomes a multi-day mutual-aid problem. Knowing which is which when the
report comes in is worth something.

Built on DOE OE-417 electric disturbance events, 2000–2014 — 1,575 usable events. Buckets
free-text causes, adds rolling counts of recent regional activity, and ranks events by the
chance of running long.

Runs offline in under a minute: `./run_all.sh`. The data is committed, no API keys, no
downloads.

### Results — test years 2012–2014, 484 events, 141 of them long

| model | accuracy | precision | recall | PR-AUC | P@25 |
| --- | --- | --- | --- | --- | --- |
| baseline (never long) | 0.709 | 0.000 | 0.000 | 0.291 | 0.291 |
| **logistic regression** | **0.800** | **0.669** | **0.617** | **0.691** | **0.840** |
| gradient boosting | 0.787 | 0.644 | 0.603 | 0.661 | 0.840 |

![Precision-recall curve](outage-duration-prediction/outputs/figures/precision_recall.png)

Of the 25 events the model ranks most likely to run long, **21 really did**. Picking 25 at
random gets you 7.

The baseline that never predicts anything scores **70.9% accuracy** while identifying zero
long events — which is the whole argument for judging this on PR-AUC and precision@k
rather than accuracy.

Logistic regression beats gradient boosting on every metric. With 1,091 training events
there isn't enough data for the boosted trees to earn their extra capacity, and the
simpler model winning is reported rather than tuned around.

### What drives it

![Permutation importance](outage-duration-prediction/outputs/figures/feature_importance.png)

Cause dominates: storms run 65% long with a 43-hour median, physical attacks 7% with a
half-hour median. The rolling regional event counts placing second and third is the more
interesting result — how busy a region has been over the past week carries real
information beyond the cause, consistent with finite crews and mutual aid.

### Calibration

![Calibration by decile](outage-duration-prediction/outputs/figures/calibration.png)

The top decile predicts 0.837 and delivers 0.735 — the model is overconfident at the top
end, because the base rate fell from 44.8% in training to 29.1% in test. The ranking
survives that shift; the probabilities don't, quite.

Full method, feature list and limitations:
**[outage-duration-prediction/README.md](outage-duration-prediction/README.md)**
