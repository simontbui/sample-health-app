"""Resumable 5M-document load. Use run-large.sh from Ubuntu with Docker access.
--reset replaces only the four benchmark schemas. Without it, loading resumes.
--plan validates parameters and prints counts without invoking Docker.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PSQL = ['docker', 'compose', 'exec', '-T', 'db', 'psql', '-X', '-q',
        '-U', 'bench', '-d', 'docbench', '-v', 'ON_ERROR_STOP=1', '-At']


def expected_counts(n):
    return {'ingest.file': n // 2, 'clinical.document': n,
            'clinical.medication': n * 3, 'clinical.diagnosis': n * 4,
            'clinical.encounter': n * 2, 'separated.medication': n * 3,
            'separated.medication_confidence': n * 3,
            'separated.diagnosis': n * 4, 'separated.diagnosis_confidence': n * 4}


def sql(query):
    return subprocess.check_output(PSQL, input=query, cwd=ROOT, text=True).strip()


def batch_sql(start, end, n):
    seed = start / (n + 1)
    return f"""
BEGIN;
SELECT setseed({seed});
INSERT INTO ingest.file(id,blob_uri,blob_version)
SELECT i,'synthetic/file-'||i||'.pdf','v1' FROM generate_series({(start+1)//2},{end//2}) i;
INSERT INTO clinical.document(id,file_id,source_document_key,member_id,member_id_conf,
 member_first_name,member_first_name_conf,member_last_name,member_last_name_conf,
 provider_name,provider_name_conf,provider_npi,provider_npi_conf)
SELECT i,(i+1)/2,'doc-'||i,'M'||(i%50000),random(),
 'First'||(i%1000),random(),'Last'||(i%10000),random(),
 'Provider '||(i%2000),random(),lpad((i%2000)::text,10,'0'),random()
FROM generate_series({start},{end}) i;
INSERT INTO clinical.medication(document_id,source_item_key,medication_name,medication_name_conf,dose,dose_conf)
SELECT d.id,'med-'||s,
 CASE WHEN random()<0.10 THEN 'simvastatin' ELSE 'medication-'||floor(random()*500)::int END,
 random(),(5+floor(random()*20)*5)::int||' mg',random()
FROM clinical.document d
CROSS JOIN LATERAL generate_series(1,(2+least(d.id%4,4-d.id%4))::int) s
WHERE d.id BETWEEN {start} AND {end};
INSERT INTO clinical.diagnosis(document_id,source_item_key,diagnosis_code,diagnosis_code_conf,code_system,code_system_conf)
SELECT d.id,'dx-'||s,
 CASE WHEN random()<0.12 THEN 'E11.9' ELSE 'SYN-'||floor(random()*1000)::int END,
 random(),'ICD-10-CM',0.99
FROM clinical.document d
CROSS JOIN LATERAL generate_series(1,(2+d.id%5)::int) s
WHERE d.id BETWEEN {start} AND {end};
INSERT INTO clinical.encounter(document_id,source_item_key,encounter_date,encounter_date_conf,encounter_type,encounter_type_conf)
SELECT d.id,'enc-'||s,DATE '2025-01-01'+floor(random()*365)::int,random(),'office',random()
FROM clinical.document d
CROSS JOIN LATERAL generate_series(1,(1+least((d.id/4)%4,4-(d.id/4)%4))::int) s
WHERE d.id BETWEEN {start} AND {end};
INSERT INTO separated.medication
SELECT id,document_id,source_item_key,medication_name,dose,version,updated_at
FROM clinical.medication WHERE document_id BETWEEN {start} AND {end};
INSERT INTO separated.medication_confidence
SELECT id,medication_name_conf,dose_conf FROM clinical.medication
WHERE document_id BETWEEN {start} AND {end};
INSERT INTO separated.diagnosis
SELECT id,document_id,source_item_key,diagnosis_code,code_system,version,updated_at
FROM clinical.diagnosis WHERE document_id BETWEEN {start} AND {end};
INSERT INTO separated.diagnosis_confidence
SELECT id,diagnosis_code_conf,code_system_conf FROM clinical.diagnosis
WHERE document_id BETWEEN {start} AND {end};
UPDATE ingest.large_benchmark SET last_document={end},updated_at=clock_timestamp();
COMMIT;
"""


def verify(n):
    counts = {}
    for table, expected in expected_counts(n).items():
        count = int(sql(f'SELECT count(*) FROM {table};'))
        if count != expected:
            raise RuntimeError(f'{table}: expected {expected:,}, found {count:,}')
        counts[table] = count
        print(f'Verified {table}: {count:,}', flush=True)
    # Consecutive blocks across the ID space cover every fanout residue.
    step = max(80, (n // 1000 // 80) * 80)
    mismatch = sql(f"""WITH sample AS (
      SELECT base+offset_id AS id FROM generate_series(1,{n},{step}) base
      CROSS JOIN generate_series(0,79) offset_id WHERE base+offset_id<={n}
    ) SELECT count(*) FROM sample d
    WHERE (SELECT count(*) FROM clinical.medication m WHERE m.document_id=d.id) <> 2+least(d.id%4,4-d.id%4)
       OR (SELECT count(*) FROM clinical.diagnosis dx WHERE dx.document_id=d.id) <> 2+d.id%5
       OR (SELECT count(*) FROM clinical.encounter e WHERE e.document_id=d.id) <> 1+least((d.id/4)%4,4-(d.id/4)%4);""")
    if int(mismatch):
        raise RuntimeError('Sampled per-document child counts differ from generator.')
    return counts


def bootstrap(n, batch_size, reset):
    base = '\n'.join(line for line in (ROOT/'sql/01-schema.sql').read_text().splitlines()
                     if not line.startswith('\\'))
    if reset:
        base = base.replace('BEGIN;', 'BEGIN;\nDROP SCHEMA IF EXISTS separated,clinical,audit,ingest CASCADE;', 1)
    initial = (ROOT/'sql/08-large-init.sql').read_text()
    initial += f'\nINSERT INTO ingest.large_benchmark(documents,batch_size) VALUES ({n},{batch_size});\n'
    prefix, suffix = base.rsplit('COMMIT;', 1)
    sql(prefix + initial + '\nCOMMIT;' + suffix)


def check_disk(remaining):
    docker_root = subprocess.check_output(['docker','info','--format','{{.DockerRootDir}}'],
                                          text=True).strip()
    if Path(docker_root).exists():
        free = shutil.disk_usage(docker_root).free
        required = (2 + remaining / 5_000_000 * 50) * 1024**3
        print(f'Docker filesystem free: {free/1024**3:.1f} GiB; conservative remaining budget: {required/1024**3:.1f} GiB', flush=True)
        if free < required:
            raise RuntimeError('Insufficient free disk space for the conservative load budget.')
    else:
        print('Docker storage is remote; confirm roughly 50 GiB free for the default dataset.', flush=True)


def run(args):
    if os.environ.get('COMPOSE_PROJECT_NAME', 'postgres-benchmark') != 'postgres-benchmark':
        raise RuntimeError('This loader targets only the postgres-benchmark Compose project.')
    subprocess.run(['docker', 'compose', 'up', '-d', '--wait'], cwd=ROOT, check=True)
    lock = subprocess.Popen(PSQL, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=ROOT)
    try:
        lock.stdin.write('SELECT pg_try_advisory_lock(54170005);\n')
        lock.stdin.flush()
        if lock.stdout.readline().strip() != 't':
            raise RuntimeError('Another large loader is already running.')
        exists = sql("SELECT to_regclass('ingest.large_benchmark') IS NOT NULL;") == 't'
        if args.reset or not exists:
            if not args.reset and sql("SELECT to_regnamespace('clinical') IS NOT NULL;") == 't':
                raise RuntimeError('Small dataset exists. Run with --reset to replace it.')
            check_disk(args.documents)
            bootstrap(args.documents,args.batch_size,args.reset)
        state = json.loads(sql('SELECT row_to_json(b) FROM ingest.large_benchmark b;'))
        if (state['documents'],state['batch_size'],state['generator_version']) != (args.documents,args.batch_size,'large-v1'):
            raise RuntimeError('Resume with the original document count and BATCH_DOCUMENTS, or explicitly use --reset.')
        if state['phase'] == 'complete':
            print('Large dataset already complete; proceeding to benchmarks.', flush=True)
            return
        check_disk(args.documents-state['last_document'])
        started = time.monotonic()
        for start in range(state['last_document'] + 1, args.documents + 1, args.batch_size):
            end = min(start + args.batch_size - 1, args.documents)
            sql(batch_sql(start,end,args.documents))
            print(f'Committed {end:,}/{args.documents:,} documents + children + comparison copies; elapsed {time.monotonic()-started:.0f}s', flush=True)
        sql(f"SELECT setval(pg_get_serial_sequence('ingest.file','id'),{args.documents//2}); SELECT setval(pg_get_serial_sequence('clinical.document','id'),{args.documents});")
        print('Building search indexes; completed indexes survive interruption.', flush=True)
        subprocess.run(PSQL + ['-f','/bench/09-large-indexes.sql'],cwd=ROOT,check=True)
        for table in expected_counts(args.documents):
            print(f'VACUUM ANALYZE {table}', flush=True)
            sql(f'VACUUM (ANALYZE) {table};')
        counts = verify(args.documents)
        out = ROOT / os.environ.get('BENCH_RESULTS_DIR','results-5m')
        out.mkdir(parents=True,exist_ok=True)
        (out/'load-verification.json').write_text(json.dumps({'counts':counts,
            'documents_per_batch':args.batch_size,
            'verification':'Exact table totals; sampled per-document fanout; source and comparison rows committed together.',
            'elapsed_seconds_this_invocation':time.monotonic()-started},indent=2))
        sql("UPDATE ingest.large_benchmark SET phase='complete',updated_at=clock_timestamp();")
        print('Ready on 127.0.0.1:55432 / docbench / bench',flush=True)
    finally:
        lock.stdin.close()
        lock.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('documents',nargs='?',type=int,default=5_000_000)
    parser.add_argument('--batch-size',type=int,default=int(os.environ.get('BATCH_DOCUMENTS','20000')))
    parser.add_argument('--reset',action='store_true')
    parser.add_argument('--plan',action='store_true')
    args = parser.parse_args()
    if args.documents < 80 or args.documents % 80 or args.batch_size < 80 or args.batch_size % 80:
        parser.error('Document count and batch size must be positive multiples of 80.')
    print(json.dumps(expected_counts(args.documents),indent=2),flush=True)
    if not args.plan:
        run(args)


if __name__ == '__main__':
    main()
