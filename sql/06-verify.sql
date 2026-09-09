\set ON_ERROR_STOP on
SELECT set_config('bench.expected_documents', :'documents', false);
DO $$
DECLARE n bigint := current_setting('bench.expected_documents')::bigint;
BEGIN
 IF (SELECT count(*) FROM clinical.document)<>n
 OR (SELECT count(*) FROM ingest.file)<>n/2
 OR (SELECT count(*) FROM clinical.medication)<>n*3/2
 OR (SELECT count(*) FROM clinical.diagnosis)<>n*3/2
 OR (SELECT count(*) FROM clinical.encounter)<>n/2 THEN
  RAISE EXCEPTION 'Unexpected seeded counts';
 END IF;
 IF EXISTS (
  (SELECT id,document_id,diagnosis_code,diagnosis_code_conf FROM clinical.diagnosis
   EXCEPT SELECT d.id,d.document_id,d.diagnosis_code,c.diagnosis_code_conf
   FROM separated.diagnosis d JOIN separated.diagnosis_confidence c USING(id))
  UNION ALL
  (SELECT d.id,d.document_id,d.diagnosis_code,c.diagnosis_code_conf
   FROM separated.diagnosis d JOIN separated.diagnosis_confidence c USING(id)
   EXCEPT SELECT id,document_id,diagnosis_code,diagnosis_code_conf FROM clinical.diagnosis)
 ) THEN RAISE EXCEPTION 'Benchmark copies differ'; END IF;
 BEGIN
  PERFORM 1.01::clinical.confidence;
  RAISE EXCEPTION 'Out-of-range confidence accepted';
 EXCEPTION WHEN check_violation THEN NULL;
 END;
END $$;
BEGIN;
SET LOCAL app.actor='verification';
DO $$
DECLARE original clinical.document; edited clinical.document;
BEGIN
 SELECT * INTO original FROM clinical.document WHERE id=1;
 UPDATE clinical.document SET member_first_name='Reviewed' WHERE id=1 AND version=original.version
 RETURNING * INTO edited;
 IF edited.member_first_name_conf<>1 OR edited.version<>original.version+1
 OR edited.member_last_name_conf IS DISTINCT FROM original.member_last_name_conf THEN
  RAISE EXCEPTION 'Edit confidence/version behavior incorrect';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM audit.edit WHERE entity_table='document' AND entity_id=1 AND actor='verification') THEN
  RAISE EXCEPTION 'Missing audit';
 END IF;
 UPDATE clinical.document SET member_first_name='Stale overwrite' WHERE id=1 AND version=original.version;
 IF FOUND THEN RAISE EXCEPTION 'Stale write succeeded'; END IF;
END $$;
ROLLBACK;
SELECT 'verification passed' AS result;
