import os
import shutil
from test_logger import get_test_logger
from unittest import TestCase, TestSuite, TextTestRunner
from Peapod import tagging

# need to have access to known mp3 and vorbis files for comparison purposes

class ID3ReadingTest( TestCase ):
    def setUp( self ):
        self.filename = "sinwaves.mp3"

    def openID3Test( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( self.filename, i.filename )

    def readID3ArtistTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Tester", i.read()["Artist"] )

    def readID3AlbumTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Testsuite", i.read()["Album"] )

    def readID3TitleTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Sinwaves", i.read()["Title"] )

    def readID3GenreTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Noise", i.read()["Genre"] )

class ID3WritingTest( TestCase ):
    def setUp( self ):
        self.orig_filename = "sinwaves.mp3"
        self.new_filename = "test.mp3"
        shutil.copy( self.orig_filename, self.new_filename )

    def writeID3ArtistTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Artist": "NewArtist"})
        self.assertEqual( i.read()["Artist"], "NewArtist" )

    def writeID3AlbumTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Album": "NewAlbum"})
        self.assertEqual( i.read()["Album"], "NewAlbum" )

    def writeID3TitleTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Title": "NewTitle"})
        self.assertEqual( i.read()["Title"], "NewTitle" )

    def writeID3GenreTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Genre": "NewGenre"})
        self.assertEqual( i.read()["Genre"], "NewGenre" )

    def tearDown( self ):
        os.remove( self.new_filename )

class VorbisReadingTest( TestCase ):
    def setUp( self ):
        self.filename = "sinwaves.ogg"

    def openVorbisTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( self.filename, i.filename )

    def readVorbisArtistTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Tester", i.read()["Artist"] )

    def readVorbisAlbumTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Testsuite", i.read()["Album"] )

    def readVorbisTitleTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Sinwaves", i.read()["Title"] )

    def readVorbisGenreTest( self ):
        i = tagging.Comment( self.filename, True, True )
        self.assertEqual( "Noise", i.read()["Genre"] )

class VorbisWritingTest( TestCase ):
    def setUp( self ):
        self.orig_filename = "sinwaves.ogg"
        self.new_filename = "test.ogg"
        shutil.copy( self.orig_filename, self.new_filename )

    def writeVorbisArtistTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Artist": "NewArtist"})
        self.assertEqual( i.read()["Artist"], "NewArtist" )

    def writeVorbisAlbumTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Album": "NewAlbum"})
        self.assertEqual( i.read()["Album"], "NewAlbum" )

    def writeVorbisTitleTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Title": "NewTitle"})
        self.assertEqual( i.read()["Title"], "NewTitle" )

    def writeVorbisGenreTest( self ):
        i = tagging.Comment( self.new_filename, True, True )
        i.write({"Genre": "NewGenre"})
        self.assertEqual( i.read()["Genre"], "NewGenre" )

    def tearDown( self ):
        os.remove( self.new_filename )

def testsuite():
    suite = TestSuite()
    tests = ['openID3Test', 'readID3ArtistTest', 'readID3AlbumTest', 'readID3TitleTest', 'readID3GenreTest']
    suite.addTests(map(ID3ReadingTest, tests))
    tests = ['writeID3ArtistTest', 'writeID3AlbumTest', 'writeID3TitleTest', 'writeID3GenreTest']
    suite.addTests(map(ID3WritingTest, tests))
    tests = ['openVorbisTest', 'readVorbisArtistTest', 'readVorbisAlbumTest', 'readVorbisTitleTest', 'readVorbisGenreTest']
    suite.addTests(map(VorbisReadingTest, tests))
    tests = ['writeVorbisArtistTest', 'writeVorbisAlbumTest', 'writeVorbisTitleTest', 'writeVorbisGenreTest']
    suite.addTests(map(VorbisWritingTest, tests))
    return suite

if __name__ == "__main__":
    logger = get_test_logger()
    suite = testsuite()
    TextTestRunner(verbosity=2).run(suite)
