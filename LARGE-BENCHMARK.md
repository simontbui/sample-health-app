# Five-million-document benchmark

**Status: scripts prepared; the 5M dataset has not been loaded or timed by Codex.** WSL access was denied in the current session and the existing PostgreSQL port was not reachable. Historical results in results/ and RESULTS.md are for the smaller dataset.

## Run in Ubuntu

From a WSL Ubuntu terminal:

```bash
cd /mnt/c/repos/sample-health-app
sudo bash scripts/run-large.sh --reset
```

This starts/reconfigures the existing postgres-benchmark Docker project and replaces its clinical, separated, ingest, and audit schemas, as authorized. It keeps the same container volume and connection details. Stop editing the benchmark data while loading/testing. The --reset flag is destructive to those four schemas; it does not delete Docker volumes or unrelated database schemas. Dependencies in other schemas that reference benchmark objects can be affected by DROP SCHEMA CASCADE.

**To resume an interrupted load, omit --reset:**

```bash
sudo bash scripts/run-large.sh
```

Committed batches are retained. Source rows, comparison rows and the checkpoint commit together. Index creation can resume after interruption. A database advisory lock prevents two large loaders from running together. Automatic IDs may have gaps after rolled-back batches; this does not affect the matching copied rows.

## Dataset

| Entity | Rows | Children per document |
|---|---:|---|
| Files | 2,500,000 | Two documents per file |
| Documents | 5,000,000 | — |
| Medications | 15,000,000 | 2–4; average 3 |
| Diagnoses | 20,000,000 | 2–6; average 4 |
| Encounters | 10,000,000 | 1–3; average 2 |

Business total: **52,500,000 rows**. The separate-confidence design adds four tables containing 70,000,000 rows, for **122,500,000 data rows** across both layouts (excluding loader metadata). Document parents are shared by both layouts.

Fanout follows an 80-document deterministic cycle; medication/diagnosis labels and confidence draws are independent random draws. Simvastatin has a 10% chance per medication; E11.9 has a 12% chance per diagnosis. Confidence is uniform, and names/codes use the original synthetic vocabulary. This is a scale and fanout test, not a model of clinical prevalence or actual parser calibration. Changed fanout means differences from the small benchmark are not attributable to document count alone.

Rows commit in batches of 20,000 documents, with all children and copies. Search indexes are built after loading. Exact totals are verified in all nine data tables, along with per-document fanout in sampled blocks across the ID space. Every comparison row is copied from its source in the same transaction. Paired benchmark queries also verify identical output. There is no full column-by-column comparison of all 70M copied rows.

Budget roughly 50–55 GiB of free physical storage for the database, indexes, WAL and temporary work; this is a conservative planning allowance, not a measured dataset size. The loader checks available space on a local Docker data filesystem. A WSL virtual disk can report more free space than the underlying Windows disk actually has, so check both. An 8 GiB or larger WSL memory allocation is a reasonable starting point; the script retains the original PostgreSQL settings to make the configuration explicit. Runtime depends on CPU, memory and storage and is not estimated here.

## Benchmark and outputs

After loading, the same command builds indexes, runs VACUUM ANALYZE, verifies counts, and benchmarks:

- Full matching-document count.
- First 50 documents.
- A 50-document page after ID 4,500,000.
- Confidence > 0.95.
- Rare and nonexistent diagnosis codes.

All scenarios compare inline confidence with the separate-table layout. Ten measured repetitions follow warming; layout order alternates. Server execution and planning samples, final plans, settings, storage and counts are saved under results-5m/. Results appear only after execution; no 5M timings are prefilled.

To rerun only measurements:

```bash
sudo env BENCH_RESULTS_DIR=results-5m python3 scripts/benchmark.py 10
```

To increase measured repetitions during a load/resume run:

```bash
sudo env BENCH_REPEATS=30 bash scripts/run-large.sh
```

For a smaller smoke load of the same fanout, use 800 documents. This also replaces the existing benchmark schemas if --reset is passed:

```bash
sudo bash scripts/run-large.sh 800 --reset
```

Use the same document count and batch size when resuming. Both must be multiples of 80. Larger transactions can be requested with --batch-size; changing batch size changes the seeded random sequence, so it is fixed in the stored loader configuration.

To inspect committed progress in VS Code:

```sql
SELECT documents, last_document, phase, updated_at
FROM ingest.large_benchmark;
```

phase becomes complete only after index creation, vacuum and count/fanout verification. After completion, do not use scripts/setup.sh or sql/06-verify.sql: those retain the old small-dataset expectations. Use run-large.sh or benchmark.py for this dataset.

## Connection

Unchanged:

```text
postgresql://bench@127.0.0.1:55432/docbench?sslmode=disable
```

Password: local-bench-only.

The SQL example queries remain in sql/05-queries.sql. Local warm measurements do not establish Azure latency or concurrency limits. Run on the target Azure hardware/storage and with realistic distributions before choosing production capacity.
