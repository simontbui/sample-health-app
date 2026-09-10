-- The loader wraps table creation and its checkpoint in one transaction.
SET search_path TO public;
CREATE DOMAIN confidence AS numeric(3,2)
  CHECK (VALUE BETWEEN 0.00 AND 1.00);

-- File location and ingestion time are system metadata, not parsed attributes.
CREATE TABLE file (
  id bigint PRIMARY KEY,
  blob_uri text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE document (
  id bigint PRIMARY KEY,
  file_id bigint NOT NULL REFERENCES file(id),
  document_type text, document_type_conf confidence,
  member_id text, member_id_conf confidence,
  member_first_name text, member_first_name_conf confidence,
  member_last_name text, member_last_name_conf confidence,
  provider_name text, provider_name_conf confidence,
  provider_npi text, provider_npi_conf confidence
);
CREATE TABLE encounter (
  id bigint PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES document(id),
  encounter_date date, encounter_date_conf confidence,
  encounter_type text, encounter_type_conf confidence
);
CREATE TABLE lab (
  id bigint PRIMARY KEY,
  encounter_id bigint NOT NULL REFERENCES encounter(id),
  lab_name text, lab_name_conf confidence,
  result_value numeric(10,2), result_value_conf confidence,
  unit text, unit_conf confidence
);
CREATE TABLE vital (
  id bigint PRIMARY KEY,
  encounter_id bigint NOT NULL REFERENCES encounter(id),
  vital_name text, vital_name_conf confidence,
  measured_value numeric(10,2), measured_value_conf confidence,
  unit text, unit_conf confidence
);
CREATE TABLE medication (
  id bigint PRIMARY KEY,
  encounter_id bigint NOT NULL REFERENCES encounter(id),
  medication_name text, medication_name_conf confidence,
  dose text, dose_conf confidence
);
CREATE TABLE diagnosis (
  id bigint PRIMARY KEY,
  encounter_id bigint NOT NULL REFERENCES encounter(id),
  diagnosis_code text, diagnosis_code_conf confidence,
  code_system text, code_system_conf confidence
);
-- Operational state is not parser output and has no confidence columns.
CREATE TABLE benchmark_state (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  documents bigint NOT NULL,
  batch_size integer NOT NULL,
  generator_version text NOT NULL,
  last_document bigint NOT NULL DEFAULT 0,
  phase text NOT NULL DEFAULT 'loading',
  updated_at timestamptz NOT NULL DEFAULT now()
);
