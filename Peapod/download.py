#!/usr/bin/python
"""
this module contains the code that actually does the downloading

author: huw lynes huw@hlynes.com

Released under the GPL - see http://www.gnu.org for details.
"""
import re
import shutil
import os
import sys
import urllib2
from urlgrabber.grabber import URLGrabber
import urlparse
import urllib
import logging
if sys.platform.startswith("win"):
    BITTORRENT = False
else:
    from popen2 import Popen3
try:
    from Peapod.btclient import mytorrent
except:
    pass

__version__ = "pre1.0"
USER_AGENT = 'Peapod/%s +http://www.peapodpy.org.uk' % __version__

# get a copy of the root logger
logger = logging.getLogger()

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
        self.goodmimes = [ "audio/x-mpeg","audio/mpeg"]
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

        if (not re.search( "\.torrent", self.url )) or (not bittorrent):
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
            self.track = mytorrent(self.url, self.basedir)
            self.trackname = self.track.filename
            if self.track.status:
                self.trackname = None

        if self.trackname:
            self.savename = os.path.join(self.basedir, self.trackname)
            logger.debug("Saving podcast as " + self.savename)


    def callbittorrent( self, url, savedir, path ):
        """
        Spawn an external process to fetch an enclosure using BitTorrent.
        """
        logger.debug("Opening connection to btclient.py")
        proc = Popen3('%s/btclient.py %s %s' % (path, url, savedir), True)
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
