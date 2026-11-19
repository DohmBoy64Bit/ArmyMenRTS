import tempfile
import contextlib
import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import workflow as w
import rules


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

    def test_smallest_ready_first_with_address_tiebreak(self):
        w.enqueue(self.db, 5000, 1, "blocked", "a"*40, [1])
        w.enqueue(self.db, 6000, 2, "higher", "a"*40)
        w.enqueue(self.db, 5100, 2, "lower", "a"*40)
        self.assertEqual([w.claim(self.db,"agent")["name"] for _ in range(3)],
                         ["lower","higher","sample"])

    def test_refresh_required_after_three_integrations(self):
        with contextlib.redirect_stdout(io.StringIO()):
            w.refresh_rules(self.db)
        for i in range(2):
            w.enqueue(self.db, 5000+i, 1, "extra", "a"*40)
        with w.transaction(self.db) as conn:
            conn.execute("UPDATE jobs SET state='integrated' WHERE id<=2")
            w.require_refresh(conn)
            conn.execute("UPDATE jobs SET state='integrated'")
            with self.assertRaises(ValueError):
                w.require_refresh(conn)
        with contextlib.redirect_stdout(io.StringIO()):
            w.refresh_rules(self.db)
        with w.transaction(self.db) as conn:
            w.require_refresh(conn)

    def test_wrong_rea_target_or_entry_rejected(self):
        path = self.db.parent / "observation.json"
        record = {"evidence_id":"ev_"+"a"*64, "operation":"read_function_instructions",
                  "subject":{"digest":{"sha256":w.DIGEST}},
                  "normalized_result":{"instructions":["RET"],"procedure":{"address":"0x404560",
                      "body":{"ranges":[{"start":"0x404560","end":"0x404569"}]}}}}
        path.write_text(json.dumps(record))
        self.assertEqual(rules.check_observation(path,{"rva":0x4560,"size":10},w.DIGEST),record["evidence_id"])
        for rva,size,digest in [(0x4561,10,w.DIGEST),(0x4560,9,w.DIGEST),(0x4560,10,"wrong")]:
            with self.assertRaises(ValueError):
                rules.check_observation(path,{"rva":rva,"size":size},digest)

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
