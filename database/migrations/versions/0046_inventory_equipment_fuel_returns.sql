DROP TRIGGER trg_inv_document_source_reference_insert;

CREATE TRIGGER trg_inv_document_source_reference_insert
BEFORE INSERT ON inv_documents
WHEN NOT (
 (NEW.source_module IS NULL AND NEW.source_type IS NULL AND NEW.source_id IS NULL)
 OR
 (NEW.source_module='equipment' AND NEW.source_type IN ('fuel_event','fuel_return_event','maintenance_order','part_lifecycle')
  AND NEW.source_id IS NOT NULL)
)
BEGIN
 SELECT RAISE(ABORT,'invalid inventory document source reference');
END;
