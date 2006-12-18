from unittest import TestCase, TestSuite

class UnittestEngineTest( TestCase ):
    def runPositiveTest( self ):
        self.assertEqual( 1, 1 )

    def runNegativeTest( self ):
        self.assertNotEqual( 1, 0 )

def testsuite():
    tests = ['runPositiveTest', 'runNegativeTest']
    return TestSuite(map(UnittestEngineTest, tests))
