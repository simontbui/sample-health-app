"""Resumable native PostgreSQL 17 benchmark loader (5M documents by default)."""
import argparse
import json
import subprocess
import time
import sys
from pathlib import Path

# pgAdmin's embedded Python does not automatically add the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ROOT, command, sql

VERSION = 'public-encounter-v2'


def expected_counts(n):
    return {'file': n // 2, 'document': n,
            'encounter': n * 2, 'lab': n * 4,
            'vital': n * 4, 'medication': n * 3,
            'diagnosis': n * 4}


def batch_sql(start, end):
    # Explicit IDs make batches reproducible and independent of batch size.
    return f"""
BEGIN;
INSERT INTO file SELECT i,'synthetic/file-'||i||'.pdf',now()
FROM generate_series({(start+1)//2},{end//2}) i;
INSERT INTO document
SELECT i,(i+1)/2,'clinical-note',0.95,'M'||(i%50000),(i%101)/100.0,
 'First'||(i%1000),0.90,'Last'||(i%10000),0.92,
 'Provider '||(i%2000),0.98,lpad((i%2000)::text,10,'0'),0.85
FROM generate_series({start},{end}) i;
INSERT INTO encounter
SELECT i,(i+1)/2,DATE '2025-01-01'+(i%365)::int,(i%101)/100.0,'office',0.95
FROM generate_series({2*start-1},{2*end}) i;
INSERT INTO lab
SELECT i,(i+1)/2,CASE WHEN i%2=0 THEN 'glucose' ELSE 'hemoglobin' END,
 (i%101)/100.0,CASE WHEN i%2=0 THEN 80+i%90 ELSE 12+i%6 END,
 ((i*7)%101)/100.0,CASE WHEN i%2=0 THEN 'mg/dL' ELSE 'g/dL' END,0.97
FROM generate_series({4*start-3},{4*end}) i;
INSERT INTO vital
SELECT i,(i+1)/2,CASE WHEN i%2=0 THEN 'heart_rate' ELSE 'temperature' END,
 (i%101)/100.0,CASE WHEN i%2=0 THEN 60+i%40 ELSE 36+i%3 END,
 ((i*11)%101)/100.0,CASE WHEN i%2=0 THEN 'beats/min' ELSE 'C' END,0.96
FROM generate_series({4*start-3},{4*end}) i;
INSERT INTO medication
SELECT i,2*((i-1)/3)+CASE WHEN (i-1)%3=0 THEN 1 ELSE 2 END,
 CASE WHEN i%10=0 THEN 'simvastatin' ELSE 'medication-'||(i%500) END,
 ((i*13)%101)/100.0,(5+(i%20)*5)||' mg',((i*17)%101)/100.0
FROM generate_series({3*start-2},{3*end}) i;
INSERT INTO diagnosis
SELECT i,(i+1)/2,CASE WHEN i%25<3 THEN 'E11.9' ELSE 'SYN-'||(i%1000) END,
 ((i*19)%101)/100.0,'ICD-10-CM',0.99
FROM generate_series({4*start-3},{4*end}) i;
UPDATE benchmark_state SET last_document={end},updated_at=clock_timestamp();
COMMIT;
"""


def verify(n):
    counts = {}
    for table, expected in expected_counts(n).items():
        counts[table] = int(sql(f'SELECT count(*) FROM {table};'))
        if counts[table] != expected:
            raise RuntimeError(f'{table}: expected {expected}, got {counts[table]}')
        print(f'Verified {table}: {counts[table]:,}', flush=True)
    # FK constraints cover every row; sample fanout throughout the ID space.
    mismatch = sql(f"""SELECT count(*) FROM generate_series(1,{n*2},{max(1,n*2//1000)}) e
    WHERE (SELECT count(*) FROM lab WHERE encounter_id=e)<>2
       OR (SELECT count(*) FROM vital WHERE encounter_id=e)<>2
       OR (SELECT count(*) FROM diagnosis WHERE encounter_id=e)<>2
       OR (SELECT count(*) FROM medication WHERE encounter_id=e)<>CASE WHEN e%2=1 THEN 1 ELSE 2 END;
    """)
    if int(mismatch):
        raise RuntimeError('Encounter fanout verification failed')
    return counts


def run(args):
    version = int(sql('SHOW server_version_num;'))
    if not 170000 <= version < 180000:
        raise RuntimeError('This benchmark requires PostgreSQL 17.')
    # A session lock covers bootstrap, load, indexing and verification.
    lock = subprocess.Popen(command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        lock.stdin.write('SELECT pg_try_advisory_lock(54170005);\n')
        lock.stdin.flush()
        if lock.stdout.readline().strip() != 't':
            raise RuntimeError('Another loader is running or lock connection failed.')
        exists = sql("SELECT to_regclass('benchmark_state') IS NOT NULL;") == 't'
        if not exists:
            sql('BEGIN;\n' + (ROOT/'sql/01-schema.sql').read_text() +
                f"\nINSERT INTO benchmark_state(documents,batch_size,generator_version) VALUES ({args.documents},{args.batch_size},'{VERSION}');\nCOMMIT;")
        state = json.loads(sql('SELECT row_to_json(s) FROM benchmark_state s;'))
        if (state['documents'], state['batch_size'], state['generator_version']) != (args.documents,args.batch_size,VERSION):
            raise RuntimeError('Resume with the original parameters; use a new empty database for a different dataset.')
        if state['phase'] == 'complete':
            print('Dataset already complete. Run benchmark.py to measure it.')
            return
        started = time.monotonic()
        for start in range(state['last_document']+1,args.documents+1,args.batch_size):
            if lock.poll() is not None:
                raise RuntimeError('Loader lock session was lost; stopped before next batch.')
            end = min(start+args.batch_size-1,args.documents)
            sql(batch_sql(start,end))
            print(f'Committed {end:,}/{args.documents:,} documents and children ({time.monotonic()-started:.0f}s)',flush=True)
        sql("UPDATE benchmark_state SET phase='indexing',updated_at=clock_timestamp();")
        print('Building indexes...',flush=True)
        sql((ROOT/'sql/02-indexes.sql').read_text())
        for table in expected_counts(args.documents):
            print(f'Vacuuming {table}...',flush=True)
            sql(f'VACUUM (ANALYZE) {table};')
        counts = verify(args.documents)
        sql("UPDATE benchmark_state SET phase='complete',updated_at=clock_timestamp();")
        print(json.dumps(counts,indent=2))
    finally:
        lock.stdin.close()
        try:
            lock.wait(timeout=10)
        except subprocess.TimeoutExpired:
            lock.terminate()
            lock.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents',type=int,default=5_000_000)
    parser.add_argument('--batch-size',type=int,default=20_000)
    parser.add_argument('--plan',action='store_true',help='Print exact row counts without connecting')
    args = parser.parse_args()
    if args.documents < 2 or args.documents%2 or args.batch_size < 2 or args.batch_size%2:
        parser.error('Document count and batch size must be positive even numbers.')
    print(json.dumps(expected_counts(args.documents),indent=2),flush=True)
    if not args.plan:
        run(args)


if __name__ == '__main__':
    main()
