CREATE INDEX IF NOT EXISTS diagnosis_search ON clinical.diagnosis(diagnosis_code,diagnosis_code_conf) INCLUDE(document_id);
CREATE INDEX IF NOT EXISTS medication_search ON clinical.medication(medication_name,document_id);
CREATE INDEX IF NOT EXISTS document_member ON clinical.document(member_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS diagnosis_doc_source ON separated.diagnosis(document_id,source_item_key);
CREATE UNIQUE INDEX IF NOT EXISTS medication_doc_source ON separated.medication(document_id,source_item_key);
CREATE INDEX IF NOT EXISTS diagnosis_search ON separated.diagnosis(diagnosis_code) INCLUDE(id,document_id);
CREATE INDEX IF NOT EXISTS diagnosis_conf_search ON separated.diagnosis_confidence(diagnosis_code_conf,id);
CREATE INDEX IF NOT EXISTS medication_search ON separated.medication(medication_name,document_id);
