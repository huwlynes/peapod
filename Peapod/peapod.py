#!/usr/bin/python
"""
Python podcast client

(C) 2005 Billy Allan.  billy@monkeytwizzle.com
Released under the GPL - see http://www.gnu.org for details.

This script uses the excellent RSS/Atom feed parser from http://feedparser.org and the
"openanything" module from the equally excellent "Dive into Python" http://diveintopython.org/ .
"""

__version__ = "pre1.0"
USER_AGENT = 'Peapod/%s +http://www.peapodpy.org' % __version__
threadcount = 0


######  Import the required modules #######

try:
    import eyeD3
    import gpod
except ImportError:
    pass

import feedparser
import re
import string
import os
import sys
import time
import shutil
import tempfile
import copy
import xml.dom.minidom
from xml.dom import Node
from threading import Thread
from Peapod.tagging import editTags
from urlgrabber.grabber import URLGrabber
from urlgrabber import urlopen
from time import strftime,localtime
import urllib
import urllib2
import urlparse
import logging
if sys.platform.startswith("win"):
    bittorrent = False
else:
    from popen2 import Popen3
from Peapod import OPML
try:
    from Peapod.btclient import mytorrent
except:
    pass

# get a copy of the root logger
logger = logging.getLogger()

#we use this error to signal no change to
#etag or modified when downloading
class PeapodError( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )


def exportfeeds( feedlist ):
    """
    Export feeds to OPML on stdout.
    """
    logger.debug("Exporting feeds")
    opml = OPML.OPML()
    outlines = OPML.OutlineList()
    for key in feedlist.keys():
        feed = feedlist[key]
        o = OPML.Outline()
        o.update({"title":feed["title"],"type":"rss","xmlUrl":feed["url"]})
        logger.debug("* %s %s %s" % (feed["title"], "rss", feed["url"]))
        outlines.add_outline(o)
        outlines.close_outline()
    opml["title"] = "Feeds Exported From Peapod"
    opml.outlines = outlines.roots()
    logger.debug("Writing opml file to stdout")
    opml.output()


class importfeeds:
    """
    Class to import feeds from RSS and OPML sources.
    """
    def __init__( self, feed, peapod, title=None ):
        self.config = getConfig()
        self.feed = feed
        self.title = title
        self.peapod = peapod
        self.feedlist = []


    def get( self ):
        """
        Convert feed source (be it opml, RSS etc) into a list of dictionaries
        containing titles and urls. This list of dictionaries can then be used
        to regenerate the user config file.
        """
        #using urlgrabber so it doesn't matter whether feed is a file or a url
        logger.debug("Opening feed: " + self.feed)
        fd = urlopen( self.feed )
        feed = {}
        #is this an OPML file?
        try:
            outlines = OPML.parse( fd ).outlines
            logger.debug("Feed is OPML")
            for opmlfeed in outlines:
                feed = {}
                feed["title"] = opmlfeed["title"]
                feed["url"] = opmlfeed["xmlUrl"]
                self.feedlist.append( feed )
                logger.debug("Feed has been imported: %s - %s" % (feed["title"], feed["url"]))
        except Exception, e:
            feed = {}
            try:
                if self.title:
                    feed["title"] = self.title
                else:
                    outlines = feedparser.parse( self.feed )["feed"]
                    feed["title"] = outlines.title
                feed["url"] = self.feed
                self.feedlist.append(feed)
                logger.debug("Feed has been imported: %s - %s" % (feed["title"], feed["url"]))
            except Exception, e:
                print "Feedparser exception:", e
                sys.exit(-1)
        self.toXML()


    def toXML( self ):
        """
        Write out imported feeds XML config file.
        """
        from xml.dom.ext import PrettyPrint
        #grab elements out of config object to form basis of xml config file
        p = self.peapod.getElementsByTagName( "peapod" )[0]

        #loop through feed dicts in list adding elements into XML
        for rssfeed in self.feedlist:
            title_node = self.peapod.createElement( "title" )
            title_node.appendChild( self.peapod.createTextNode( rssfeed["title"] ) )
            url_node = self.peapod.createElement( "url" )
            url_node.appendChild( self.peapod.createTextNode( rssfeed["url"] ) )
            feed = self.peapod.createElement( "feed" )
            feed.appendChild( url_node )
            feed.appendChild( title_node )
            p.appendChild( feed )
        try:
            fd = open( os.path.sep.join( (self.config.options["homedir"], "peapod.xml") ), "w" )
            logger.debug("Writing feedlist to " + fd.name)
            PrettyPrint( p, fd )
            fd.close()
        except Exception,e:
            print e


class downloadURL:
    """
    A class to download a single enclosure from a feed.  Redirect requests are
    handled before the download request is made.

    A limited number of filetypes are accepted for download, as defined by a
    hardcoded list of file extensions.  In the case where a pattern match
    fails, a subsequent match is tested based on a list of mime-types.

    BitTorrent downloads are handled by an out-of-process application.
    """
    blockSize = 4096

    def __init__( self, url, basedir, tmpdir='/tmp',filename=None, bittorrent=True, bandwidth=5000, user_agent=USER_AGENT, path=False, content_type=None ):
            self.url = url
            self.basedir = basedir
            self.filename = filename
            self.bandwidth = bandwidth
            self.user_agent = user_agent
            self.path = path
            self.content_type = content_type
            self.goodmimes = [ "audio/x-mpeg","audio/mpeg" ]
            self.tmpdir = tmpdir

            try:
                #use urllib2 to handle redirects before we hand the url off to openanything
                request = urllib2.Request( url, headers={'User-agent':user_agent} )
                opener = urllib2.build_opener()
                logger.debug("Opening connection to: " + url)
                f = opener.open( request )
                #urlgrabber expects unquoted urls
                self.url = urllib.unquote( f.geturl() )
                self.info = f.info()
            except (KeyboardInterrupt, SystemExit):
		sys.exit(0)
            except Exception, e:
                raise IOError, "%s : %s" % ( e, url )

            if ( not re.search( "\.torrent", self.url ) ) or ( not bittorrent ):
                self.torrent = False
            else:
                self.torrent = True

            if self.content_type == "application/x-bittorrent" and bittorrent:
                self.torrent = True
            # get the actual track name
            # chop off any extraneous guff at the end of the URL (ie, blah.mp3?type=podcast)
            self.trackname = urlparse.urlparse( self.url )[2]
            logger.debug("Found trackname: " + self.trackname)

            # also check for not having an mp3/ogg at all (ie, blah.com/sendfeed.php?id=43)
            if not re.search( "\.(mp3|ogg|mov|wav|m4v|mp4|m4a|aac|wmv|pdf)", self.trackname ):
                if self.content_type in self.goodmimes:
                    self.trackname = os.path.split( self.trackname )[1]
                else:
                    self.trackname = None
            else:
                self.trackname = os.path.split( self.trackname )[1]

            if self.torrent:
                logger.debug("Using bittorrent to download file")
                self.track = mytorrent( self.url, self.basedir )
                self.trackname = self.track.filename
                if self.track.status:
                    self.trackname = None

            if self.trackname:
                self.savename = os.path.join( self.basedir, self.trackname )
                logger.debug("Saving podcast as " + self.savename)


    def callbittorrent( self, url, savedir, path ):
        """
        Spawn an external process to fetch an enclosure using BitTorrent.
        """
        logger.debug("Opening connection to btclient.py")
        proc = Popen3( '%s/btclient.py %s %s' % ( path, url, savedir ), True )
        output = proc.fromchild.readlines()
        errors = proc.childerr.read()
        errno = proc.wait()
        if errno:
            raise IOError, errors
        else:
            return 0


    def get( self ):
        """
        Fetch the requested enclosure to a temporary path.  If the file already
        exists in the temporary location, a simple reget should pick up the
        download where it previously left off.  Once the file has been
        completely downloaded, it is moved into the proper location.
        """
        if self.torrent:
            amp = re.compile( '(?P<amp>&)' )
	    whtspc = re.compile( '(?P<whtspc> )' )
	    safe_basedir = whtspc.sub( r'\\\g<whtspc>', self.basedir )
	    safe_path = whtspc.sub( r'\\\g<whtspc>', self.path )
            safe_url = amp.sub( r'\\\g<amp>', self.url )
            self.callbittorrent( safe_url, safe_basedir, safe_path )
	    logger.debug("Safe URL %s" % safe_url)
	    logger.debug("Safe basedir %s" % safe_basedir)
	    logger.debug("Safe path %s" % safe_path)

        else:
            try:
                #save to .peapod dir in basedir
                #allows us to recommence download after a problem
                self.tmpdir = os.path.join(self.tmpdir,".peapod")
                self.tmppath = os.path.join(self.tmpdir,self.trackname)
                if not os.path.isdir(self.tmpdir):
                    logger.debug("Creating directory for temporary file: " + self.tmpdir)
                    os.makedirs(self.tmpdir)
                if not os.path.isfile(self.tmppath):
                    logger.debug("Creating temporary file: " + self.tmppath)
                    fd = open(self.tmppath,'w')
                    fd.close()
            except (KeyboardInterrupt, SystemExit):
		sys.exit()
            except Exception, e:
                logger.warn("Could not save the track : %s" % self.savename)
                raise IOError


            # keep reading from the remote file and saving to disk till we'
            filename = self.tmppath
            try:
                logger.debug("Fetching url")
                grabber = URLGrabber( user_agent=self.user_agent, bandwidth=self.bandwidth )
                grabber.urlgrab( str( self.url ), filename=str(filename), reget='simple' )
                logger.debug( self.url )
                logger.debug( filename )
	    except (KeyboardInterrupt, SystemExit):
		sys.exit()
            except Exception, e:
                e = "%s:%s" % ( self.url, e )
                logger.warn("%s:%s" % ( self.url, e ))
                raise IOError, e

            try:
                logger.debug("moving file to " + self.savename)
                shutil.move( self.tmppath, self.savename )
                #hack to get file permissions back to system defaults
                #since mkstmp uses paranoid permissions
                current_umask = os.umask(0)
                os.umask(current_umask)
                mode = (0666 & (0666 ^ current_umask))
                os.chmod(self.savename, mode)
            except Exception, e:
                logger.warn("Could not create the file %s" % self.savename)
                os.remove( self.tmppath )
                raise IOError


class podcastThreaded( Thread ):
    """
    Update a feed and parse it for new enclosures, using conditional download
    information, if available.  Before downloading, each file is checked
    against a list of known downloads to prevent duplicates.
    """
    message = ""
    log = ""
    feedlog = ""
    title = ""
    options = ""
    url = ""
    maxfetch = 1

   # this is the threaded version of the podcastFeed class.
    def __init__( self, url, title, options, feedLogDict, guidlist, filelist ):
        self.bandwidth = int( options["bandwidth"] ) * 1024
        self.url = url
        self.message = ""
        self.title = title
        self.options = options
        self.feedLogDict = feedLogDict
        self.maxfetch = int( options["maxfetch"] )
        self.guidlist = guidlist
        self.filelist = filelist
        Thread.__init__( self )


    def run( self ):
        message, log, feedlog = self.fetchFeed()
        self.message = message
        self.log = log
        self.feedlog = feedlog


    def makefeedlogentry( self, feed ):
        """
        Generate a string to be appended to the feed log for updating
        conditional download information.
        """
        logger.debug("Writing entry to feed log")
        if feed == None:
            self.feedlog = "%s||None||None\n" % ( self.url )
        else:
            if feed.has_key( "etag" ):
                feed_etag = feed.etag
            else:
                feed_etag = None
            if feed.has_key( "modified" ):
                feed_modified = time.mktime( feed.modified )
            else:
                feed_modified = None
            self.feedlog = self.feedlog + "%s||%s||%s\n" % ( self.url, feed_etag, feed_modified )


    def getcontenturl( self, entry ):
        """
        Extract enclosure URLs and Content-Type information from feed entry.
        """
        content_type = None
        mp3URL = None
        if entry.has_key("enclosures"):
            mp3URL = entry.enclosures[0]['url']
            logger.debug("Found enclosure: " + entry.enclosures[0]["url"])
            if entry.enclosures[0].has_key( "type" ):
                content_type = entry.enclosures[0]['type']
                logger.debug("Content-type: " + entry.enclosures[0]["type"])
            else:
                content_type = None
        elif entry.has_key("links"):
            for link in entry.links:
                if link.has_key("rel") and link["rel"] == "enclosure":
                    logger.debug("Found enclosure: " + link["href"])
                    mp3URL = link["href"]
                    if link.has_key("type"):
                        content_type = link["type"]
                        logger.debug("Content-type: " + link["type"])
                    break
        if mp3URL == '':
            mp3URL = None
        return mp3URL,content_type


    def dowehaveit( self, entry ):
        """
        Check new entry against list of known feed entries and report
        duplicates.
        """
        if entry.has_key( "id" ):
            if entry["id"] in self.guidlist:
                return 1
            else:
                return None


#    def feednewcontent( self ):
#    #don't check last-modified or etag on these conditions
#    if self.options["catchup"] or re.compile( self.title, re.I ).match( self.options["getall"] ) or self.options["getallglobal"]:
#        feed = feedparser.parse( self.url, agent=USER_AGENT)
#    else:
#        #check last-modified or etag, only download if they have changed
#        try:
#            if self.feedLogDict.has_key(self.url):
#                if self.feedLogDict[self.url]["e-tag"]:


    def fetchFeed( self ):
        """
        Fetch feed from host and parse it for enclosures, performing
        conditional downloading if appropriate.  If enclosures are found,
        creates an instance of downloadURL to retrieve the files.
        """
        global threadcount
        numgrabbed = 0
        #don't do conditional download if we are trying to catchup or any of the getall options match
        if self.options["catchup"] or re.compile( self.title, re.I ).match( self.options["getall"] ) or self.options["getallglobal"]:
            logger.debug("Ignoring any conditional download")
            logger.debug("Attempting to parse feed")
            feed = feedparser.parse( self.url, agent=USER_AGENT )
        else:
            #if not catchup use last-modified or ETag to see if feed has changed since last download
            try:
                if self.feedLogDict.has_key( self.url ):
                    if self.feedLogDict[self.url]["e-tag"]:
                        feed = feedparser.parse( self.url, etag=self.feedLogDict[self.url]["e-tag"], agent=USER_AGENT )
                        if feed.status == 304:
                            raise PeapodError, "etag"
                    elif self.feedLogDict[self.url]["modified"]:
                        feed = feedparser.parse( self.url, modified=time.gmtime( float( self.feedLogDict[self.url]["modified"] ) ), agent=USER_AGENT )
                        if feed.status == 304:
                            raise PeapodError, "last-modified"
                    else:
                        try:
                            logger.debug("Attempting to parse feed")
                            feed = feedparser.parse( self.url, agent=USER_AGENT )
                        except Exception,e:
                            logger.warn("Unable to parse feed: " + self.url)
                            threadcount = threadcount -1
                else:
                    logger.debug("Attempting to parse feed")
                    feed = feedparser.parse( self.url, agent=USER_AGENT )
            except PeapodError, e:
                logger.info( str( e.value ) + " unchanged, not fetching: " + str( self.url ))
                threadcount = threadcount - 1
                #we can't just use makefeedlogentry here because we haven't actually downloaded the feed
                self.feedlog = self.feedlog + "%s||%s||%s\n" % ( self.url, self.feedLogDict[self.url]["e-tag"], self.feedLogDict[self.url]["modified"] )
                return self.message, self.log, self.feedlog
            except AttributeError, e:
                logger.info("%s: %s : problem getting url" % ( self.url, e ))
                if feed.has_key( "headers" ):
                    logger.info( feed.headers )
                threadcount = threadcount - 1
                return self.message, self.log, self.feedlog
#            except:
#                print >> sys.stderr, "Failed to fetch/parse %s" % self.url
#                threadcount = threadcount - 1
#                return self.message,self.log

        #update feed.log
        self.makefeedlogentry( feed )

        # if we don't already have a title, then grab one from the feed
        if not self.title:
            # if the feed has no title then just bail out as it's probably gibberish
            if not feed.feed.has_key( 'title' ):
                logger.info("Ignoring feed - no title " + self.url)
                return self.message, self.log, self.feedlog

            self.title = feed['feed']['title']

        # strip out any non-alphanumericals in the title so we can safely(ish) use it as a path-name
        #self.title = re.sub( "\W\W*", "_", self.title )
        #self.options["getall"] = re.sub( "\W\W*", "_", self.options["getall"] )

        logger.info("Fetching podcasts from " + self.title)

        # set the base directory of the feed to the global "savedir" + the sanitised feed title
        if self.options["savestyle"] == "feed":
            basedir = "%s/%s" % ( self.options["savedir"], self.title )
            tmpdir = basedir
        elif self.options["savestyle"] == "date":
            basedir = "%s/%s" % ( self.options["savedir"], self.options["datedir"] )
            tmpdir = self.options["savedir"]
        elif self.options["savestyle"] == "none":
            basedir = self.options["savedir"]
            tmpdir = basedir
        else:
            basedir = self.options["savedir"]
            tmpdir = basedir

        # if we've never seen this feed before, then make a directory for it
        if not os.path.exists( basedir ):
            logger.debug("Creating directory for feed: " + basedir)
            os.makedirs( basedir )

            # this is the first time we've seen the feed - if we've been told only to download
            # the latest feed for new stuff then set the maxfetch counter to "1"
            if self.options["newfeedsingle"] == 1:
                self.maxfetch = 1

        # check to see if we are to over-ride the maxfetch and download everything for this feed
        if re.compile( self.title, re.I ).match( self.options["getall"] ) or self.options["getallglobal"]:
            self.maxfetch = 1000000
            getall = 1
            logger.info("Fetching all podcasts for %s" % self.title)
        else:
            getall = 0

        # loop over each entry in the podcast feed (again, all praise feedparser.org!)
        timelist = []
        feeds = {}
        #make feed_count 3 months in the future so that we can deal with feeds that have a couple of
        #dodgy pubDates
        feed_count = int( time.mktime( time.localtime() ) ) + 7776000
        #before we get to downloading the podcasts it's a good idea to order the feed by published date
        for entry in feed.entries:
            mp3URL,content_type = self.getcontenturl(entry)
            if mp3URL:
                if entry.has_key( "modified_parsed" ):
                    try:
                        time_epoch = time.mktime( entry.modified_parsed )
                    except TypeError:
                        #this is for feeds that advertise pubDate but don't create entries
                        try:
                            grabber = downloadURL( mp3URL, basedir, tmpdir,bittorrent=self.options["bittorrent"], bandwidth=self.bandwidth, content_type=content_type )
                        except IOError:
                            self.makefeedlogentry( None )
                            continue
                        entry["grabber"] = grabber
                        if grabber.info.has_key( "last-modified" ):
                            if feedparser._parse_date( grabber.info["last-modified"] ):
                                time_epoch = time.mktime( feedparser._parse_date( grabber.info["last-modified"] ) )
                            else:
                                time_epoch = feed_count
                                feed_count = feed_count - 1
                        else:
                            time_epoch = feed_count
                            feed_count = feed_count - 1
                else:
                    logger.info("No pubDate information for " + self.title)
                    #podcasts which don't use pubDate use a fake time. These feeds end up getting
                    #read from top to bottom like they would if we were not ordering by time
                    try:
                        grabber = downloadURL( mp3URL, basedir, tmpdir, bittorrent=self.options["bittorrent"], bandwidth=self.bandwidth, path=self.options["path"], content_type=content_type )
                    except (KeyboardInterrupt, SystemExit):
                        sys.exit()
                    except Exception:
                        self.makefeedlogentry( None )
                        continue
                    entry["grabber"] = grabber
                    if grabber.info.has_key( "last-modified" ):
                        time_epoch = time.mktime( feedparser._parse_date( grabber.info["last-modified"] ) )
                    else:
                        time_epoch = feed_count
                        feed_count = feed_count - 1

                #occasionaly you get idiots who put two entries in with the same pubDate
                #we increment the second by 1 so that we get both podcasts
                while 1:
                    if time_epoch in timelist:
                        time_epoch = time_epoch - 1
                    else:
                        break
                timelist.append( time_epoch )
                feeds[time_epoch] = entry

        timelist.sort()
        timelist.reverse()

        #go through the podcasts from latest to earliest
        for time_epoch in timelist:
            entry = feeds[time_epoch]
            # get the "enclosure" tag which should contain our mp3/ogg/whatever
            mp3URL,content_type = self.getcontenturl(entry)
            if not mp3URL:
                #no enclosures so move on to next
                logger.info("No enlosures found.")
                continue

            #quick check against guid first before bothering to head back to the webserver
            if self.dowehaveit( entry ):
                self.maxfetch = self.maxfetch -1
                if self.maxfetch <= 0:
                    break
                else:
                    continue

            # open it as a stream using the "openanything" module from "Dive Into Python" (thanks!)
            if entry.has_key( "grabber" ):
                grabber = entry["grabber"]
            else:
                try:
                    grabber = downloadURL( mp3URL, basedir, tmpdir, bittorrent=self.options["bittorrent"], bandwidth=self.bandwidth, path=self.options["path"], content_type=content_type )
		except (KeyboardInterrupt, SystemExit):
		    sys.exit()
                except Exception, e:
                    logger.info("Unable to download enclosure: " + mp3URL)
                    self.makefeedlogentry( None )
                    continue

            if not grabber.trackname:
                #no filename indicates something went wrong so move on
                logger.info("Not downloading " + mp3URL)
                self.makefeedlogentry( None )
                continue
            else:
                trackname = grabber.trackname
                savename = grabber.savename
                mp3URL = grabber.url

            # check to see if we've already got this track downloaded
            if trackname in self.filelist:

                # we have - so decrease the counter and check to see if we're done
                #check that the time on this podcast isn't in the future. If it is it's probably
                #a bad time. don't decrease maxfetch so that a bad pubdate doesn't clog up the feed
                logger.debug("Already have file.  Skipping download")
                if not int( time_epoch ) > int( time.mktime( time.localtime() ) ):
                    self.maxfetch = self.maxfetch -1
                    if self.maxfetch <= 0:
                        break
                    else:
                        continue
                else:
                    continue

            logger.info("\tDownloading %s -- %s" % (self.title, mp3URL))
            logger.info("\tTrackname " + trackname)
            logger.info("\tSavename " + savename)
            logger.info("\tMime-type " + grabber.info["content-type"])

            if self.options["tellnew"]:
                self.message = self.message + savename + " (" + self.title + ")\n"


            if ( not  ( self.options["dryrun"] or self.options["catchup"] ) ):
                #break for problems reading url
                try:
                    grabber.get()
                except IOError, e:
                    logger.info("Unable to download enclosure " + mp3URL)
                    self.makefeedlogentry( None )
                    break

            # update our log of downloaded tracks
            if entry.has_key( 'id' ):
                self.log = self.log + "%s||%s||%s\n" % ( savename, entry["id"], int( time.time() ) )
            else:
                self.log = self.log + "%s||None||%s\n" % ( savename, int( time.time() ) )

            #if we have python-vorbis or eyed3 re-write the file's id3/ogg tags
            #check that it's an mp3 or ogg to get round m4a corruption problem
            #we have to let bittorrent files through because we don't know what type they are
            if not ( self.options["dryrun"] or self.options["catchup"] or sys.platform.startswith("win") ):
                if grabber.info["content-type"] in ('audio/mpeg','application/ogg','audio/x-mpeg','application/x-bittorrent'):
                    editTags( feed['feed'],entry, self.options, savename )

            #run post command if specified
            if self.options["post"] and not ( self.options["dryrun"] or self.options["catchup"] ):
                os.system( self.options["post"] + " " + savename )

            # update our track counters
            numgrabbed = numgrabbed + 1
            self.maxfetch = self.maxfetch - 1

            # if we've hit our limit them bail out
            if self.maxfetch <= 0:
                break

        # indicate that we've finished with this thread to the global counter
        threadcount = threadcount - 1
        # and return with our messages and log
        return self.message, self.log, self.feedlog


class podcastListXML:
    """
    Manages the spawning of threads to fetch each feed in the list of known
    feeds.  After the threads have all been started, handles writing results to
    the appropriate log files.
    """
    filename = ""
    tlist = []
    message = ""
    max_threads = 1

    def __init__( self, feedLogDict, guidlist, filelist ):
        self.config = getConfig()
        self.guidlist = guidlist
        self.filelist = filelist
        self.max_threads = self.config.options["max_threads"]
        self.feedLogDict = feedLogDict


    def downloadList( self ):
        """
        Loop over the URLs in the feed list and fetch each one.
        """
        for feed_title in self.config.feedlist:
            global threadcount
            feed = self.config.feedlist[feed_title]

            while threadcount >= self.max_threads:
                time.sleep( 1 )

            # skip anything that isn't http - probably lazy, but hey!
            if not re.compile( "^http", re.I ).search( feed["url"] ):
                logger.info("Skipping feed - not http: " + feed["url"])
                continue

            # set the config options for this feed.  We use the defaults then
            # merge in any per-feed settings
            options = copy.deepcopy( self.config.options )
            if feed.has_key( "options" ):
                for k, v in feed["options"].items():
                    logger.debug("Setting feed-specific option: %s = %s" % (k, v))
                    options[k] = v

            # fetch the feed using a thread
            logger.info("...Spawning thread %s for feed url %s" % ( threadcount, feed["url"] ))
            feed_thread = podcastThreaded( feed["url"], feed["title"], options, self.feedLogDict, self.guidlist, self.filelist )
            self.tlist.append( feed_thread )
            feed_thread.start()
            threadcount = threadcount + 1

        for t in self.tlist:
            t.join()
            if t.message:
                if options["tellnew"]:
                    print "Downloaded\n%s" % ( t.message )
                logger.info("Downloaded\n%s" % ( t.message ))
                logger.info("Logged : %s" % ( t.log ))
            if t.log:
                logfile = open( os.path.sep.join( (self.config.options["homedir"], "download.log") ), "a" )
                if not self.config.options["dryrun"]:
                    logger.debug("Appending to " + logfile.name)
                    logfile.write( t.log )
                else:
                    logger.info("Would have logged : %s" % t.log)
                logfile.close()
            if t.feedlog:
                feedlog = open( os.path.sep.join( (self.config.options["homedir"], "feed.log") ), "a" )
                if not self.config.options["dryrun"]:
                    logger.debug("Appending to " + feedlog.name)
                    feedlog.write( t.feedlog )
                else:
                    logger.info("Would have logged : %s" % t.feedlog)
                feedlog.close()


class peapodConf:
    """
    Class to manage the configuration for peapod.  Handles command-line
    arguments, configuration file options and hardcoded defaults.  Options may
    be global or specific to a known feed.

    The configuration file is stored as an xml file.  If one is not present, a
    default can be created.

    Use :

    config = getConfig()
    print config.options["savepath"]
    for feed in config.feedlist:
        print feed[""]
        print feed["url"]
        print feed["options"]["savepath"]
    """
    _instance = None
    defaults = {
                "savedir": "/tmp/podcasts",
                "verbose": 0,
                "log_level": logging.WARN,
                "tellnew": 0,
                "homedir": "~/.peapod",
                "configfile": "peapod.xml",
                "savestyle": "feed",
                "bittorrent": 1,
                "bandwidth" : 0,
                "newfeedsingle": 1,
                "maxfetch": 1,
                "copynew": 0,
                "synciPod": 0,
                "getall": "asd9f98675324l#1234$",
                "getallglobal": 0,
                "playlist": 0,
                "max_threads": 10,
                "mp3path": "/tmp/mp3player",
                "ipodpath": "/media/ipod",
                "dryrun": 0,
                "catchup": 0,
                "forgetnew": 0,
                "addnew": 0,
                "post": 0,
                "export": 0,
                "addnew": 0,
                "title": 0,
                "rewriteID3": 0
               }


    def get_text( self, nodelist ):
        """
        Extract text from the xml tags read in.  Data type is not known at this
        point.
        """
        rc = ""
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc = rc + node.data
        return rc


    def process_options( self, element, opt ):
        """
        Extract value from an option element.  Data type is assumed from the
        string content.  Extracted values are inserted into opt as dictionary
        elements.
        """
        for item in element.childNodes:
            if item.nodeType == Node.ELEMENT_NODE:
                tag = item.nodeName
                value = self.get_text( item.childNodes )
                value = value.strip()
                if re.compile( "^\d+$" ).search( value ):
                    value = int( value )
                if value == "true":
                    value = 1
                if value == "false":
                    value = 0
                opt[tag] = value
        return opt


    def __init__( self, cmd_line=None ):
        self.feedlist = {}
        self.options = copy.deepcopy( self.defaults )
        if cmd_line:
            home = cmd_line.pop( "homedir", self.options["homedir"] )
            self.options["homedir"] = cleanpath( home )

            conf = cmd_line.pop( "configfile", self.options["configfile"] )
            if not os.path.dirname( conf ):
                self.options["configfile"] = os.path.sep.join( (self.options["homedir"], conf) )
            else:
                self.options["configfile"] = cleanpath( conf )
        else:
            self.options["homedir"] = cleanpath( self.options["homedir"] )
            self.options["configfile"] = os.path.sep.join( (self.options["homedir"], self.options["configfile"]) )
            
        logger.debug('Using homedir:' + self.options["homedir"])
        logger.debug('Using config file:' + self.options["configfile"])

        # check to see if our user already has a homedir - create it if missing
        if not os.path.exists( self.options["homedir"] ):
            logger.warn( "Creating user directory: %s" % self.options["homedir"] )
            os.mkdir( self.options["homedir"] )

        self.parse_configfile()

        # merge in command line options to override config file options
        if cmd_line:
            for (k, v) in cmd_line.items():
                self.options[k] = v

        #make sure we've expanded out the paths
        self.options["savedir"] = os.path.expanduser( self.options["savedir"] )


    def parse_configfile( self ):
        """
        Read configuration file and use contents to override default options.
        """
        if not os.path.isfile( self.options["configfile"] ):
            logger.debug("No configuration file found")
            self.create_default_config()
            logger.warn("Created a default configuration file in :")
            logger.warn( self.options["configfile"] )
            logger.warn("Please edit this file to contain your feeds and options.")

            # It is perfectly okay to not exit at this stage.  Because the
            # default configuration that is created has not been parsed, no
            # feeds are stored in memory.  As a result, there is nothing to be
            # done and the whole program completes naturally.

        else:
            data = open( self.options["configfile"] )
            logger.debug("Parsing configuration file" + data.name)
            config = xml.dom.minidom.parseString( data.read() )
            options = {}
            if config.getElementsByTagName( "options" ):
                option_elements = config.getElementsByTagName( "options" )
                for element in option_elements:
                    if element.parentNode.nodeName == "peapod":
                        self.process_options( element, self.options )

            feeds = config.getElementsByTagName( "feed" )
            feedlist = []
            for feed in feeds:
                fop = {}
                title = self.get_text( feed.getElementsByTagName( "title" )[0].childNodes )
                url = self.get_text( feed.getElementsByTagName( "url" )[0].childNodes )
                if feed.getElementsByTagName( "options" ):
                    option_elements = feed.getElementsByTagName( "options" )
                    for element in option_elements:
                        fop = self.process_options( element, fop )
                self.feedlist[title] = {'title': title, 'url': url, 'options': fop}

            data.close()
            self.config = config


    def create_default_config( self ):
        """
        Creates a default configuration file, usually in ~/.peapod/peapod.xml,
        which provides a sample podcast subscription.
        """
        config = """<?xml version='1.0' encoding='UTF-8'?>
<peapod>
    <options>
        <savedir>~/podcasts</savedir>
        <verbose>true</verbose>
    </options>

    <feed>
        <title>LugRadio</title>
        <url>http://www.lugradio.org/episodes.rss</url>
    </feed>
</peapod>
"""
        try:
            fd = open( self.options["configfile"], "w" )
            logger.debug("Writing to file" + fd.name)
            fd.write( config )
            fd.close()
        except:
            logger.critical("Could not create default config file!")
            raise Exception


def getConfig( cmd_line=None ):
    """
    A function to wrap the creation of peapodConf as a singleton class.  Only
    the first call to getConfig will recognise any command line options passed
    to it.
    """
    if not peapodConf._instance:
        peapodConf._instance = peapodConf( cmd_line )
    return peapodConf._instance


def purgeConfig( ):
    """
    A function to unload the config object.  This shouldn't be necessary during
    normal functioning, but is very handy for running test suites over the
    config class.  Note that the object is still only subject to garbage
    collection, and is not destroyed immediately.
    """
    if peapodConf._instance:
        del peapodConf._instance
        peapodConf._instance = None


class newTracks:
    """
    A class to manage actions based on recent changes to the peapod databases.
    Generation of playlists and copying of new files to a device are currently
    included.
    """

    list = []
    lasttime = 0
    logfile = ""
    config = ""

    def __init__( self, logfile ):
        self.logfile = logfile
        self.config = getConfig().options
        # check to see if we've run a copynew before - grab the time if we have
        if os.path.exists( os.path.sep.join( (self.config["homedir"], logfile) )):
            lc = open( os.path.sep.join( (self.config["homedir"], logfile) ), "r" )
            logger.debug("Reading from " + lc.name)
            self.lasttime = lc.readline()
            logger.debug("Last update of %s: %s" % (lc.name, str(self.lasttime)))
            lc.close()
        else:
            self.lasttime = 0


    def copyNew( self, path ):
        """
        Examine the download log for any files which have been downloaded since
        the last run.  Copies files to configured mountpoint for media device.
        """
        if os.path.exists( os.path.sep.join( (self.config["homedir"], "download.log") )):
            log = open( os.path.sep.join( (self.config["homedir"], "download.log") ), "r" )
            logger.debug("Reading from " + log.name)
            while 1:
                line = log.readline()
                if not line:
                    break
                try:
                    filename = line.split( "||" )[0]
                    dtime = line.split( "||" )[2]
                except:
                    logger.warn( "Error in download log : %s\n" % line )
                    continue
                if int( dtime ) > int( self.lasttime ):
                    logger.info("Copying " + filename + " to " + path)
                    if not self.config["dryrun"]:
                        shutil.copyfile( filename, "%s/%s" % ( path, os.path.basename( filename ) ) )
            log.close()
        if not self.config["dryrun"]:
            self.updateLog()


    def synciPod( self, mountPoint ):
        """
        Examine the download log for any files which have been downloaded since
        the last run.  Copies files to iPod.
        """
        mountPoint=mountPoint.encode()
        try:
            itdb=gpod.itdb_parse(mountPoint,None)
        except NameError,e:
            raise Exception("iPod support requires libgpod library and its python bindings")
        if not itdb:
            raise Exception('Cannot open iTunesDB at mount point: %s' % mountPoint)
        try:
            if os.path.exists( os.path.sep.join( (self.config["homedir"], "download.log") )):
                log = open( os.path.sep.join( (self.config["homedir"], "download.log") ), "r" )
                while 1:
                    line = log.readline()
                    if not line:
                        break
                    try:
                        filename = line.split( "||" )[0]
                        dtime = line.split( "||" )[2]
                    except:
                        logger.warn("Error in download log : %s\n" % line )
                        continue
                    if int( dtime ) > int( self.lasttime ):
                        logger.info("Copying %s to %s" % (filename, mountPoint))
                        if not self.config["dryrun"]:
                            self.copyToiPod(itdb, filename )
                log.close()
                if not self.config["dryrun"]:
                    self.updateLog()
        finally:
            if not self.config["dryrun"]:
                gpod.itdb_write(itdb, None)
                logger.info("Updating iTunesDB...")


    def copyToiPod(self,itdb,filename):
        """
        Copy file to iPod via gpod library.
        """
        track = gpod.itdb_track_new()
        pl=gpod.itdb_playlist_podcasts(itdb)
        audiofile = eyeD3.Mp3AudioFile(filename)
        tag = audiofile.getTag()
        for func, attrib in (('getArtist','artist'),
                             ('getTitle','title'),
                             ('getBPM','BPM'),
                             ('getPlayCount','playcount'),
                             ('getAlbum','album')):
            value = getattr(tag,func)()
            if value:
                value = value.encode("utf-8")
                setattr(track,attrib,value)
        track.skip_when_shuffling=0x01
        track.remember_playback_position=0x01
        #track.flag4=0x01
        track.tracklen = audiofile.getPlayTime() * 1000
        gpod.itdb_track_add(itdb, track, -1)
        gpod.itdb_playlist_add_track(pl, track, -1)
        if gpod.itdb_cp_track_to_ipod(track,filename, None)!= 1:
            raise Exception('Unable to copy %s to iPod' % filename)


    def playlistNew( self, path ):
        """
        Examine the download log for any files which have been downloaded since
        the last run.  Print filenames to create a playlist.
        """
        if os.path.exists( os.path.sep.join( (self.config["homedir"], "download.log") )):
            log = open( os.path.sep.join( (self.config["homedir"], "download.log") ), "r" )
            logger.debug("Reading from " + log.name)
            while 1:
                line = log.readline()
                if not line:
                    break
                try:
                    filename = line.split( "||" )[0]
                    dtime = line.split( "||" )[2]
                except:
                    logger.warn( "Error in download log : %s\n" % line )
                    continue
                if int( dtime ) > int( self.lasttime ):
                    # Should this be handled by logging engine?
                    print filename
            log.close()
        if not self.config["dryrun"]:
            self.updateLog()

    def updateLog( self ):
        """
        Update the timestamp for marking new files.  Has the effect of marking
        all downloaded files as old.
        """
        lc = open( os.path.sep.join( (self.config["homedir"], self.logfile) ), "w" )
        logger.debug("Updating logfile: " + lc.name)
        lc.write( "%s" % int( time.time() ) )
        lc.close()


def cleanpath( path ):
    """
    Takes a path and expands any variables and ~ and returns an absolute path
    """
    path = os.path.expanduser( path )
    path = os.path.expandvars( path )
    path = os.path.abspath( path )
    return path


def feedLog():
    """
    Parse feed.log and extract information about known feeds, and any
    associated conditional download information (e-tag, modified timestamps).
    Returns information as a dict, indexed by URL.
    """
    config = getConfig()
    feedLogDict = {}
    entryDict = {}
    if os.path.exists( os.path.sep.join( (config.options["homedir"], "feed.log") )):
        log = open( os.path.sep.join( (config.options["homedir"], "feed.log") ), "r" )
        logger.debug("Reading logfile: " + log.name)
        for line in log.readlines():
            entryDict = {}
            parts = line.split( "||" )
            entryDict["e-tag"] = string.strip( parts[1] )
            entryDict["modified"] = string.strip( parts[2] )
            feedLogDict[parts[0]] = entryDict
        log.close()
        #now clear out the file
        log = open( os.path.sep.join( (config.options["homedir"], "feed.log") ), "w" )
        log.close()
    return feedLogDict


def downloadListFull():
    """
    Parses old version of download.log to extract filenames of previously
    downloaded files.  Returns a list.

    I believe this is no longer used and can be purged.
    """
    #like downloadList but returns full paths not filenames
    config = getConfig()
    filenames = []
    if os.path.exists( os.path.sep.join( (config["homedir"], "download.log") )):
        log = open( os.path.sep.join( (config["homedir"], "download.log") ), "r" )
        logger.debug("Reading logfile: " + log.name)
        while 1:
            line = log.readline()
            if not line:
                break
            parts = line.split( "," )
            filenames.append( parts[0] )
    return filenames


def upgradeDownloadLog( logfile ):
    """
    Upgrade a comma-delimited download.log to new format, using '||' as a
    delimiter.
    """
    if not os.path.exists( logfile ):
        return
    logger.debug("Upgrading download log to new version")
    downloadDict = {}
    log = open( logfile )
    logger.debug("Reading logfile: " + log.name)
    while 1:
        line = log.readline()
        if not line:
            break
        parts = line.split( "," )

        #double-check that we haven't already upgraded this log
        #this shoudn't happen but I'm feeling cautious today
        if string.find( line, "||" ) != -1:
            logger.debug("Detected current version of download log")
            return
        else:
            #we are actually going to upgrade the log so take a copy for safe-keeping
            logger.debug("Saving copy of download log to " + logfile + ".peapodsav" )
            shutil.copyfile( logfile, logfile + ".peapodsav" )

        #if we have podcast names containing ',' we have to be clever to
        #piece the filename back together
        if len( parts ) != 2:
            logger.info("Broken entry in %s: attempting to fix it" % logfile)
            filename=string.join( parts[:-1], ',' )
            downloaddate=parts[-1]
        else:
            filename = parts[0]
            downloaddate = parts[1]
        downloadDict[filename] = [filename, "None", downloaddate]
    log.close()

    #now we've got all the data it's time to write out the new log
    log = open( logfile, 'w' )
    logger.debug("Rewriting log file: " + log.name)
    for key in downloadDict.keys():
        item = downloadDict[key]
        content = item[0] + "||" + item[1] + "||" + item[2]
        log.write( content )
    log.close()
    logger.debug("Upgrade completed")

def downloadList():
    """
    Parse download.log and extract information about previously downloaded
    files.
    Returns a dict, composed of two lists.

    """
    # quicky function to grab the filenames from the download log
    config = getConfig()
    filenames = []
    guids = []
    logdict = {}
    if os.path.exists( os.path.sep.join( (config.options["homedir"], "download.log") )):
        log = open( os.path.sep.join( (config.options["homedir"], "download.log") ), "r" )
        logger.debug("Reading logfile: " + log.name)
        while 1:
            line = log.readline()
            if not line:
                break
            parts = line.split( "||" )
            filename = os.path.split( parts[0] )[1]
            guid = parts[1]
            if guid == "None":
                guid = None
            filenames.append( os.path.split( parts[0] )[1] )
            guids.append( guid )
    logdict["filenames"] = filenames
    logdict["guids"] = guids
    return logdict


#stuff below here is the peapod cli script it should probably be in a separate file
if __name__ == "__main__":

    print "This is a library you should probably be running the 'peapod' script"
    sys.exit(0)

