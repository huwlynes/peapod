#!/usr/bin/python

"""
 (C) 2006 Huw Lynes.  huw@peapodpy.org
 Released under the GPL - see http://www.gnu.org for details.

short script to check peapod dependencies
useful for remotely debugging problems
"""


try:
    import BitTorrent
except Exception,e:
    print "Bittorrent problem:",e
else:
    print "Bittorrent Version:", BitTorrent.version
        
try:
    import eyeD3
except Exception,e:
    print "eyeD3 Problem:",e
else:
    print "EyeD3 Version:",eyeD3.eyeD3Version
    

try:
    from Peapod.tagging import vorbisComment
    comment = vorbisComment("/dev/null")
    version = comment.callVorbisComment(cmd="--version")
except Exception,e:
    print "VorbisComment Problem:",e
else:
    print version
    
try:
    import urlgrabber
except Exception,e:
    print "URLgrabber Problem:",e
else:
    print "URLgrabber Version:",urlgrabber.__version__
    
try:
    import xml
except Exception,e:
    print "PyXML Problem:", e
else:
    print "PyXML Version:",xml.__version__
