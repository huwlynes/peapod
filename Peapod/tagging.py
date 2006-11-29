#!/usr/bin/python

try:
    import eyeD3
    eyed3 = True
except:
    eyed3 = False
    
import sys
import string
from time import strftime,localtime
if not sys.platform.startswith("win"):
	from popen2 import Popen3

class id3Comment:
    def __init__(self,filename,taglist = ["Artist","Title","Genre","Album"]):
        self.filename = filename
        self.taglist = taglist
        if eyed3:
            pass
        else:
            raise IOError, "no ID3 support"
    def read(self):
        if eyeD3.isMp3File(str(self.filename)):
            self.tagobject = eyeD3.Tag()
            self.tagobject.link(str(self.filename))
            self.tagobject.setVersion(eyeD3.ID3_V2_3)
        else:
            raise IOError, "can't ID3 tag %s" % self.filename
        tagdict = {}
        for tag in self.taglist:
            cmd = "content = self.tagobject.get%s()" % str(tag)
            try:
                exec(cmd)
                tagdict[tag] = content
            except:
                print "id3 comments read",e
        return tagdict
    def write(self,tagdict):
        for tag in tagdict:
            cmd = "self.tagobject.set%s(%s)" % (str(tag),'tagdict["%s"]' % unicode(tag))
            try:
                exec(cmd)
            except Exception,e:
                print "id3 comments set",e
                pass
        self.tagobject.setTextEncoding(eyeD3.UTF_16_ENCODING)
        try:
            self.tagobject.update(eyeD3.ID3_V2_3)
        except Exception,e:
            print "id3 write",e

class vorbisComment:
    def __init__(self,filename):
        self.filename = filename
        self.callVorbisComment()
    def callVorbisComment(self,cmd="--help"):
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
        cmd = "-w %s " % self.filename
        for item in tagdict.keys():
            cmd = cmd + '-t "%s=%s" ' % (string.capitalize(item),tagdict[item])  
        self.callVorbisComment(cmd)
    def read(self):
        cmd = "-l %s" % self.filename
        output = self.callVorbisComment(cmd)
        tagdict = {}
        for line in output:
            tag,content = string.split(line,'=')
            if not tag == "":
                tagdict[string.capitalize(tag)] = string.strip(content)
        if tagdict == {}:
            raise IOError,"couldn't read tags from %s" % self.filename
        return tagdict

class Comment:
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
                print "ogg",e
                raise IOError,"can't read tags: %s" % self.filename
    def read(self):
        dict = {}
        if self.fileformat == "mp3" and eyed3:
            try:
                self.comment = id3Comment(self.filename)
                dict = self.comment.read()
                return dict
            except Exception,e:
                print "id3-read",e
                pass
                
        if self.fileformat == "vorbis" and self.vorbis:
            try:
                self.comment = vorbisComment(self.filename)
                dict = self.comment.read()
                return dict
            except Exception,e:
                print "vorbis-read",e
                pass
                
        return dict
    def write(self,dict):
        try:
            self.comment.write(dict)
        except Exception,e:
            pass
                

def editTags(feed,entry,options,filename,taglist=["Artist","Title","Genre","Album"]):
    tagdict = {}
    try:
        vorbisComment("stuff")
        vorbis = True
    except:
        vorbis = False
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
    comment.write(tagdict)

