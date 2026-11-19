import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import workflow as w


class LeaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "queue.db"
        w.enqueue(self.db, 4096, 3, "sample", "a" * 40)

    def test_expired_worker_cannot_submit_after_reassignment(self):
        with patch("workflow.time.time", return_value=100):
            first = w.claim(self.db, "one")
            self.assertIsNone(w.claim(self.db, "two"))
        with patch("workflow.time.time", return_value=100 + w.LEASE + 1):
            second = w.claim(self.db, "two")
            with self.assertRaises(ValueError):
                w.submit(self.db, first, {})
            w.renew(self.db, second)
            w.submit(self.db, second, {"commit": "b" * 40})
            self.assertIsNone(w.claim(self.db, "three"))

    def test_overlapping_jobs_rejected(self):
        with self.assertRaises(ValueError):
            w.enqueue(self.db, 4098, 4, "overlap", "a" * 40)

    def test_concurrent_workers_have_one_winner(self):
        with ThreadPoolExecutor(10) as pool:
            leases = list(pool.map(lambda i: w.claim(self.db, str(i)), range(10)))
        self.assertEqual(1, sum(job is not None for job in leases))

    def test_prerequisite_blocks_dispatch_until_integration(self):
        w.enqueue(self.db, 4100, 4, "next", "a"*40, [1])
        first = w.claim(self.db, "worker")
        w.submit(self.db, first, {"commit":"a"*40})
        self.assertIsNone(w.claim(self.db, "other"))
        with w.transaction(self.db) as conn:
            conn.execute("UPDATE jobs SET state='integrated' WHERE id=1")
        self.assertEqual("next", w.claim(self.db, "other")["name"])
