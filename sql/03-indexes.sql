\set ON_ERROR_STOP on
-- Equality first, range second; document ID available without visiting the heap.
CREATE INDEX diagnosis_search ON clinical.diagnosis(diagnosis_code,diagnosis_code_conf) INCLUDE(document_id);
CREATE INDEX medication_search ON clinical.medication(medication_name,document_id);
CREATE INDEX document_member ON clinical.document(member_id,id);
-- UNIQUE(document_id,source_item_key) already indexes child->parent lookups.
-- UNIQUE(file_id,source_document_key) already indexes file->documents.
VACUUM (ANALYZE) clinical.document;
VACUUM (ANALYZE) clinical.diagnosis;
VACUUM (ANALYZE) clinical.medication;
VACUUM (ANALYZE) clinical.encounter;
VACUUM (ANALYZE) ingest.file;
