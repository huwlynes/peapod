#!/usr/bin/python
"""
peapod is a command-line podcast downloader
(C) 2005 Billy Allan.  billy@monkeytwizzle.com
Released under the GPL - see http://www.gnu.org for details.
"""
from Peapod.peapod import getConfig, newTracks, feedLog
from Peapod.peapod import importfeeds, exportfeeds, urlparse
from Peapod.peapod import cleanpath, upgradeDownloadLog
from Peapod.peapod import downloadList, podcastListXML
import os
import sys
import logging
from time import strftime, localtime
import getopt

def parse_commandline( arglist=None ):
    """
    Check for commandline arguments.  Uses getopt for argument processing long
    and short style options.
    """
    LOGGER.debug("Parsing command line arguments")
    if not arglist:
        arglist = sys.argv[1:]
    try:
        opts, args = getopt.getopt(arglist, "hDbcdvpm:ag:f",
                                        ["help", "debug", 
                                         "savestyle=", "post=", 
                                          "copynew", "synciPod", 
                                          "playlist", "dryrun", 
                                          "catchup", "mp3path=", 
                                          "ipodpath=","addnew=", 
                                          "getall=", "bandwidth=", 
                                          "forgetnew", "verbose", 
                                          "getallglobal", "export", 
                                          "title=", "homedir=", 
                                          "config="] )
    except getopt.GetoptError,error:
        LOGGER.critical("Error parsing commandline:%s" % error)
        peapod_usage()
        sys.exit( -2 )

    optdict = {}
    for opt, arg in opts:
        if opt in ( "-h", "--help" ):
            peapod_usage()
            sys.exit( -2 )
        elif opt in ( "--config" ):
            optdict["configfile"] = arg
        elif opt in ( "--homedir" ):
            optdict["homedir"] = arg
        elif opt in ( "--savestyle" ):
            optdict["savestyle"] = arg
        elif opt in ( "-c", "--copynew" ):
            optdict["copynew"] = 1
        elif opt in ( "--synciPod" ):
            optdict["synciPod"] = 1
        elif opt in ( "-d", "--dryrun" ):
            optdict["dryrun"] = 1
        elif opt in ( "--catchup" ):
            optdict["catchup"] = 1
        elif opt in ( "-v", "--verbose" ):
            optdict["verbose"] = 1
        elif opt in ( "-D", "--debug" ):
            optdict["log_level"] = logging.DEBUG
        elif opt in ( "-p", "--playlist" ):
            optdict["playlist"] = 1
        elif opt in ( "-m", "--mp3path" ):
            optdict["mp3path"] = arg
        elif opt in ( "--ipodpath" ):
            optdict["ipodpath"] = arg
        elif opt in ( "-g", "--getall" ):
            optdict["getall"] = arg
        elif opt in ( "--bandwidth" ):
            optdict["bandwidth"] = int( arg )
        elif opt in ( "--getallglobal" ):
            optdict["getallglobal"] = 1
        elif opt in ( "--post" ):
            optdict["post"] = arg
        elif opt in ( "-a", "--addnew" ):
            optdict["addnew"] = arg
        elif opt in ( "--title" ):
            optdict["title"] = arg
        elif opt in ( "-f", "--forgetnew" ):
            optdict["forgetnew"] = 1
        elif opt in ( "--export" ):
            optdict["export"] = 1
        else:
            pass

    return optdict


def peapod_usage():
    """
    Display command line usage info to stdout.
    """
    print "%s - Usage" % sys.argv[0]
    print "--help | -h\t\t\tDisplay this message and exit"
    print "--config\t\t\tSpecify a config file to use. Default: \
          ~/.peapod/peapod.xml"
    print "--homedir\t\t\tSpecify a directory to save internal data into. \
          Default: ~/.peapod"
    print "--debug | -D\t\t\tWrites debugging messages to ~/.peapod/log"
    print "--verbose | -v\t\t\tWrites progress information to CONSOLE"
    print "--copynew | -c\t\t\tCopy recent downloads to your mp3 player"
    print "--synciPod \t\t\tSynchronize the podcast library with your iPod"
    print "--savestyle=style \t\t'feed' saves into directories named \
           after the feed"
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
    print "--forgetnew | -f\t\tForget the last copy & playlist dates \
          and set them to \"now\""
    print "--post=command \t\t\t'command' is run against the \
          filename of each new podcast"
    print "--export \t\t\tprints feeds in OPML"


if __name__ == "__main__":
    # create an initial LOGGER.  Messages to the 
    # screen should be warnings or higher.
    LOGGER = logging.getLogger()
    CONSOLE = logging.StreamHandler()
    CONSOLE.setLevel(logging.WARN)
    LOGGER.addHandler(CONSOLE)

    # load the config & check for commandline options
    ARGS = parse_commandline()
    try:
        CONFIG = getConfig(ARGS)
    except:
        LOGGER.critical("Error generating configuration object")
        sys.exit(-1)

    # build file handler with configured level
    FH = logging.FileHandler(os.path.sep.join((CONFIG.options["homedir"], 
                                              "log")))
    FH.setLevel( CONFIG.options["log_level"] )
    FORMAT = logging.Formatter("%(asctime)s %(levelname)s \
                               %(name)s %(message)s")
    FH.setFormatter(FORMAT)
    LOGGER.addHandler(FH)

    # the LOGGER must be capable of catching the lowest desired log level.
    LOGGER.setLevel(CONFIG.options["log_level"])

    if CONFIG.options["verbose"]:
        # reset CONSOLE to deliver more messages
        CONSOLE.setLevel(logging.INFO)
        if LOGGER.level > logging.INFO:
            LOGGER.setLevel(logging.INFO)


    #check that we have bittorrent support unless explicitly turned off
    if CONFIG.options["bittorrent"]:
        try:
            from BitTorrent.platform import install_translation
        except ImportError:
            try:
                from BitTorrent.download import Feedback, Multitorrent
            except ImportError:
                LOGGER.debug("Disabling bittorrent support")
                CONFIG.options["bittorrent"] = False
    else:
        LOGGER.debug("Disabling bittorrent support")


    # check to see if our save directory exists - create it if missing
    if not os.path.exists( CONFIG.options["SAVEDIR"] ):
        SAVEDIR = CONFIG.options["SAVEDIR"]
        LOGGER.info("Creating directory for podcasts: " + SAVEDIR)
        os.mkdir( SAVEDIR )

    #create DATEDIR for savestyle=date
    DATEDIR = strftime( "%Y-%m-%d", localtime() )
    CONFIG.options["DATEDIR"] = DATEDIR

    #if necessary upgrade the download.log
    upgradeDownloadLog(os.path.sep.join((CONFIG.options["homedir"],
                                           "download.log")))

    #get our path so that we can shell out to bittorrent
    THISFILE = os.path.realpath(sys.argv[0])
    CONFIG.options["path"] = os.path.dirname(THISFILE)

    if CONFIG.options["export"]:
        LOGGER.debug("Action: export feeds")
        try:
            exportfeeds(CONFIG.feedlist)
            sys.exit( 0 )
        except OSError,error:
            LOGGER.critical("Export Failed: %s" % error)
            sys.exit( -1 )

    if CONFIG.options["addnew"]:
        LOGGER.debug("Action: add new feed")
        URL = CONFIG.options["addnew"]
        if CONFIG.options["title"]:
            TITLE = CONFIG.options["title"]
        else:
            TITLE = None
        try:
            IMPORTED_FEEDS = importfeeds(URL, CONFIG.config, TITLE)
        except:
            #if this is a path we'll need to normalise it
            if urlparse.urlparse(URL)[0] == '':
                PATH = cleanpath(URL)
            else:
                PATH = URL
            IMPORTED_FEEDS = importfeeds(PATH, CONFIG.config)
        IMPORTED_FEEDS.get()

    # check to see if we are to copy new downloads to the mp3 player
    if CONFIG.options["copynew"]:
        LOGGER.debug("Action: copy new downloads to mp3 player")
        TRACKLIST = newTracks("lastcopy.log")
        TRACKLIST.copyNew( CONFIG.options["mp3path"])

    #Sync new podcasts to iPod
    if CONFIG.options["synciPod"]:
        LOGGER.debug("Action: sync new downloads to ipod")
        TRACKLIST = newTracks( "lastcopy.log" )
        TRACKLIST.synciPod( CONFIG.options["ipodpath"] )

    # check to see if we are to print out a playlist of new downloads
    if CONFIG.options["playlist"]:
        LOGGER.debug("Action: print playlist")
        TRACKLIST = newTracks("lastplay.log")
        TRACKLIST.playlistNew()

    #were we asked to forget all the new podcasts
    if CONFIG.options["forgetnew"]:
        LOGGER.debug("Action: forget all new podcasts")
        TRACKLIST = newTracks("lastcopy.log")
        if not CONFIG.options["dryrun"]:
            TRACKLIST.updateLog()
        TRACKLIST = newTracks("lastplay.log")
        if not CONFIG.options["dryrun"]:
            TRACKLIST.updateLog()

    # actually download the feeds (assuming we've not done a copynew or playlist
    if not ( CONFIG.options["copynew"] \
          or CONFIG.options["synciPod"] \
          or CONFIG.options["playlist"] \
          or CONFIG.options["addnew"] \
          or CONFIG.options["forgetnew"] ):
        LOGGER.debug("Action: download new podcasts")
        FEED_LOGS = feedLog()
        DOWNLOADS = downloadList()
        GUIDS = DOWNLOADS["guids"]
        FILES = DOWNLOADS["filenames"]
        TRACKLIST = podcastListXML( FEED_LOGS, GUIDS, FILES )
        TRACKLIST.downloadList()
