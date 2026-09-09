# Measured benchmark results

Documents: 5,000,000. Repetitions per query: 10.

Warm server execution times; single client, excluding transfer and UI rendering. Not an Azure latency estimate.

| Scenario | Confidence columns median | Separate confidence median |
|---|---:|---:|
| common_count | 606.298 ms | 1479.483 ms |
| common_page | 0.845 ms | 1.324 ms |
| late_page | 81.921 ms | 82.139 ms |
| high_confidence | 302.568 ms | 636.425 ms |
| rare_code | 39.844 ms | 128.519 ms |
| no_match | 0.174 ms | 28.892 ms |

All paired query results matched. See environment.json, summary.csv, samples.json and the saved query plans.
Ten repetitions are too few for an SLO claim. Cached pages, data distribution, concurrency and Azure storage/tier affect results.
