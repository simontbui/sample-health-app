"""Measure a loaded native PostgreSQL dataset; results are server timings."""
import argparse
import csv
import datetime
import json
import math
import platform
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ROOT, sql
from setup import VERSION, verify


def query(code, threshold, paged=False, cursor=0):
    projection = 'd.id,d.member_id,d.member_first_name,d.member_last_name' if paged else 'count(*)'
    tail = 'ORDER BY d.id LIMIT 50' if paged else ''
    return f"""SELECT {projection} FROM document d
    WHERE d.id>{cursor} AND EXISTS (
      SELECT 1 FROM encounter e WHERE e.document_id=d.id
      AND EXISTS (SELECT 1 FROM diagnosis dx WHERE dx.encounter_id=e.id
                  AND dx.diagnosis_code='{code}' AND dx.diagnosis_code_conf>{threshold})
      AND EXISTS (SELECT 1 FROM medication m WHERE m.encounter_id=e.id
                  AND m.medication_name='simvastatin')) {tail}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=10)
    parser.add_argument('--output',type=Path,default=ROOT/'results')
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error('Use at least two repetitions.')
    state = json.loads(sql('SELECT row_to_json(s) FROM benchmark_state s;'))
    if state['phase'] != 'complete' or state['generator_version'] != VERSION:
        raise RuntimeError('Run setup.py to complete this dataset first.')
    counts = verify(state['documents'])
    # Each run has its own directory, so interrupted/new runs cannot mix results.
    out = args.output / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    environment = {'postgres':sql('SELECT version();'),'client':platform.platform(),
        'state':state,'counts':counts,'repetitions':args.repeats,
        'settings':json.loads(sql("SELECT json_agg(t) FROM (SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','work_mem','effective_cache_size','max_parallel_workers_per_gather','jit','random_page_cost','track_io_timing')) t;")),
        'storage':json.loads(sql("SELECT json_agg(t) FROM (SELECT relname,pg_total_relation_size(relid) bytes FROM pg_stat_user_tables WHERE schemaname = 'public') t;"))}
    (out/'environment.json').write_text(json.dumps(environment,indent=2))
    rows, samples = [], []
    scenarios = [('common_count','E11.9',.65,False,0),('common_page','E11.9',.65,True,0),
        ('late_page','E11.9',.65,True,int(state['documents']*.9)),
        ('high_confidence','E11.9',.95,False,0),('rare_code','SYN-999',.65,False,0),
        ('no_match','DOES-NOT-EXIST',.65,False,0)]
    for name,code,threshold,paged,cursor in scenarios:
        statement = query(code,threshold,paged,cursor)
        result = sql(statement)
        values = []
        for repeat in range(args.repeats+1):
            plan = json.loads(sql('EXPLAIN (ANALYZE,BUFFERS,SETTINGS,TIMING OFF,FORMAT JSON) '+statement))
            if repeat:
                values.append(plan[0]['Execution Time'])
                samples.append(dict(scenario=name,repeat=repeat,execution_ms=values[-1],planning_ms=plan[0]['Planning Time']))
        (out/f'{name}-plan.json').write_text(json.dumps(plan,indent=2))
        rows.append(dict(scenario=name,median_ms=statistics.median(values),min_ms=min(values),
            p95_ms=sorted(values)[math.ceil(len(values)*.95)-1],result=result if not paged else f'{len(result.splitlines())} rows'))
        with (out/'summary.csv').open('w',newline='') as stream:
            writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (out/'samples.json').write_text(json.dumps(samples,indent=2))
        print(f'{name}: median {statistics.median(values):.3f} ms',flush=True)
    print(f'Saved measurements: {out}')


if __name__ == '__main__':
    main()
