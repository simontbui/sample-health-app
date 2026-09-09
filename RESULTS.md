# Local benchmark results — September 9, 2026

Recommendation: keep confidence beside its extracted value in the typed entity table. The measured matching queries were faster with this layout, and its medication/diagnosis tables plus indexes used less space than the separated equivalent. This supports the recommendation for this workload; it does not establish that every possible query is faster.

PostgreSQL 17.11 runs in Docker Engine 29.8.0 inside Ubuntu 26.04 on WSL. The database is running at `127.0.0.1:55432`. Connection details and restart commands are in README.md.

Loaded 100,000 files, 200,000 documents, 300,000 medications, 300,000 diagnoses and 100,000 encounters: **1,000,000 business rows**. The comparison schema adds 1,200,000 rows for medication/diagnosis values and their confidence tables.

| Scenario | Confidence columns, median | Separate confidence tables, median | Matching documents |
|---|---:|---:|---:|
| E11.9, confidence > 0.65, simvastatin; full count | 13.708 ms | 20.350 ms | 1,536 |
| Same filters; first 50 documents | 1.388 ms | 1.592 ms | 50 returned |
| Confidence > 0.95; full count | 5.641 ms | 10.637 ms | 217 |
| Rare diagnosis SYN-999; full count | 0.722 ms | 1.684 ms | 16 |
| Nonexistent diagnosis; full count | 0.102 ms | 0.086 ms | 0 |

Ten measured repetitions per query, after warming, with alternating layout order. These are server execution times from EXPLAIN ANALYZE, excluding connection setup, result transmission, and UI rendering. Queries run with one client; PostgreSQL can use parallel workers internally. These are warm local measurements, not Azure predictions or concurrent throughput measurements.

The common-count confidence-column plan uses `diagnosis_search` as an index-only scan with both code and confidence in its index condition. The separated plan scans code and confidence indexes separately and joins their rows. In the saved common-count plans both layouts have zero shared reads and zero temporary reads/writes, so the comparison is of cached execution. Some document heap fetches remain after the rollback-based edit verification.

Medication + diagnosis storage, including indexes, was 116,998,144 bytes with confidence columns versus 164,773,888 bytes across the four separated tables. The separate layout uses about 41% more space for these entities in this configuration. Shared documents, files, encounters and audit are excluded from this comparison.

Validation passed: exact seeded row counts, identical diagnosis comparison projections, invalid confidence rejection, changed-field confidence=1, unchanged-field confidence preservation, version increment, stale-write rejection, and audit insertion. Benchmark checks confirmed identical results for each scenario in both layouts. Human edit tests rolled back. Windows TCP connectivity to the published port was verified.

See `results/summary.csv` for all timing summaries, `results/environment.json` for tested versions/settings/storage, and the `results/*-plan.json` files for execution plans. The scripts and seed remain available to rerun on larger data or the intended Azure tier.
