-- Matching diagnosis and medication must occur in the SAME encounter.
-- Remove EXPLAIN to return data. Change cursor 0 to the last document ID to page.
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF)
SELECT d.id, d.member_id, d.member_first_name, d.member_last_name
FROM document d
WHERE d.id > 0 AND EXISTS (
  SELECT 1 FROM encounter e
  WHERE e.document_id = d.id
    AND EXISTS (SELECT 1 FROM diagnosis dx
                WHERE dx.encounter_id = e.id
                  AND dx.diagnosis_code = 'E11.9' AND dx.diagnosis_code_conf > 0.65)
    AND EXISTS (SELECT 1 FROM medication m
                WHERE m.encounter_id = e.id AND m.medication_name = 'simvastatin')
)
ORDER BY d.id LIMIT 50;

SELECT documents, last_document, phase, updated_at FROM benchmark_state;

-- View the labs and vitals for an encounter.
SELECT * FROM lab WHERE encounter_id = 1;
SELECT * FROM vital WHERE encounter_id = 1;

-- Documents and their source PDF locations, 50 results per page.
SELECT DISTINCT
    d.id, d.file_id, f.blob_uri,
    d.member_id, d.member_first_name, d.member_last_name, d.provider_name
FROM document AS d
JOIN file AS f ON f.id = d.file_id
JOIN encounter AS e ON e.document_id = d.id
JOIN diagnosis AS dx ON dx.encounter_id = e.id
JOIN medication AS m ON m.encounter_id = e.id
WHERE dx.diagnosis_code = 'E11.9'
  AND dx.diagnosis_code_conf > 0.65
  AND m.medication_name = 'simvastatin'
  AND m.medication_name_conf > 0.80
ORDER BY d.id
LIMIT 50 OFFSET 0;
