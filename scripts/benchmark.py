"""Standard-library benchmark: Docker + psql, executed from Ubuntu."""
import csv
import datetime
import json
import math
import os
import pathlib
import platform
import statistics
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sql(query):
    return subprocess.check_output(
        ['docker', 'compose', 'exec', '-T', 'db', 'psql', '-X', '-U', 'bench',
         '-d', 'docbench', '-v', 'ON_ERROR_STOP=1', '-At', '-c', query],
        cwd=ROOT, text=True).strip()


def query(layout, code, threshold, paged=False, cursor=0):
    if layout == 'clinical':
        child, conf = 'clinical.diagnosis dx', 'dx.diagnosis_code_conf'
    else:
        child = 'separated.diagnosis dx JOIN separated.diagnosis_confidence c ON c.id=dx.id'
        conf = 'c.diagnosis_code_conf'
    projection = 'd.id,d.member_id,d.member_first_name,d.member_last_name' if paged else 'count(*)'
    tail = 'ORDER BY d.id LIMIT 50' if paged else ''
    return f"""SELECT {projection} FROM clinical.document d
    WHERE d.id>{int(cursor)} AND EXISTS (SELECT 1 FROM {child}
    WHERE dx.document_id=d.id AND dx.diagnosis_code='{code}' AND {conf}>{threshold})
    AND EXISTS (SELECT 1 FROM {layout}.medication m
    WHERE m.document_id=d.id AND m.medication_name='simvastatin') {tail}"""


def main():
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    if repeats < 2:
        raise SystemExit('Use at least 2 measured repetitions.')
    out = ROOT / os.environ.get('BENCH_RESULTS_DIR', 'results')
    out.mkdir(parents=True, exist_ok=True)
    if sql("SELECT to_regclass('ingest.large_benchmark') IS NOT NULL") == 't':
        if sql('SELECT phase FROM ingest.large_benchmark') != 'complete':
            raise SystemExit('Large load/index/verification is unfinished; resume run-large.sh first.')
    print('Collecting database counts and settings...', flush=True)
    environment = {
        'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'postgres': sql('SELECT version()'),
        'settings': json.loads(sql("SELECT json_agg(t) FROM (SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','work_mem','effective_cache_size','max_parallel_workers_per_gather','jit','random_page_cost','track_io_timing')) t")),
        'counts': json.loads(sql("SELECT json_build_object('files',(SELECT count(*) FROM ingest.file),'documents',(SELECT count(*) FROM clinical.document),'medications',(SELECT count(*) FROM clinical.medication),'diagnoses',(SELECT count(*) FROM clinical.diagnosis),'encounters',(SELECT count(*) FROM clinical.encounter))")),
        'storage': json.loads(sql("SELECT json_agg(t) FROM (SELECT schemaname,relname,pg_total_relation_size(relid) AS bytes FROM pg_stat_user_tables ORDER BY 1,2) t")),
        'docker_image': subprocess.check_output(['docker','compose','images','--format','json'],cwd=ROOT,text=True).strip(),
        'client_host': {'system': platform.system(), 'release': platform.release(), 'logical_cpus': os.cpu_count()},
        'repetitions': repeats,
        'method': 'One explicit warm-up per query; alternating layout order; server EXPLAIN execution time; sequential clients; no cold-cache claim.'
    }
    (out / 'environment.json').write_text(json.dumps(environment, indent=2))
    rows, raw = [], []
    scenarios = [('common_count','E11.9','0.65',False,0),
                 ('common_page','E11.9','0.65',True,0),
                 ('late_page','E11.9','0.65',True,int(environment['counts']['documents']*.9)),
                 ('high_confidence','E11.9','0.95',False,0),
                 ('rare_code','SYN-999','0.65',False,0),
                 ('no_match','DOES-NOT-EXIST','0.65',False,0)]
    for name, code, threshold, paged, cursor in scenarios:
        print(f'Running {name}...', flush=True)
        statements = {layout: query(layout,code,threshold,paged,cursor) for layout in ('clinical','separated')}
        outputs = {layout: sql(q) for layout,q in statements.items()}
        if outputs['clinical'] != outputs['separated']:
            raise RuntimeError(f'{name}: result mismatch; comparison snapshot may be stale after edits.')
        timings = {layout: [] for layout in statements}
        for repeat in range(repeats + 1):
            order = list(statements) if repeat % 2 == 0 else list(reversed(statements))
            for layout in order:
                plan = json.loads(sql('EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF, FORMAT JSON) ' + statements[layout]))
                if repeat:
                    timings[layout].append(plan[0]['Execution Time'])
                    raw.append({'scenario':name,'layout':layout,'repeat':repeat,
                                'execution_ms':plan[0]['Execution Time'],'planning_ms':plan[0]['Planning Time']})
                if repeat == repeats:
                    (out / f'{name}-{layout}-plan.json').write_text(json.dumps(plan,indent=2))
        for layout,values in timings.items():
            row = dict(scenario=name,layout=layout,median_ms=round(statistics.median(values),3),
                       min_ms=min(values),p95_ms=sorted(values)[math.ceil(len(values)*.95)-1],
                       repetitions=repeats,result=outputs[layout] if not paged else f'{len(outputs[layout].splitlines())} rows; cursor={cursor}')
            rows.append(row)
            print(f"{name:18} {layout:10} median={row['median_ms']:8.3f} ms", flush=True)
        # Persist completed scenarios even if a later query fails.
        with (out / 'summary.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (out / 'samples.json').write_text(json.dumps(raw,indent=2))
    report = ['# Measured benchmark results', '',
              f"Documents: {environment['counts']['documents']:,}. Repetitions per query: {repeats}.",
              '', 'Warm server execution times; single client, excluding transfer and UI rendering. Not an Azure latency estimate.',
              '', '| Scenario | Confidence columns median | Separate confidence median |',
              '|---|---:|---:|']
    for name, *_ in scenarios:
        pair = {r['layout']:r['median_ms'] for r in rows if r['scenario']==name}
        report.append(f"| {name} | {pair['clinical']:.3f} ms | {pair['separated']:.3f} ms |")
    report += ['', 'All paired query results matched. See environment.json, summary.csv, samples.json and the saved query plans.',
               'Ten repetitions are too few for an SLO claim. Cached pages, data distribution, concurrency and Azure storage/tier affect results.']
    (out / 'RESULTS.md').write_text('\n'.join(report)+'\n')
    print(f'Saved measurements to {out}', flush=True)


if __name__ == '__main__':
    main()
