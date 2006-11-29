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
import getopt
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
if sys.platform.startswith("win"):
	bittorrent = False
else:
	from popen2 import Popen3
from Peapod import OPML
try:
	from Peapod.btclient import mytorrent
except:
	pass

#we use this error to signal no change to
#etag or modified when downloading
class PeapodError( Exception ):
    def __init__( self, value ):
        self.value = value
    def __str__( self ):
        return repr( self.value )

#export feeds to OPML on stdout, reads in feedlist from PeapodConf
def exportfeeds( feedlist ):
    opml = OPML.OPML()
    outlines = OPML.OutlineList()
    for key in feedlist.keys():
        feed = feedlist[key]
        o = OPML.Outline()
        o.update({"title":feed["title"],"type":"rss","xmlUrl":feed["url"]})
        outlines.add_outline(o)
        outlines.close_outline()
    opml["title"] = "Feeds Exported From Peapod"
    opml.outlines = outlines.roots()
    opml.output()
    
class importfeeds:
    """
    class to import RSS feeds from files, urls, RSS and OPML
    """
    def __init__( self, feed, peapod, title=None ):
        self.feed = feed
        self.title = title
        self.peapod = peapod
        self.feedlist = []
        
    def get( self ):
        """
        convert feed source (be it opml, RSS etc) into a list of dictionaries 
        containing titles and urls. This list of dictionaries can then be used to
        generate a config file
        """
        #using urlgrabber so it doesn't matter whether feed is a file or a url
        fd = urlopen( self.feed )
        feed = {}
        #is this an OPML file?
        try:
            outlines = OPML.parse( fd ).outlines
            for opmlfeed in outlines:
                feed = {}
                feed["title"] = opmlfeed["title"]
                feed["url"] = opmlfeed["xmlUrl"]
                self.feedlist.append( feed )
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
                    
            except Exception, e:
                print "Feedparser exception:", e
                sys.exit(-1)
        self.toXML()
        
    def toXML( self ):
        """
        write out imported feeds XML config file
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
            fd = open( os.path.expanduser( "~/.peapod/peapod.xml" ), "w" )
            PrettyPrint( p, fd )
            fd.close()
        except Exception,e:
            print e

class downloadURL:
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
                   f = opener.open( request )
                   #urlgrabber expects unquoted urls
                   self.url = urllib.unquote( f.geturl() )
                   self.info = f.info()
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

           # also check for not having an mp3/ogg at all (ie, blah.com/sendfeed.php?id=43)
            if not re.search( "\.(mp3|ogg|mov|wav|m4v|mp4|m4a|aac|wmv)", self.trackname ):
                if self.content_type in self.goodmimes:
			self.trackname = os.path.split( self.trackname )[1]
		else:
			self.trackname = None
            else:
                self.trackname = os.path.split( self.trackname )[1]
           
            if self.torrent:
                self.track = mytorrent( self.url, self.basedir )
                self.trackname = self.track.filename
                if self.track.status:
                    self.trackname = None
           
            if self.trackname:
                self.savename = os.path.join( self.basedir, self.trackname )
                
    def callbittorrent( self, url, savedir, path ):
        proc = Popen3( '%s/btclient.py %s %s' % ( path, url, savedir ), True )
        output = proc.fromchild.readlines()
        errors = proc.childerr.read()
        errno = proc.wait() 
        if errno:
            raise IOError, errors
        else:
            return 0
            
    def get( self ):
        
        if self.torrent:
            amp = re.compile( '(?P<amp>&)' )
            safe_url = amp.sub( r'\\\g<amp>', self.url )
            self.callbittorrent( safe_url, self.basedir, self.path )
                
        else:
            try:                                                                       
                       #save to .peapod dir in basedir
		       #allows us to recommence download after a problem
		       self.tmpdir = os.path.join(self.tmpdir,".peapod")
		       self.tmppath = os.path.join(self.tmpdir,self.trackname)
		       print self.tmppath
		       print self.tmpdir
		       if not os.path.isdir(self.tmpdir):
		           os.makedirs(self.tmpdir)
		       if not os.path.isfile(self.tmppath):
		       	   fd = open(self.tmppath,'w')
		           fd.close()
            except Exception, e:
            	print e                                                                 
                raise IOError, "Could not save the track : %s" % self.savename                                                                      


            # keep reading from the remote file and saving to disk till we'    
            filename = self.tmppath
            try:
                grabber = URLGrabber( user_agent=self.user_agent, bandwidth=self.bandwidth )
                grabber.urlgrab( str( self.url ), filename=str(filename), reget='simple' )
            except Exception, e:
                e = "%s:%s" % ( self.url, e )
                raise IOError, e                                                              
                
            try:
                shutil.move( self.tmppath, self.savename )
                #hack to get file permissions back to system defaults
                #since mkstmp uses paranoid permissions
                current_umask = os.umask(0)
                os.umask(current_umask)
                mode = (0666 & (0666 ^ current_umask))
                os.chmod(self.savename, mode)
            except Exception, e:
            	print e
                os.remove( self.tmppath )
                raise IOError, "Could not create the file %s" % self.savename


class podcastThreaded( Thread ):

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
   
   def getcontenturl( self, entry):
       content_type = None
       mp3URL = None
       if entry.has_key("enclosures"):
           mp3URL = entry.enclosures[0]['url']
           if entry.enclosures[0].has_key( "type" ):
               content_type = entry.enclosures[0]['type']
           else:
               content_type = None
       elif entry.has_key("links"):
           for link in entry.links:
       	       if link.has_key("rel") and link["rel"] == "enclosure":
                   mp3URL = link["href"]
                   if link.has_key("type"):
                    	content_type = link["type"]
                   break
       if mp3URL == '':
           mp3URL = None
       return mp3URL,content_type
       
   def dowehaveit( self, entry ):
       if entry.has_key( "id" ):
           if entry["id"] in self.guidlist:
               return 1
           else:
               return None
               
#   def feednewcontent( self ):
#	#don't check last-modified or etag on these conditions
#	if self.options["catchup"] or re.compile( self.title, re.I ).match( self.options["getall"] ) or self.options["getallglobal"]:
#		feed = feedparser.parse( self.url, agent=USER_AGENT)
#	else:
#		#check last-modified or etag, only download if they have changed
#		try:
#			if self.feedLogDict.has_key(self.url):
#				if self.feedLogDict[self.url]["e-tag"]:
				

   def fetchFeed( self ):

       global threadcount
       numgrabbed = 0
       #don't do conditional download if we are trying to catchup or any of the getall options match
       if self.options["catchup"] or re.compile( self.title, re.I ).match( self.options["getall"] ) or self.options["getallglobal"]:
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
                           feed = feedparser.parse( self.url, agent=USER_AGENT )
		       except Exception,e:
		           print e
			   threadcount = threadcount -1
               else:
                   feed = feedparser.parse( self.url, agent=USER_AGENT )
           except PeapodError, e:
               if self.options["verbose"]:
                   print str( e.value ) + " unchanged, not fetching: " + str( self.url )
               threadcount = threadcount - 1
	       #we can't just use makefeedlogentry here because we haven't actually downloaded the feed
               self.feedlog = self.feedlog + "%s||%s||%s\n" % ( self.url, self.feedLogDict[self.url]["e-tag"], self.feedLogDict[self.url]["modified"] )
               return self.message, self.log, self.feedlog
           except AttributeError, e:
               if self.options["verbose"]:
                   print "%s: %s : problem getting url" % ( self.url, e )
		   if feed.has_key( "headers" ):
			print feed.headers
               threadcount = threadcount - 1
               return self.message, self.log, self.feedlog
#       except:
#           print >> sys.stderr, "Failed to fetch/parse %s" % self.url
#           threadcount = threadcount - 1
#           return self.message,self.log
               
       #update feed.log
       self.makefeedlogentry( feed )

       # if we don't already have a title, then grab one from the feed
       if not self.title:
           # if the feed has no title then just bail out as it's probably gibberish
           if not feed.feed.has_key( 'title' ):
               return self.message, self.log, self.feedlog

           self.title = feed['feed']['title']
 
       # strip out any non-alphanumericals in the title so we can safely(ish) use it as a path-name
       self.title = re.sub( "\W\W*", "_", self.title )
       self.options["getall"] = re.sub( "\W\W*", "_", self.options["getall"] )

       if self.options["verbose"]:
           print "Fetching podcasts from " + self.title

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
           
       # if we've never seen this feed before, then make a directory for it
       if not os.path.exists( basedir ):
           os.makedirs( basedir )
               
           # this is the first time we've seen the feed - if we've been told only to download
           # the latest feed for new stuff then set the maxfetch counter to "1"
           if self.options["newfeedsingle"] == 1:
               self.maxfetch = 1

       # check to see if we are to over-ride the maxfetch and download everything for this feed
       if re.compile( self.title, re.I ).match( self.options["getall"] ) or self.options["getallglobal"]:
           self.maxfetch = 1000000
           getall = 1
           if self.options["verbose"]:
               print "Fetching all podcasts for %s" % self.title
       else:
           getall = 0

       # loop over each entry in the podcast feed (again, all praise feedparser.org!)
       timelist = []
       feeds = {}
       #make feed_count 3 months in the future so that we can deal with feeds that have a couple of
       #dodgy pubDates
       feed_count = int( time.mktime( time.localtime() ) ) + 7776000
       #before we get to downloading the podcasts it's a ggod idea to order the feed by published date
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
                   if self.options["verbose"]:
                       print self.title + " : no pubDate"
                   #podcasts which don't use pubDate use a fake time. These feeds end up getting
                   #read from top to bottom like they would if we were not ordering by time
                   try:
                       grabber = downloadURL( mp3URL, basedir, tmpdir, bittorrent=self.options["bittorrent"], bandwidth=self.bandwidth, path=self.options["path"], content_type=content_type )
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
               print self.title, "no enclosures"
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
               except Exception, e:
                   if self.options["verbose"]:
                       print e
		   self.makefeedlogentry( None )
                   continue
                   
           if not grabber.trackname:
               #no filename indicates something went wrong so move on
               if self.options["verbose"]:
                   print "Not downloading %s" % mp3URL
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
               if not int( time_epoch ) > int( time.mktime( time.localtime() ) ):
                   self.maxfetch = self.maxfetch -1 
                   if self.maxfetch <= 0:
                       break
                   else:
                       continue
               else:
                   continue
               

           if self.options["verbose"]:
               print "\tDownloading " + self.title + " -- " + mp3URL
               print "\tTrackname " + trackname
               print "\tSavename " + savename
               print "\tMime-type " + grabber.info["content-type"]

           if self.options["tellnew"]:
               self.message = self.message + savename + " (" + self.title + ")\n"
           

           if ( not  ( self.options["dryrun"] or self.options["catchup"] ) ): 
               #break for problems reading url
               try:
                   grabber.get()
               except IOError, e:
                   sys.stderr.write( str( e ) )
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
           if self.options["post"]:
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

   filename = ""
   tlist = []
   message = ""
   config = ""
   max_threads = 1

   def __init__( self, config, feedLogDict, guidlist, filelist ):
       self.config = config
       self.guidlist = guidlist
       self.filelist = filelist
       self.max_threads = self.config.defaults["max_threads"]
       self.feedLogDict = feedLogDict

   def downloadList( self ):
       # loop over the feed URL's and fetch each one
       for feed_title in self.config.feedlist:
           global threadcount
           feed = self.config.feedlist[feed_title]

           while threadcount >= self.max_threads:
               time.sleep( 1 )

           # skip anything that isn't http - probably lazy, but hey!
           if not re.compile( "^http", re.I ).search( feed["url"] ):
               continue

           # set the config options for this feed.  We use the defaults then
           # merge in any per-feed settings
           options = copy.deepcopy( self.config.defaults )
           if feed.has_key( "options" ):
               for k, v in feed["options"].items():
                   options[k] = v

           # fetch the feed using a thread
           if self.config.defaults["verbose"]:
               print "...Spawning thread %s for feed url %s" % ( threadcount, feed["url"] )
           feed_thread = podcastThreaded( feed["url"], feed["title"], options, self.feedLogDict, self.guidlist, self.filelist )
           self.tlist.append( feed_thread )
           feed_thread.start()
           threadcount = threadcount + 1

       for t in self.tlist:
           t.join()
           if t.message:
               if self.options["verbose"] or self.options["tellnew"]:
                   print "Downloaded\n%s" % ( t.message )
                   if self.options["verbose"]:
                       print "Logged : %s" % ( t.log )
           if t.log:
               logfile = open( os.path.expanduser( "~/.peapod/download.log" ), "a" )
               if not self.config.defaults["dryrun"]:
                   logfile.write( t.log )
               else:
                   print "Would have logged : %s" % t.log
               logfile.close()
           if t.feedlog:
               feedlog = open( os.path.expanduser( "~/.peapod/feed.log" ), "a" )
               if not self.config.defaults["dryrun"]:
                   feedlog.write( t.feedlog )
               else:
                   print "Would have logged : %s" % t.feedlog
               feedlog.close()



class peapodConf:
    """
    Class to parse the ~/.peapod/peapod.xml file.
    It will create a default one if it's missing.

    Use :

    config = peapodConf()
    print config.defaults["savepath"]
    for feed in config.feedlist:
        print feed[""]
        print feed["url"]
        print feed["options"]["savepath"]
    """
    parsed = 0
    feedlist = {}
    defaults = {
                "savedir": "/tmp/podcasts", 
                "verbose": 0, 
                "tellnew": 0, 
                "homedir": "~/.peapod", 
                "savestyle": "feed", 
                "incoming": "/tmp/peapod", 
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
        rc = ""
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc = rc + node.data
        return rc

    def process_options( self, element, opt ):
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

    def __init__( self ):
        if not self.parsed:
            if not os.path.isfile( os.path.expanduser( '~/.peapod/peapod.xml' ) ):
                self.create_default_config()
                print "\nCreated a default configuration file in :\n"
                print "\t %s\n" % os.path.expanduser( "~/.peapod/peapod.xml" )
                print "\nPlease edit this file to contain your feeds and options.\n"
                sys.exit( -1 )
            else:
                data = open( os.path.expanduser( "~/.peapod/peapod.xml" ) )
                config = xml.dom.minidom.parseString( data.read() )
                options = {}
                if config.getElementsByTagName( "options" ):
                    option_elements = config.getElementsByTagName( "options" )
                    for element in option_elements:
                        if element.parentNode.nodeName == "peapod":
                            self.process_options( element, self.defaults )

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
                self.parse_commandline()
                #config.unlink()
                self.parsed = 1
        #make sure we've expanded out the paths
        self.defaults["savedir"] = os.path.expanduser( self.defaults["savedir"] )
        self.config = config

    def parse_commandline( self):
       # check for commandline argument - we do this second so commandline > peapod.conf
       try:
           opts, args = getopt.getopt( sys.argv[1:], "hbcdvpm:ag:f", ["help", "savestyle=", "post=", "copynew","synciPod", "playlist", "dryrun", "catchup", "mp3path=", "ipodpath=","addnew=", "getall=", "bandwidth=", "forgetnew", "verbose", "getallglobal", "export", "title="] )
       except getopt.GetoptError,e:
           print "options error",e
           peapod_usage()
           sys.exit( -2 )
       for opt, arg in opts:
            if opt in ( "-h", "--help" ):
                peapod_usage()
                sys.exit( -2 )
    	    elif opt in ( "--savestyle" ):
                self.defaults["savestyle"] = arg
            elif opt in ( "-c", "--copynew" ):
                self.defaults["copynew"] = 1
            elif opt in ("--synciPod" ):
                self.defaults["synciPod"] = 1
            elif opt in ( "-d", "--dryrun" ):
                self.defaults["dryrun"] = 1
            elif opt in ( "--catchup" ):
                self.defaults["catchup"] = 1
            elif opt in ( "-v", "--verbose" ):
                self.defaults["verbose"] = 1
            elif opt in ( "-p", "--playlist" ):
                self.defaults["playlist"] = 1
            elif opt in ( "-m", "--mp3path" ):
                self.defaults["mp3path"] = arg
            elif opt in ( "--ipodpath" ):
                self.defaults["ipodpath"] = arg
            elif opt in ( "-g", "--getall" ):
                self.defaults["getall"] = arg
            elif opt in ( "--bandwidth" ):
                self.defaults["bandwidth"] = int( arg )
            elif opt in ( "--getallglobal" ):
	            self.defaults["getallglobal"] = 1
            elif opt in ( "--post" ):
                self.defaults["post"] = arg
            elif opt in ( "-a", "--addnew" ):
                self.defaults["addnew"] = arg
            elif opt in ( "--title" ):
            	self.defaults["title"] = arg
            elif opt in ( "-f", "--forgetnew" ):
                self.defaults["forgetnew"] = 1
            elif opt in ( "--export" ):
                try:
                    exportfeeds( self.feedlist )
                except Exception,e:
                    print "Export Failed:",e
                    sys.exit(-3)
                else:
                    sys.exit(0)

    def create_default_config( self ):
        config = """<?xml version='1.0' encoding='UTF-8'?>
<peapod>
    <options>
        <savedir>/tmp/podcasts</savedir>
        <verbose>true</verbose>
    </options>
    
    <feed>
        <title>LugRadio</title>
        <url>http://www.lugradio.org/episodes.rss</url>
    </feed>
</peapod>
"""
        try:
            fd = open( os.path.expanduser( "~/.peapod/peapod.xml" ), "w" )
            fd.write( config )
            fd.close()
        except:
            print "Could not create default config file!"
            sys.exit( -1 )


class newTracks:

   list = []
   lasttime = 0
   logfile = ""
   config = ""

   def __init__( self, logfile, config ):
       self.logfile = logfile
       self.config = config
       # check to see if we've run a copynew before - grab the time if we have
       if os.path.exists( os.path.expanduser( "~/.peapod/%s" % logfile ) ):
           lc = open( os.path.expanduser( "~/.peapod/%s" % logfile ), "r" )
           self.lasttime = lc.readline()
           lc.close()
       else:
           self.lasttime = 0

   def copyNew( self, path ):

       # open the download log and check for any files which have been downloaded since the last run
       if os.path.exists( os.path.expanduser( "~/.peapod/download.log" ) ):
           log = open( os.path.expanduser( "~/.peapod/download.log" ), "r" )
           while 1:
               line = log.readline()
               if not line:
                   break
               try:
                   filename = line.split( "||" )[0]
                   dtime = line.split( "||" )[2]
               except:
                   sys.stderr.write( "Error in download log : %s\n" % line )
                   continue
               if int( dtime ) > int( self.lasttime ):
                   if self.config["verbose"]:
                       print "Copying " + filename + " to " + path
                   shutil.copyfile( filename, "%s/%s" % ( path, os.path.basename( filename ) ) )
           log.close()
       self.updateLog()
   
   def synciPod( self, mountPoint ):
     mountPoint=mountPoint.encode()
     try:
         itdb=gpod.itdb_parse(mountPoint,None)
     except NameError,e:
         raise Exception("iPod support requires libgpod library and its python bindings")
     if not itdb:
         raise Exception('Cannot open iTunesDB at mount point: %s' % mountPoint)
     try:
         if os.path.exists( os.path.expanduser( "~/.peapod/download.log" ) ):
             log = open( os.path.expanduser( "~/.peapod/download.log" ), "r" )
             while 1:
                 line = log.readline()
                 if not line:
                     break
                 try:
                     filename = line.split( "||" )[0]
                     dtime = line.split( "||" )[2]
                 except:
                     sys.stderr.write( "Error in download log : %s\n" % line )
                     continue
                 if int( dtime ) > int( self.lasttime ):
                     if self.config["verbose"]:
                         print "Copying " + filename + " to " + mountPoint
                     self.copyToiPod(itdb, filename )
             log.close()
             self.updateLog()
     finally:
         gpod.itdb_write(itdb, None)
         print "Updating iTunesDB..."
   
   def copyToiPod(self,itdb,filename):
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
       # open the download log and check for any files which have been downloaded since the last run
       if os.path.exists( os.path.expanduser( "~/.peapod/download.log" ) ):
           log = open( os.path.expanduser( "~/.peapod/download.log" ), "r" )
           while 1:
               line = log.readline()
               if not line:
                   break
               try:
                   filename = line.split( "||" )[0]
                   dtime = line.split( "||" )[2]
               except:
                   sys.stderr.write( "Error in download log : %s\n" % line )
                   continue
               if int( dtime ) > int( self.lasttime ):
                   print filename
                           
           log.close()
       self.updateLog()

   def updateLog( self ):
       # update the time of our run
       lc = open( os.path.expanduser( "~/.peapod/%s" % self.logfile ), "w" )
       lc.write( "%s" % int( time.time() ) )
       lc.close()


def cleanpath( path ):
    """
    takes a path and expands any variables and ~ and returns an absolute path
    """
    path = os.path.expanduser( path )
    path = os.path.expandvars( path )
    path = os.path.abspath( path )
    return path

def peapod_usage():
   # quicky function to print some help
   print "PeaPod - Usage"
   print "--help | -h\t\t\tThis message"
   print "--copynew | -c\t\t\tCopy recent downloads to your mp3 player"
   print "--synciPod \t\t\tSynchronize the podcast library with your iPod"
   print "--savestyle=style \t\t'feed' saves into directories named after the feed"
   print "              \t\t\t'date' saves into YYMMDD directories"
   print "--playlist | -p\t\t\tPrint out a playlist of recent downloads"
   print "--mp3path=path | -m path\tPath to your mp3 player"
   print "--ipodpath=path \t\tMount point of your iPod"
   print "--addnew=url\t\t\tAdd a new feed to peapod"
   print '--title="a title"\t\tSelect a title when using --addnew'
   print "--getall=\"title\"\t\tGrab all of the podcasts for this feed"
   print "--getallglobal\t\t\tGrab all of the podcasts for all feeds"
   print "--dryrun | -d\t\t\tRun without downloading for testing purposes only"
   print "--catchup \t\t\tLog new podcasts but don't download them."
   print "--forgetnew | -f\t\tForget the last copy & playlist dates and set them to \"now\""
   print "--post=command \t\t\t'command' is run against the filename of each new podcast"
   print "--export \t\t\tprints feeds in OPML"

def feedLog():
    #feed.log contains a list of feeds and e-tags or last-modified headers
    #this information allows us to not keep downloading unchanged feeds
    feedLogDict = {}
    entryDict = {}
    if os.path.exists( os.path.expanduser( "~/.peapod/feed.log" ) ):
        log = open( os.path.expanduser( "~/.peapod/feed.log" ), "r" )
        for line in log.readlines():
            entryDict = {}
            parts = line.split( "||" )
            entryDict["e-tag"] = string.strip( parts[1] )
            entryDict["modified"] = string.strip( parts[2] )
            feedLogDict[parts[0]] = entryDict
        log.close()
        #now clear out the file
        log = open( os.path.expanduser( "~/.peapod/feed.log" ), 'w' )
        log.close()
    return feedLogDict

def downloadListFull():
    #like downloadList but returns full paths not filenames
    filenames = []
    if os.path.exists( os.path.expanduser( "~/.peapod/download.log" ) ):
        log = open( os.path.expanduser( "~/.peapod/download.log" ) )
        while 1:
            line = log.readline()
            if not line:
                break
            parts = line.split( "," )
            filenames.append( parts[0] )
    return filenames


def upgradeDownloadLog( logfile ):
    """this function is here to allow us to seamlessly upgrade to the new log format"""
    if not os.path.exists( logfile ):
        return
    downloadDict = {}
    log = open( logfile )
    while 1:
        line = log.readline()
        if not line:
            break
        parts = line.split( "," )
        
        #double-check that we haven't already upgraded this log
        #this shoudn't happen but I'm feeling cautious today
        if string.find( line, "||" ) != -1:
            return
        else:
            #we are actually going to upgrade the log so take a copy for safe-keeping
            shutil.copyfile( logfile, os.path.expanduser( "~/.peapod/download.log" ) + ".peapodsav" )
        
        #if we have podcast names containing ',' we have to be clever to
        #piece the filename back together
        if len( parts ) != 2:
            print "Broken entry in %s: attempting to fix it" % logfile
            filename=string.join( parts[:-1], ',' )
            downloaddate=parts[-1]
        else:
            filename = parts[0]
            downloaddate = parts[1]
        downloadDict[filename] = [filename, "None", downloaddate]
    log.close()
    
    #now we've got all the data it's time to write out the new log
    log = open( logfile, 'w' )
    for key in downloadDict.keys():
        item = downloadDict[key]
        content = item[0] + "||" + item[1] + "||" + item[2]
        log.write( content )
    log.close() 
    
    
def downloadList():
   # quicky function to grab the filenames from the download log
   filenames = []
   guids = []
   logdict = {}
   if os.path.exists( os.path.expanduser( "~/.peapod/download.log" ) ):
       log = open( os.path.expanduser( "~/.peapod/download.log" ) )
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

