\set ON_ERROR_STOP on
-- Optional static benchmark copy. Typed one-to-one confidence tables are a stronger
-- baseline than generic entity/attribute/value storage. Never used by the edit API.
CREATE SCHEMA separated;
CREATE TABLE separated.diagnosis AS SELECT id,document_id,source_item_key,diagnosis_code,code_system,version,updated_at FROM clinical.diagnosis;
ALTER TABLE separated.diagnosis ADD PRIMARY KEY(id);
ALTER TABLE separated.diagnosis ADD FOREIGN KEY(document_id) REFERENCES clinical.document(id);
CREATE TABLE separated.diagnosis_confidence (
 id bigint PRIMARY KEY REFERENCES separated.diagnosis(id),
 diagnosis_code_conf clinical.confidence,code_system_conf clinical.confidence
);
INSERT INTO separated.diagnosis_confidence SELECT id,diagnosis_code_conf,code_system_conf FROM clinical.diagnosis;
CREATE TABLE separated.medication AS SELECT id,document_id,source_item_key,medication_name,dose,version,updated_at FROM clinical.medication;
ALTER TABLE separated.medication ADD PRIMARY KEY(id);
ALTER TABLE separated.medication ADD FOREIGN KEY(document_id) REFERENCES clinical.document(id);
CREATE TABLE separated.medication_confidence (
 id bigint PRIMARY KEY REFERENCES separated.medication(id),
 medication_name_conf clinical.confidence,dose_conf clinical.confidence
);
INSERT INTO separated.medication_confidence SELECT id,medication_name_conf,dose_conf FROM clinical.medication;
CREATE UNIQUE INDEX ON separated.diagnosis(document_id,source_item_key);
CREATE UNIQUE INDEX ON separated.medication(document_id,source_item_key);
CREATE INDEX ON separated.diagnosis(diagnosis_code) INCLUDE(id,document_id);
CREATE INDEX ON separated.diagnosis_confidence(diagnosis_code_conf,id);
CREATE INDEX ON separated.medication(medication_name,document_id);
VACUUM (ANALYZE) separated.diagnosis;
VACUUM (ANALYZE) separated.diagnosis_confidence;
VACUUM (ANALYZE) separated.medication;
VACUUM (ANALYZE) separated.medication_confidence;
