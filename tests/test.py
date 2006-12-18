from test_unittest import testsuite as ts_unittest
from test_tagging import testsuite as ts_tagging
import unittest

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTests(ts_unittest())
    suite.addTests(ts_tagging())
    unittest.TextTestRunner(verbosity=1).run(suite)
