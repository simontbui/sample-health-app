import unittest
from setup import batch_sql, expected_counts
from benchmark import query


class GeneratorTests(unittest.TestCase):
    def test_default_scale(self):
        counts = expected_counts(5_000_000)
        self.assertEqual(counts['document'],5_000_000)
        self.assertEqual(sum(counts.values()),92_500_000)

    def test_atomic_checkpoint(self):
        statement = batch_sql(201,400)
        self.assertIn('generate_series(101,200)',statement)
        self.assertIn('generate_series(801,1600)',statement)
        self.assertTrue(statement.strip().startswith('BEGIN;'))
        self.assertTrue(statement.strip().endswith('COMMIT;'))
        self.assertGreater(statement.index('last_document=400'),statement.index('INSERT INTO diagnosis'))

    def test_encounter_scoped_search(self):
        statement = query('E11.9',.65,True,4_500_000)
        self.assertIn('dx.encounter_id=e.id',statement)
        self.assertIn('m.encounter_id=e.id',statement)
        self.assertIn('d.id>4500000',statement)
        self.assertIn('ORDER BY d.id LIMIT 50',statement)


if __name__ == '__main__':
    unittest.main()
