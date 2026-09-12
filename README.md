# Power-Outage

Projects on power outage data.

## [ca-outage-prediction](ca-outage-prediction/)

Predicting high-outage days in 15 California counties from daily weather. Joins
EAGLE-I 15-minute outage records to Open-Meteo weather history, builds rolling wind and
precipitation features, and ranks county-days by the chance of landing in that county's
worst 5%. Time-based train/test split, precision@k and calibration rather than
accuracy.
