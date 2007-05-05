import os
from test_logger import get_test_logger
from unittest import TestCase, TestSuite, TextTestRunner
from Peapod.peapod import getConfig, purgeConfig, peapodConf


class SingletonConfigTest( TestCase ):
    def setUp( self ):
        self.testhome = "."
        self.arglist = {"homedir": self.testhome}

    def singletonConfigTest( self ):
        c = getConfig( self.arglist )
        d = getConfig()
        self.assertEqual( c, d )

    def purgeSingletonTest( self ):
        c = getConfig( self.arglist )
        purgeConfig()
        d = getConfig( self.arglist )
        self.assertNotEqual( c, d )

    def tearDown( self ):
        purgeConfig()


class ConfigTest( TestCase ):
    def setUp( self ):
        self.testhome = "."
        self.arglist = {"homedir": self.testhome}

    def createConfigTest( self ):
        c = peapodConf( self.arglist )
        self.assertNotEqual( c, None )

    def hasDefaultsTest( self ):
        c = peapodConf( self.arglist )
        self.assertNotEqual( c.defaults, None )


class ArbitraryConfigTest( TestCase ):
    def setUp( self ):
        self.testhome = "."
        self.configfile = "newpeapod.xml"
        self.arglist = {"homedir": self.testhome, "configfile": self.configfile}

    def createArbitraryConfig( self ):
        if os.path.exists( os.path.sep.join( (self.testhome, self.configfile) )):
            self.fail( "File exists: " + self.configfile )
        c = peapodConf( self.arglist )
        self.assertNotEqual( c, None )
        if c.feedlist:
            logger.critical( "found feeds" + str( c.feedlist ))
            self.fail( "No feeds should be known" )
        
    def readArbitraryConfig( self ):
        if not os.path.exists( os.path.sep.join( (self.testhome, self.configfile) )):
            self.fail( "File does not exist: " + self.configfile )
        c = peapodConf( self.arglist )
        self.assertNotEqual( c, None )
        if not c.feedlist:
            self.fail( "No feeds are known" )
        os.remove( os.path.sep.join( (self.testhome, self.configfile) ))


def testsuite():
    suite = TestSuite()
    singletonTests = ["singletonConfigTest", "purgeSingletonTest"]
    configTests = ["createConfigTest", "hasDefaultsTest"]
    arbitraryConfigTests = ["createArbitraryConfig", "readArbitraryConfig"]
    suite.addTests( map(SingletonConfigTest, singletonTests))
    suite.addTests( map(ConfigTest, configTests))
    suite.addTests( map(ArbitraryConfigTest, arbitraryConfigTests))
    return suite

if __name__ == "__main__":
    logger = get_test_logger()
    suite = testsuite()
    TextTestRunner(verbosity=2).run(suite)
