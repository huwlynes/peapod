#!/usr/bin/python
from Peapod.peapod import *
import os
import sys
import logging
from time import strftime, localtime

# create an initial logger.  Messages to the screen should be warnings or higher.
logger = logging.getLogger()
console = logging.StreamHandler()
console.setLevel(logging.WARN)
logger.addHandler(console)

# check to see if our user has a ~/.peapod directory - create it if missing
if not os.path.exists( os.path.expanduser( "~/.peapod" ) ):
    logger.warn( "~/.peapod missing - Creating ~/.peapod directory" )
    os.mkdir( os.path.expanduser( "~/.peapod" ) )

# load the config & check for commandline options
configp = peapodConf()

# build file handler with configured level
fh = logging.FileHandler( os.path.expanduser( "~/.peapod/log" ))
fh.setLevel( configp.defaults["log_level"] )
format = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
fh.setFormatter(format)
logger.addHandler(fh)

# the logger must be capable of catching the lowest desired log level.
logger.setLevel( configp.defaults["log_level"] )

if configp.defaults["verbose"]:
    # reset console to deliver more messages
    console.setLevel(logging.INFO)
    if logger.level > logging.INFO:
        logger.setLevel(logging.INFO)

#check that we have bittorrent support unless explicitly turned off
if configp.defaults["bittorrent"]:
    try:
        from BitTorrent.platform import install_translation
    except:
        try:
            from BitTorrent.download import Feedback, Multitorrent
        except:
            logger.debug("Disabling bittorrent support")
            configp.defaults["bittorrent"] = False
else:
    logger.debug("Disabling bittorrent support")

# check to see if our save directory exists - create it if missing
if not os.path.exists( configp.defaults["savedir"] ):
    savedir = configp.defaults["savedir"]
    logger.info("Creating directory for podcasts: " + savedir)
    os.mkdir( savedir )

#create datedir for savestyle=date
datedir = strftime( "%Y-%m-%d", localtime() )
configp.defaults["datedir"] = datedir

#if necessary upgrade the download.log
upgradeDownloadLog( os.path.expanduser( "~/.peapod/download.log" ) )



#get our path so that we can shell out to bittorrent
thisfile = os.path.realpath( sys.argv[0] )
configp.defaults["path"] = os.path.dirname( thisfile )

if configp.defaults["addnew"]:
    logger.debug("Action: add new feed")
    url = configp.defaults["addnew"]
    if configp.defaults["title"]:
        title = configp.defaults["title"]
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
if configp.defaults["copynew"]:
    logger.debug("Action: copy new downloads to mp3 player")
    list = newTracks( "lastcopy.log", configp.defaults )
    list.copyNew( configp.defaults["mp3path"] )

#Sync new podcasts to iPod
if configp.defaults["synciPod"]:
    logger.debug("Action: sync new downloads to ipod")
    list = newTracks( "lastcopy.log", configp.defaults )
    list.synciPod( configp.defaults["ipodpath"] )

# check to see if we are to print out a playlist of new downloads
if configp.defaults["playlist"]:
    logger.debug("Action: print playlist")
    list = newTracks( "lastplay.log", configp.defaults )
    list.playlistNew( configp.defaults["mp3path"] )

#were we asked to forget all the new podcasts
if configp.defaults["forgetnew"]:
    logger.debug("Action: forget all new podcasts")
    list = newTracks( "lastcopy.log", configp.defaults )
    list.updateLog()
    list = newTracks( "lastplay.log", configp.defaults )
    list.updateLog()

# actually download the feeds (assuming we've not done a copynew or playlist
if not ( configp.defaults["copynew"] or configp.defaults["playlist"] or configp.defaults["addnew"] or configp.defaults["forgetnew"] ):
    logger.debug("Action: download new podcasts")
    feedLogDict = feedLog()
    download_dict = downloadList()
    guidlist = download_dict["guids"]
    filelist = download_dict["filenames"]
    list = podcastListXML( configp, feedLogDict, guidlist, filelist )
    list.downloadList()
