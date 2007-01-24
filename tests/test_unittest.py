from test_logger import get_test_logger
from unittest import TestCase, TestSuite, TextTestRunner

class UnittestEngineTest( TestCase ):
    def runPositiveTest( self ):
        self.assertEqual( 1, 1 )

    def runNegativeTest( self ):
        self.assertNotEqual( 1, 0 )

def testsuite():
    tests = ['runPositiveTest', 'runNegativeTest']
    return TestSuite(map(UnittestEngineTest, tests))

if __name__ == "__main__":
    logger = get_test_logger()
    suite = testsuite()
    TextTestRunner(verbosity=2).run(suite)
