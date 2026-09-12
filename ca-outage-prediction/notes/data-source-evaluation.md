# Why this project uses EAGLE-I and not DOE OE-417

Two public datasets could plausibly answer "which places will have a bad outage
day tomorrow." I evaluated both. This note records why one was chosen, so the
choice isn't mistaken for an accident.

Reproduce the numbers below with `python tools/evaluate_oe417.py`, which reads
the OE-417 file committed at `handoff/oe417/`.

## The candidates

| | EAGLE-I (chosen) | OE-417 grid disruptions |
| --- | --- | --- |
| publisher | Oak Ridge National Laboratory | DOE / OE, via a Kaggle mirror |
| what a row is | a county at a 15-minute instant | one reportable disturbance event |
| geography | county FIPS | free text: "California", "Northern California", "San Francisco Bay Area" |
| coverage | every county, every interval | only events above federal reporting thresholds |
| span | 2014– | 2000–2014 |
| cause recorded | no | yes, as free text |

## What killed OE-417

**1. Too few positives to measure anything.**

Nationwide it holds 1,652 events across 15 years. California's share is 162
events on 146 distinct days. Bucketing the free-text descriptions by cause:

| cause | events | distinct days |
| --- | --- | --- |
| other (equipment, attack, fuel, grid operations) | 108 | 100 |
| storm / wind / rain | 37 | 36 |
| fire | 12 | 8 |
| heat | 5 | 4 |

Weather-driven causes total **54 events on 48 days over fifteen years** — a
0.94% base rate. Holding out 2012–2014 the way this project holds out its last
three years leaves **7 positive days in the test set.**

Seven is not a test set. Precision@10 cannot be computed meaningfully against it,
and one event landing differently moves any metric by more than ten points. No
amount of modelling fixes a denominator that small.

**2. Using every event instead makes the target incoherent.**

Widening the target to all 146 event days lifts the base rate to 2.9%, but
two-thirds of those events are vandalism, equipment failure, fuel supply
emergencies and islanding — outcomes weather genuinely cannot predict. A model
trained on that target would mostly be learning that weather doesn't explain
vandalism. That's a true finding and a useless one: the null result would come
from contaminating the label, not from anything about weather and the grid.

**3. No county resolution.**

Geography is free text at inconsistent granularity — "California", "Northern and
Central California", "San Diego & Orange Counties". The 15-county panel collapses
to a single statewide series, cutting the data by a factor of fifteen and
removing the per-county thresholds that let Napa and Los Angeles be judged on
their own scales.

**4. It ends in 2014, where EAGLE-I begins.**

The weather already collected covers 2014–2024, so the overlap with OE-417 is a
single year. Using it would mean a second weather pull for 2000–2014.

## What OE-417 is still good for

Its cause labels are the thing EAGLE-I lacks, and a lack this project names as a
limitation: EAGLE-I cannot distinguish a storm outage from a PSPS shutoff. OE-417
can't fix that here, because its coverage ends in 2014 and California's PSPS
programme began in 2018 — but it's the right shape of data for that question, and
a later version of this project with 2015+ OE-417 records could use it to label
causes on the worst days EAGLE-I identifies.

The file is kept in `handoff/oe417/` for that reason, and because a rejected data
source is worth keeping alongside the reason it was rejected.

## The decision

EAGLE-I, on a 15-county daily panel. It gives roughly 60,000 county-days with
about 3,000 high-outage days, against OE-417's 48 usable positives. The gap is
three orders of magnitude in the quantity that actually constrains this problem.
