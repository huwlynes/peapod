#!/usr/bin/python

# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Bram Cohen, Uoti Urpala and John Hoffman
# modified to form btclient.py by Huw Lynes


from __future__ import division


import sys
import os
import threading
from time import time, strftime
from signal import signal, SIGWINCH
from cStringIO import StringIO
from string import find

#this is needed for bittorrent 4.2 and up
try:
    from BitTorrent.platform import install_translation
    install_translation()
    __btversion__ = 4.2
except:
    __btversion__ = 1.0


from BitTorrent.download import Feedback, Multitorrent
from BitTorrent.defaultargs import get_defaults
from BitTorrent.parseargs import parseargs, printHelp
from BitTorrent.zurllib import urlopen
from BitTorrent.bencode import bdecode
from BitTorrent.ConvertedMetainfo import ConvertedMetainfo
from BitTorrent import configfile
from BitTorrent import BTFailure
from BitTorrent import version

noneerror = 0

def fmtsize(n):
    s = str(n)
    size = s[-3:]
    while len(s) > 3:
        s = s[:-3]
        size = '%s,%s' % (s[-3:], size)
    if n > 999:
        unit = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
        i = 1
        while i + 1 < len(unit) and (n >> 10) >= 999:
            i += 1
            n >>= 10
        n /= (1 << 10)
        size = '%s (%.0f %s)' % (size, n, unit[i])
    return size


class HeadlessDisplayer(object):

    def __init__(self, doneflag):
        self.doneflag = doneflag

        self.done = False
        self.percentDone = ''
        self.timeEst = ''
        self.downRate = '---'
        self.upRate = '---'
        self.shareRating = ''
        self.seedStatus = ''
        self.peerStatus = ''
        self.errors = []
        self.file = ''
        self.downloadTo = ''
        self.fileSize = ''
        self.numpieces = 0

    def set_torrent_values(self, name, path, size, numpieces):
        self.file = name
        self.downloadTo = path
        self.fileSize = fmtsize(size)
        self.numpieces = numpieces

    def finished(self):
        self.done = True
        self.downRate = '---'
        self.display({'activity':'download succeeded', 'fractionDone':1})

    def error(self, errormsg):
        noneerror = 0
        newerrmsg = strftime('[%H:%M:%S] ') + errormsg
        self.errors.append(newerrmsg)
        self.display({})
        self.errors = []


    def display(self, statistics):
        for err in self.errors:
            print 'ERROR:' + err + '\n'




class DL(Feedback):

    def __init__(self, metainfo, config):
        self.doneflag = threading.Event()
        self.metainfo = metainfo
        self.config = config

    def run(self):
        self.d = HeadlessDisplayer(self.doneflag)
        try:
            self.multitorrent = Multitorrent(self.config, self.doneflag,
                                             self.global_error)
            # raises BTFailure if bad
            metainfo = ConvertedMetainfo(bdecode(self.metainfo))
            torrent_name = metainfo.name_fs
            if self.config['save_as']:
                if self.config['save_in']:
                    raise BTFailure('You cannot specify both --save_as and '
                                    '--save_in')
                saveas = self.config['save_as']
            elif self.config['save_in']:
                saveas = os.path.join(self.config['save_in'], torrent_name)
            else:
                saveas = torrent_name

            self.d.set_torrent_values(metainfo.name, os.path.abspath(saveas),
                                metainfo.total_bytes, len(metainfo.hashes))
            self.torrent = self.multitorrent.start_torrent(metainfo,
                                self.config, self, saveas)
        except BTFailure, e:
            print str(e)
            return 1
        except AttributeError, e:
            print str(e)
            return 1
        self.get_status()
        self.multitorrent.rawserver.listen_forever()
        self.d.display({'activity':'shutting down', 'fractionDone':0})
        self.torrent.shutdown()

    def reread_config(self):
        try:
            newvalues = configfile.get_config(self.config, 'btdownloadcurses')
        except Exception, e:
            self.d.error('Error reading config: ' + str(e))
            return
        self.config.update(newvalues)
        # The set_option call can potentially trigger something that kills
        # the torrent (when writing this the only possibility is a change in
        # max_files_open causing an IOError while closing files), and so
        # the self.failed() callback can run during this loop.
        for option, value in newvalues.iteritems():
            self.multitorrent.set_option(option, value)
        for option, value in newvalues.iteritems():
            self.torrent.set_option(option, value)

    def get_status(self):
        self.multitorrent.rawserver.add_task(self.get_status,
                                             self.config['display_interval'])
        status = self.torrent.get_status(self.config['spew'])
        self.d.display(status)

    def global_error(self, level, text):
        self.d.error(text)

    def error(self, torrent, level, text):
        self.d.error(text)

    def failed(self, torrent, is_external):
        self.doneflag.set()
        return 1

    def finished(self, torrent):
        self.d.finished()
        if self.config["selfish"]:
            self.doneflag.set()


class mytorrent:
    def __init__(self,url,save_in,selfish=1):
        self.status = 0
        if __btversion__ >= 4.2:
            uiname = 'bittorrent-console'
        else:
            uiname = 'btdownloadheadless'
        defaults = get_defaults(uiname)

        try:
            config, args = configfile.parse_configuration_and_args(defaults,
                                      uiname)

            config["url"] = url
            config["save_in"] = save_in
            config["selfish"] = selfish


            if args:
                if config['responsefile']:
                    raise BTFailure, 'must have responsefile as arg or ' \
                          'parameter, not both'
                config['responsefile'] = args[0]
            try:
                if config['responsefile']:
                    h = file(config['responsefile'], 'rb')
                    metainfo = h.read()
                    h.close()
                elif config['url']:
                    h = urlopen(config['url'])
                    metainfo = h.read()
                    h.close()
                else:
                    raise BTFailure('you need to specify a .torrent file')
            except IOError, e:
                raise BTFailure('Error reading .torrent file: ', str(e))
        except BTFailure, e:
            print str(e)
            self.status = 1

        if not self.status:
            self.config = config
            self.metainfo = metainfo
            try:
                self.metadict = bdecode(metainfo)
                self.filename = self.metadict["info"]["name"]
            except BTFailure,e:
                print str(e)
                self.status = 1
                self.metadict = None
                self.filename = None
        else:
            self.config = None
            self.metainfo = None

    def run(self):
        if self.status:
            return self.status
        dl = DL(self.metainfo, self.config)
        code = dl.run()
        return code

if __name__ == "__main__":

    selfish = 1

    def quick_usage():
        print "btclient.py url save_dir [seed]"
        print "url \t\t url of torrent"
        print "save_dir \t path to save directory"
        print "seed \t\t set for btclient to continue seeding when finished"

    if len(sys.argv) == 3:
        url = sys.argv[1]
        save_dir = sys.argv[2]
    elif len(sys.argv) == 4:
        url = sys.argv[1]
        save_dir = sys.argv[2]
        selfish = 0
    else:
        quick_usage()
        sys.exit(1)

    torrent = mytorrent(url,save_dir,selfish)
    print "Downloading:",torrent.filename
    ret = torrent.run()
    sys.exit(ret)

