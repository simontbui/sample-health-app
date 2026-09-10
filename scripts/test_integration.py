"""Run explicitly against a dedicated empty test database, never the full dataset."""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ROOT, sql
from setup import VERSION, batch_sql, run, verify
from benchmark import query


def rejected(statement):
    try:
        sql('BEGIN;'+statement+';ROLLBACK;')
    except subprocess.CalledProcessError:
        return
    raise AssertionError('Database accepted invalid input: '+statement)


def main():
    assert sql("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public';") == '0', 'Use an empty test database'
    assert sql("SELECT to_regtype('confidence') IS NULL;") == 't', 'Confidence type already exists'
    # Simulate interruption after the first committed batch, then resume.
    sql('BEGIN;'+(ROOT/'sql/01-schema.sql').read_text()+
        f"INSERT INTO benchmark_state(documents,batch_size,generator_version) VALUES (800,200,'{VERSION}');COMMIT;")
    sql(batch_sql(1,200))
    # A failed multi-table batch must roll back rows and checkpoint together.
    rejected(batch_sql(201,400).replace('BEGIN;','').replace('COMMIT;','') + 'SELECT 1/0')
    assert sql('SELECT last_document FROM benchmark_state;') == '200'
    assert sql('SELECT count(*) FROM document;') == '200'
    run(argparse.Namespace(documents=800,batch_size=200))
    run(argparse.Namespace(documents=800,batch_size=200))
    verify(800)
    for value in ('-0.01','1.01',"'NaN'"):
        rejected(f'SELECT ({value})::confidence')
    assert sql('SELECT 0::confidence,1::confidence,NULL::confidence;') == '0.00|1.00|'
    rejected('UPDATE lab SET encounter_id=999999 WHERE id=1')
    rejected('UPDATE vital SET encounter_id=NULL WHERE id=1')
    # Every parsed field must have a confidence sibling (except the parent FK).
    missing = sql("""SELECT count(*) FROM information_schema.columns c
      WHERE table_schema='public' AND table_name IN ('document','encounter','lab','vital','medication','diagnosis')
      AND domain_name IS DISTINCT FROM 'confidence'
      AND column_name NOT IN ('id','file_id','document_id','encounter_id')
      AND NOT EXISTS (SELECT 1 FROM information_schema.columns s
         WHERE s.table_schema=c.table_schema AND s.table_name=c.table_name
         AND s.column_name=c.column_name||'_conf' AND s.domain_name='confidence');""")
    assert missing == '0'
    assert int(sql(query('E11.9',.65))) > 0
    assert sql(query('DOES-NOT-EXIST',.65)) == '0'
    # A split match across two encounters must not qualify the document.
    sql("""BEGIN;
      UPDATE diagnosis SET diagnosis_code='FIXTURE',diagnosis_code_conf=1 WHERE id=1;
      UPDATE medication SET medication_name='other' WHERE encounter_id=1;
      UPDATE medication SET medication_name='simvastatin' WHERE encounter_id=2;
      COMMIT;""")
    assert sql(query('FIXTURE',.65)) == '0'
    sql("UPDATE medication SET medication_name='simvastatin' WHERE encounter_id=1;")
    assert sql(query('FIXTURE',.65)) == '1'
    # Drop only the fixture's objects; never drop the shared public schema.
    sql('DROP TABLE diagnosis, medication, vital, lab, encounter, document, file, benchmark_state; DROP DOMAIN confidence;')
    print('Integration checks passed: atomic rollback, resume, counts, confidence, FKs and same-encounter semantics.')


if __name__ == '__main__':
    main()
