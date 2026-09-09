CREATE SCHEMA separated;
CREATE TABLE separated.diagnosis AS
 SELECT id,document_id,source_item_key,diagnosis_code,code_system,version,updated_at
 FROM clinical.diagnosis WITH NO DATA;
ALTER TABLE separated.diagnosis ADD PRIMARY KEY(id);
ALTER TABLE separated.diagnosis ADD FOREIGN KEY(document_id) REFERENCES clinical.document(id);
CREATE TABLE separated.diagnosis_confidence (
 id bigint PRIMARY KEY REFERENCES separated.diagnosis(id),
 diagnosis_code_conf clinical.confidence,code_system_conf clinical.confidence
);
CREATE TABLE separated.medication AS
 SELECT id,document_id,source_item_key,medication_name,dose,version,updated_at
 FROM clinical.medication WITH NO DATA;
ALTER TABLE separated.medication ADD PRIMARY KEY(id);
ALTER TABLE separated.medication ADD FOREIGN KEY(document_id) REFERENCES clinical.document(id);
CREATE TABLE separated.medication_confidence (
 id bigint PRIMARY KEY REFERENCES separated.medication(id),
 medication_name_conf clinical.confidence,dose_conf clinical.confidence
);
CREATE TABLE ingest.large_benchmark (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 documents bigint NOT NULL,
 batch_size integer NOT NULL,
 last_document bigint NOT NULL DEFAULT 0,
 phase text NOT NULL DEFAULT 'loading',
 generator_version text NOT NULL DEFAULT 'large-v1',
 updated_at timestamptz NOT NULL DEFAULT now()
);
