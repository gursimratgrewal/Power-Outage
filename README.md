# Power-Outage

## [outage-duration-prediction](outage-duration-prediction/)

**When a grid disturbance is first reported, will it still be unresolved 24 hours later?**

Built on DOE OE-417 electric disturbance events, 2000–2014. Buckets free-text causes,
adds rolling counts of recent regional activity, and ranks events by the chance of
running long — a crew-allocation question rather than an academic one.

Baseline vs logistic regression vs gradient boosting, split by year rather than
randomly, judged on PR-AUC and precision@k instead of accuracy. Of the 25 events the
model flags hardest, 21 really ran long; picking 25 at random gets 7.

Runs offline in under a minute — the data is committed, no API keys, no downloads.
