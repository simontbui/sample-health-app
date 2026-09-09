\set ON_ERROR_STOP on
-- documents must be a positive multiple of 4. Default supplied by setup.sh: 200000.
SELECT setseed(0.314159);
BEGIN;
INSERT INTO ingest.file(id,blob_uri,blob_version)
SELECT i,'synthetic/file-'||i||'.pdf','v1' FROM generate_series(1,:documents / 2) i;
INSERT INTO clinical.document(id,file_id,source_document_key,member_id,member_id_conf,
 member_first_name,member_first_name_conf,member_last_name,member_last_name_conf,
 provider_name,provider_name_conf,provider_npi,provider_npi_conf)
SELECT i,(i+1)/2,'doc-'||i,'M'||(i%50000),random(),
 'First'||(i%1000),random(),'Last'||(i%10000),random(),
 'Provider '||(i%2000),random(),lpad((i%2000)::text,10,'0'),random()
FROM generate_series(1,:documents) i;
-- Variable fanout: 0..3 medications; 0..3 diagnoses; 0..2 encounters.
-- Independent random draws avoid accidental modulo correlation between search predicates.
INSERT INTO clinical.medication(document_id,source_item_key,medication_name,medication_name_conf,dose,dose_conf)
SELECT d.id,'med-'||s,
 CASE WHEN random()<0.10 THEN 'simvastatin' ELSE 'medication-'||floor(random()*500)::int END,
 random(),(5+floor(random()*20)*5)::int||' mg',random()
FROM clinical.document d CROSS JOIN LATERAL generate_series(1,(d.id%4)::int) s;
INSERT INTO clinical.diagnosis(document_id,source_item_key,diagnosis_code,diagnosis_code_conf,code_system,code_system_conf)
SELECT d.id,'dx-'||s,
 CASE WHEN random()<0.12 THEN 'E11.9' ELSE 'SYN-'||floor(random()*1000)::int END,
 random(),'ICD-10-CM',0.99
FROM clinical.document d CROSS JOIN LATERAL generate_series(1,((d.id+1)%4)::int) s;
INSERT INTO clinical.encounter(document_id,source_item_key,encounter_date,encounter_date_conf,encounter_type,encounter_type_conf)
SELECT d.id,'enc-'||s,DATE '2025-01-01'+floor(random()*365)::int,random(),'office',random()
FROM clinical.document d CROSS JOIN LATERAL generate_series(1,CASE WHEN d.id%4=0 THEN 2 ELSE 0 END) s;
SELECT setval(pg_get_serial_sequence('ingest.file','id'),:documents/2);
SELECT setval(pg_get_serial_sequence('clinical.document','id'),:documents);
COMMIT;
