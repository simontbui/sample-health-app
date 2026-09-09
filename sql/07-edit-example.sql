-- This example rolls back so benchmark copies remain equal.
-- Backend supplies authenticated actor; use a short explicit transaction.
BEGIN;
SET LOCAL app.actor='example-user';
UPDATE clinical.document
SET member_first_name='Corrected first name'
WHERE id=7 AND version=1
RETURNING id,member_first_name,member_first_name_conf,version;
-- A zero-row result is a version conflict; re-fetch instead of overwriting.
SELECT * FROM audit.edit WHERE entity_table='document' AND entity_id=7;
ROLLBACK;

-- To confirm an unchanged value, explicitly set its confidence to 1.0000
-- in the same actor-tagged transaction; the audit captures that review too.
