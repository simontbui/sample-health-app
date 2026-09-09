"""Offline checks for the large generator. No Docker/database access."""
import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

large=load('large',ROOT/'scripts/setup-large.py')
bench=load('bench',ROOT/'scripts/benchmark.py')

class GeneratorChecks(unittest.TestCase):
    def test_exact_fanout(self):
        ids=range(1,81)
        meds=[2+min(i%4,4-i%4) for i in ids]
        dx=[2+i%5 for i in ids]
        enc=[1+min((i//4)%4,4-(i//4)%4) for i in ids]
        self.assertEqual((sum(meds),sum(dx),sum(enc)),(240,320,160))
        self.assertEqual((min(meds),max(meds),min(dx),max(dx),min(enc),max(enc)),(2,4,2,6,1,3))
        n=5_000_000
        counts=large.expected_counts(n)
        self.assertEqual(counts['clinical.medication'],sum(meds)*(n//80))
        self.assertEqual(counts['clinical.diagnosis'],sum(dx)*(n//80))
        self.assertEqual(counts['clinical.encounter'],sum(enc)*(n//80))
        self.assertEqual(sum(counts.values()),122_500_000)

    def test_resume_ranges(self):
        n=5_000_000
        ranges=[(start,min(start+19999,n)) for start in range(1,n+1,20000)]
        self.assertEqual(len(ranges),250)
        self.assertEqual(ranges[-1],(4_980_001,5_000_000))
        for index,(start,end) in enumerate(ranges):
            self.assertEqual((end//2)-(start+1)//2+1,10000)
            if index:
                self.assertEqual(start,ranges[index-1][1]+1)
        statement=large.batch_sql(20001,40000,n)
        self.assertIn('generate_series(10001,20000)',statement)
        self.assertIn('generate_series(20001,40000)',statement)
        self.assertTrue(statement.rstrip().endswith('COMMIT;'))
        self.assertLess(statement.index('INSERT INTO separated.diagnosis_confidence'),
                        statement.index('UPDATE ingest.large_benchmark SET last_document=40000'))

    def test_atomic_reset(self):
        with patch.object(large,'sql') as execute:
            large.bootstrap(5_000_000,20_000,True)
        text=execute.call_args.args[0]
        self.assertLess(text.index('BEGIN;'),text.index('DROP SCHEMA'))
        self.assertLess(text.index('INSERT INTO ingest.large_benchmark'),text.rindex('COMMIT;'))
        with patch.object(large,'sql') as execute:
            large.bootstrap(5_000_000,20_000,False)
        self.assertNotIn('DROP SCHEMA',execute.call_args.args[0])

    def test_late_page_predicates(self):
        for layout in ('clinical','separated'):
            text=bench.query(layout,'E11.9','0.65',True,4_500_000)
            self.assertIn('d.id>4500000',text)
            self.assertEqual(text.count('EXISTS'),2)
            self.assertIn('ORDER BY d.id LIMIT 50',text)

    def test_python_syntax(self):
        for path in (ROOT/'scripts').glob('*.py'):
            ast.parse(path.read_text())

if __name__=='__main__':
    unittest.main()
