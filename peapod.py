#!/usr/bin/python
from Peapod.peapod import *
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
    logger.debug("Parsing command line arguments")
    if not arglist:
        arglist = sys.argv[1:]
    try:
        opts, args = getopt.getopt( arglist, "hDbcdvpm:ag:f", ["help", "debug", "savestyle=", "post=", "copynew","synciPod", "playlist", "dryrun", "catchup", "mp3path=", "ipodpath=","addnew=", "getall=", "bandwidth=", "forgetnew", "verbose", "getallglobal", "export", "title=", "homedir=", "config="] )
    except getopt.GetoptError,e:
        logger.critical("Error parsing commandline")
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
    print "--config\t\t\tSpecify a config file to use. Default: ~/.peapod/peapod.xml"
    print "--homedir\t\t\tSpecify a directory to save internal data into. Default: ~/.peapod"
    print "--debug | -D\t\t\tWrites debugging messages to ~/.peapod/log"
    print "--verbose | -v\t\t\tWrites progress information to console"
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


if __name__ == "__main__":
    # create an initial logger.  Messages to the screen should be warnings or higher.
    logger = logging.getLogger()
    console = logging.StreamHandler()
    console.setLevel(logging.WARN)
    logger.addHandler(console)

    # load the config & check for commandline options
    cmd_line_options = parse_commandline()
    try:
        configp = getConfig( cmd_line_options )
    except:
        logger.critical("Error generating configuration object")
        sys.exit( -1 )

    # build file handler with configured level
    fh = logging.FileHandler( os.path.sep.join( (configp.options["homedir"], "log") ))
    fh.setLevel( configp.options["log_level"] )
    format = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    fh.setFormatter(format)
    logger.addHandler(fh)

    # the logger must be capable of catching the lowest desired log level.
    logger.setLevel( configp.options["log_level"] )

    if configp.options["verbose"]:
        # reset console to deliver more messages
        console.setLevel(logging.INFO)
        if logger.level > logging.INFO:
            logger.setLevel(logging.INFO)


    #check that we have bittorrent support unless explicitly turned off
    if configp.options["bittorrent"]:
        try:
            from BitTorrent.platform import install_translation
        except:
            try:
                from BitTorrent.download import Feedback, Multitorrent
            except:
                logger.debug("Disabling bittorrent support")
                configp.options["bittorrent"] = False
    else:
        logger.debug("Disabling bittorrent support")


    # check to see if our save directory exists - create it if missing
    if not os.path.exists( configp.options["savedir"] ):
        savedir = configp.options["savedir"]
        logger.info("Creating directory for podcasts: " + savedir)
        os.mkdir( savedir )

    #create datedir for savestyle=date
    datedir = strftime( "%Y-%m-%d", localtime() )
    configp.options["datedir"] = datedir

    #if necessary upgrade the download.log
    upgradeDownloadLog( os.path.sep.join( (configp.options["homedir"], "download.log") ))

    #get our path so that we can shell out to bittorrent
    thisfile = os.path.realpath( sys.argv[0] )
    configp.options["path"] = os.path.dirname( thisfile )

    if configp.options["export"]:
        logger.debug("Action: export feeds")
        try:
            exportfeeds( configp.feedlist )
            sys.exit( 0 )
        except Exception,e:
            logger.critical("Export Failed")
            sys.exit( -1 )

    if configp.options["addnew"]:
        logger.debug("Action: add new feed")
        url = configp.options["addnew"]
        if configp.options["title"]:
            title = configp.options["title"]
        else:
            title = None
        try:
            feedimport = importfeeds( url, configp.config, title )
        except:
            #if this is a path we'll need to normalise it
            if urlparse.urlparse( url )[0] == '':
                path = cleanpath( url )
            else:
                path = url
            feedimport = importfeeds( path, configp.config )
        feedimport.get()

    # check to see if we are to copy new downloads to the mp3 player
    if configp.options["copynew"]:
        logger.debug("Action: copy new downloads to mp3 player")
        list = newTracks( "lastcopy.log" )
        list.copyNew( configp.options["mp3path"] )

    #Sync new podcasts to iPod
    if configp.options["synciPod"]:
        logger.debug("Action: sync new downloads to ipod")
        list = newTracks( "lastcopy.log" )
        list.synciPod( configp.options["ipodpath"] )

    # check to see if we are to print out a playlist of new downloads
    if configp.options["playlist"]:
        logger.debug("Action: print playlist")
        list = newTracks( "lastplay.log" )
        list.playlistNew( configp.options["mp3path"] )

    #were we asked to forget all the new podcasts
    if configp.options["forgetnew"]:
        logger.debug("Action: forget all new podcasts")
        list = newTracks( "lastcopy.log" )
        if not configp.options["dryrun"]:
            list.updateLog()
        list = newTracks( "lastplay.log" )
        if not configp.options["dryrun"]:
            list.updateLog()

    # actually download the feeds (assuming we've not done a copynew or playlist
    if not ( configp.options["copynew"] or configp.options["synciPod"] or configp.options["playlist"] or configp.options["addnew"] or configp.options["forgetnew"] ):
        logger.debug("Action: download new podcasts")
        feedLogDict = feedLog()
        download_dict = downloadList()
        guidlist = download_dict["guids"]
        filelist = download_dict["filenames"]
        list = podcastListXML( feedLogDict, guidlist, filelist )
        list.downloadList()
