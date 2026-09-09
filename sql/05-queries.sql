-- Ordinary SQL: run individual statements directly in VS Code.
-- Full matching-document count: use this to measure all matching work.
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT count(*) FROM clinical.document d
WHERE EXISTS (
 SELECT 1 FROM clinical.diagnosis dx WHERE dx.document_id=d.id
 AND dx.diagnosis_code='E11.9' AND dx.diagnosis_code_conf>0.65
) AND EXISTS (
 SELECT 1 FROM clinical.medication m WHERE m.document_id=d.id
 AND m.medication_name='simvastatin'
);

-- UI page: replace 0 with the last document ID from the previous page.
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT d.id,d.member_id,d.member_first_name,d.member_last_name
FROM clinical.document d
WHERE d.id>0 AND EXISTS (
 SELECT 1 FROM clinical.diagnosis dx WHERE dx.document_id=d.id
 AND dx.diagnosis_code='E11.9' AND dx.diagnosis_code_conf>0.65
) AND EXISTS (
 SELECT 1 FROM clinical.medication m WHERE m.document_id=d.id
 AND m.medication_name='simvastatin'
)
ORDER BY d.id LIMIT 50;

-- Same count, confidence separated. Copy is static; re-create it after edits
-- before comparing. Document parent is shared to isolate child-table layout.
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT count(*) FROM clinical.document d
WHERE EXISTS (
 SELECT 1 FROM separated.diagnosis dx
 JOIN separated.diagnosis_confidence c ON c.id=dx.id
 WHERE dx.document_id=d.id AND dx.diagnosis_code='E11.9'
 AND c.diagnosis_code_conf>0.65
) AND EXISTS (
 SELECT 1 FROM separated.medication m WHERE m.document_id=d.id
 AND m.medication_name='simvastatin'
);

-- Diagnosis only, to isolate the cost of joining value and confidence.
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT DISTINCT document_id FROM clinical.diagnosis
WHERE diagnosis_code='E11.9' AND diagnosis_code_conf>0.65;

-- Fetch a document's children independently to avoid medication x diagnosis
-- x encounter row multiplication. Replace 7 with a selected document ID.
SELECT * FROM clinical.document WHERE id=7;
SELECT * FROM clinical.medication WHERE document_id=7;
SELECT * FROM clinical.diagnosis WHERE document_id=7;
SELECT * FROM clinical.encounter WHERE document_id=7;

-- Storage comparison includes all indexes and confidence tables.
SELECT schemaname,relname,n_live_tup,
 pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables ORDER BY schemaname,relname;
