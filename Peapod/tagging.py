#!/usr/bin/python

import sys
import string
import logging
from time import strftime,localtime

# get root logger
logger = logging.getLogger()

try:
    import eyeD3
    eyed3 = True
    logger.debug("Has eyeD3")
except:
    eyed3 = False
    logger.debug("Does not have eyeD3")

if not sys.platform.startswith("win"):
    from popen2 import Popen3

class id3Comment:
    """
    A class to manage simple reading and writing of id3 tags.
    """

    def __init__(self,filename,taglist = ["Artist","Title","Genre","Album"]):
        self.filename = filename
        self.taglist = taglist
        if eyed3:
            pass
        else:
            raise IOError, "no ID3 support"


    def read(self):
        """
        Read id3 tags stored in mp3 file.  Tags are restricted to the subset
        configured in the constructor.  Returns a dict.
        """
        if eyeD3.isMp3File(str(self.filename)):
            logger.debug("File is an mp3")
            self.tagobject = eyeD3.Tag()
            self.tagobject.link(str(self.filename))
            self.tagobject.setVersion(eyeD3.ID3_V2_3)
        else:
            logger.debug("File is not an mp3")
            raise IOError, "can't ID3 tag %s" % self.filename
        tagdict = {}
        for tag in self.taglist:
            cmd = "content = self.tagobject.get%s()" % str(tag)
            try:
                exec(cmd)
                tagdict[tag] = content
                logger.debug("Found tag: %s = %s" % (tag, content))
            except:
                print "id3 comments read",e
        return tagdict


    def write(self,tagdict,encoding):
        """
        Writes id3 tags to mp3 file.
        """
        for tag in tagdict:
            cmd = "self.tagobject.set%s(%s)" % (str(tag),'tagdict["%s"]' % unicode(tag))
            try:
                exec(cmd)
                logger.debug("Writing tag: %s = %s" % (tag, tagdict[tag]))
            except Exception,e:
                print "id3 comments set",e
                pass
	if encoding == "latin1":
		self.tagobject.setTextEncoding(eyeD3.LATIN1_ENCODING)
	elif encoding == "utf-8":
		self.tagobject.setTextEncoding(eyeD3.UTF_8_ENCODING)
	else:
		self.tagobject.setTextEncoding(eyeD3.UTF_16_ENCODING)
        try:
            self.tagobject.update(eyeD3.ID3_V2_3)
            logger.debug("Committing tags")
        except Exception,e:
            print "id3 write",e


class vorbisComment:
    """
    A class to manage simple reading and writing of vorbis tags.
    """

    def __init__(self,filename):
        self.filename = filename
        self.callVorbisComment()


    def callVorbisComment(self,cmd="--help"):
        """
        Spawns a process to vorbiscomment to handle read and write requests.
        """
        proc = Popen3('vorbiscomment %s' % cmd,True)
        output = proc.fromchild.readlines()
        errors = proc.childerr.read()
        errno = proc.wait()
        if errno:
            raise IOError,string.strip(errors)
        if errors and not output:
            output.append(errors)
        return output


    def write(self,tagdict):
        """
        Writes a set of tags to a vorbis file.
        """
        cmd = "-w %s " % self.filename
        for item in tagdict.keys():
            logger.debug("Writing tag: %s = %s" % (item, tagdict[item]))
            cmd = cmd + '-t "%s=%s" ' % (string.capitalize(item),tagdict[item])
        logger.debug("Committing tags")
        self.callVorbisComment(cmd)


    def read(self):
        """
        Read tags stored in a vorbis file.  Returns a dict.
        """
        cmd = "-l %s" % self.filename
        output = self.callVorbisComment(cmd)
        tagdict = {}
        for line in output:
            tag,content = string.split(line,'=')
            logger.debug("Found tag: %s = %s" % (tag, content))
            if not tag == "":
                tagdict[string.capitalize(tag)] = string.strip(content)
        if tagdict == {}:
            raise IOError,"couldn't read tags from %s" % self.filename
        return tagdict

class Comment:
    """
    A class to abstract the data types away from the tagging process.
    """

    def __init__(self,filename,eyed3,vorbis):
        self.filename = filename
        self.vorbis = vorbis
        self.eyed3 = eyed3
        if not (self.vorbis or self.eyed3):
            raise IOError,"no vorbis or ID3 tagging support"
        try:
            self.comment = id3Comment(self.filename)
            dict = self.comment.read()
            if not dict == {}:
                self.fileformat = "mp3"
            else:
                raise IOError
        except Exception,e:
            try:
                self.comment = vorbisComment(self.filename)
                dict = self.comment.read()
                if not dict == {}:
                    self.fileformat = "vorbis"
                else:
                    raise IOError
            except Exception, e:
                logger.warn("Error initialising vorbis comments")
                raise IOError,"can't read tags: %s" % self.filename


    def read(self):
        """
        Read tags from either mp3 or vorbis file.
        """
        dict = {}
        if self.fileformat == "mp3" and eyed3:
            try:
                self.comment = id3Comment(self.filename)
                dict = self.comment.read()
                return dict
            except Exception,e:
                logger.warn("Error reading ID3 tags")
                pass

        if self.fileformat == "vorbis" and self.vorbis:
            try:
                self.comment = vorbisComment(self.filename)
                dict = self.comment.read()
                return dict
            except Exception,e:
                logger.warn("Error reading vorbis tags")
                pass

        return dict


    def write(self,dict,encoding="utf-16"):
        """
        Write tags to either mp3 or vorbis file.
        """
        try:
	    if self.fileformat == "mp3":
		self.comment.write(dict,encoding)
	    else:
		self.comment.write(dict)
        except Exception,e:
            pass


def editTags(feed,entry,options,filename,taglist=["Artist","Title","Genre","Album"]):
    """
    Writes new tags to filename.  Default values are used to replace empty
    tags.
    """
    tagdict = {}
    try:
        vorbisComment("stuff")
        vorbis = True
        logger.debug("Has vorbis")
    except:
        vorbis = False
        logger.debug("Does not have vorbis")
    try:
        comment = Comment(filename,eyed3,vorbis)
    except IOError:
        return

    tagdict = comment.read()

    #set empty tag to defaults
    rewriteID3=options["rewriteID3"]
    if not tagdict.has_key("Title") or not tagdict["Title"] or rewriteID3:
        ymddate = strftime("%Y-%m-%d",localtime())
        #tagdict["Title"] = "%s-%s" % (feed["title"],ymddate)
        tagdict["Title"] = entry['title']
    if not tagdict.has_key("Genre") or not tagdict["Genre"] or rewriteID3:
        tagdict["Genre"] = "Podcast"
    if not tagdict.has_key("Album") or not tagdict["Album"] or rewriteID3:
        tagdict["Album"] = feed["title"]

    for tag in taglist:
        if options.has_key(tag):
            tagdict[tag] = str(options[tag])
    if comment.fileformat == "mp3":
        comment.write(tagdict,options["ID3encoding"])
    else:
        comment.write(tagdict)
