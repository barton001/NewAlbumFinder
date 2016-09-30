#!/usr/bin/python
#
"""  
Uses the iTunes store web API to find CDs by artists we like 
that we don't have yet.  It does this by:
1) Get a list of the artists and CDs we have by scanning our MP3 directory
2) Getting a list of available CDs for each artist from iTunes
3) Generate an HTML file containing the list of CDs we don't have
4) Saves the list of all CDs from iTunes so that on subsequent runs, it will
   only show you anything new since the last run (disable with -i switch).
"""

DEBUG = False

import urllib, json
import os, sys, time, copy, re, string
import optparse, glob, codecs
import id3tags

appName = "NewAlbumFinder"
appVersion = "1.0.0"

# Initial default values, can override with command line options
MINTRACKS = 8   # skip CDs with less than this number of tracks
musicPath = None

# Use the wxPython GUI?
try:
    import wx
    USE_WX = True
    import NewAlbumFinderGUI
except:
    USE_WX = False
    
def err_exit(msg, status=1):
    print msg
    sys.exit(status)

def print3(*args, **kwargs):
    "Emulate the Python3 print function"
    f = sys.stdout
    sep = ' '
    end = '\n'
    if 'sep' in kwargs.keys():
        sep = kwargs['sep']
    if 'end' in kwargs.keys():
        end = kwargs['end']
    if 'file' in kwargs.keys():
        f = kwargs['file']
    f.write(str(args[0]))
    for item in args[1:]:
        f.write(sep)
        if type(item) not in (type('a'), type(u'a')):
            item = str(item)
        f.write(item)
    f.write(end)
    
def parseCmdLine():
    # Parse command line options
    if sys.platform == 'win32':
        outputDir = "Desktop"
    else:
        outputDir = "."
    parser = optparse.OptionParser(version="%s v%s" % (appName, appVersion))
    parser.add_option("-m", "--mintracks", type="int", default=MINTRACKS, 
        dest="MINTRACKS", help="Skip CDs with less than this number of tracks [default: %default]")
    parser.add_option("-o", "--outdir", type="string", dest="outdir", 
        default=outputDir, help="put output files in FOLDER [default: %default]", metavar="FOLDER")
    parser.add_option("-l", "--logfile", action="store_true", dest="writeLogfile", 
        default=False, help="create a log file [default: %default]")
    parser.add_option("-t", "--tunesdir", type="string", dest="tunesDir", 
        default=musicPath, help="top-level MP3 folder [default: %default]")
    parser.add_option("-y", "--year", type="int", dest="minYear", 
        default=0, help="earliest year to include [default: include all]")
    parser.add_option("-i", "--ignore_previous", action="store_true", dest="ignorePrevious", 
        default=False, help="ignore previous run [i.e. show all CDs]")
    parser.add_option("-n", "--nogui", action="store_true", dest="nogui", default=False,
        help="don't use the graphical interface (i.e. command line mode)")
    parser.add_option("-d", "--debug", action="store_true", dest="debug", default=False,
        help="enable DEBUG mode")
    parser.add_option("-T", "--use_tree", action="store_true", dest="albums_from_dir_structure", default=False,
        help="get album list from directory tree")
    (options, args) = parser.parse_args()
    return options, args

def generateAlbumDataFromPath(path):
    """
    Generate album database as a dictionary of unicode strings
        {artist1:[album1,album2,...], artist2:[album1,...]}
    from the toplevel path of your MP3 file tree.  Assumes that path
    contains a directory for each artist and each artist directory contains
    a directory for each of their albums.
    """
    artistCount = albumCount = 0
    artistList = os.listdir(path)
    albumDB = id3tags.ListDict()
    for artist in artistList:
        artistPath = os.path.join(path, artist)
        if not os.path.isdir(artistPath): continue
        if artist in ("Various Artists","Soundtrack","Unknown"): continue
        artistFiles = os.listdir(artistPath)
        for f in artistFiles:
            subpath = os.path.join(artistPath, f)
            # If file is a directory containing MP3 files, assume it's an album
            if os.path.isdir(subpath) and glob.glob(os.path.join(subpath, "*.mp3")):
                addAlbum2DB(albumDB, artist, f)
    return albumDB

def progressFun(n, msg):
    print msg,
    return True

def addAlbum2DB(db, artist, album):
    if artist not in ("Various Artists","Soundtrack","Unknown",""):
        artist = standardizeArtistName(artist)
        album = standardizeAlbumTitle(album)
        if type(artist) != type(u' '):
            artist = unicode(artist, 'latin-1')
        if type(album) != type(u' '):
            album = unicode(album, 'latin-1')
        if album == u'greatest hits':
            album = artist + ' greatest hits'   # this is how iTunes usually lists greatest hits albums
        db.add(artist, album)
    
def generateAlbumDataFromMP3s(mp3s, progressFun = None):
    """
    Generate album database as a dictionary
        {artist1:[album1,album2,...], artist2:[album1,...]}
    from the ID3 tags in the provided list of MP3 files.  As a shortcut,
    if the album name from the ID3 tag matches the directory name, we assume
    the rest of the MP3s in that directory are from the same artist/album and
    skip reading them.
    """
    albumDB = id3tags.ListDict()
    i = 0
    skipRestOfDirectory = False
    lastDir = None
    for mp3 in mp3s:
        i += 1
        if progressFun:
            keep_going = progressFun(i, "MP3s scanned: %d of %d" % (i, len(mp3s)))
            if not keep_going: return albumDB
        thisDir = os.path.basename(os.path.dirname(mp3))
        if skipRestOfDirectory:
            if thisDir == lastDir:
                continue    # skip this file
            else:
                skipRestOfDirectory = False # we changed directories, so start need to read ID3 tag
        lastDir = thisDir
        if DEBUG: print mp3
        # Try getting artist/album data from v2 tag first since it should be more accurate
        v2tag = id3tags.ID3V2tag(mp3)
        if v2tag.loaded and v2tag.artist != "N/A" and v2tag.album != "N/A":
            album = v2tag.album
            addAlbum2DB(albumDB, v2tag.artist, v2tag.album)
        else:
            # Try version 1 tag
            v1tag = id3tags.ID3V1tag(mp3)
            if v1tag.loaded and v1tag.artist != "N/A" and v1tag.album != "N/A":
                album = v1tag.album
                addAlbum2DB(albumDB, v1tag.artist, v1tag.album)
        try:
            if album == thisDir:
                skipRestOfDirectory = True
        except:
            pass
    return albumDB

def standardizeAlbumTitle(title):
    stdAlbum = title.replace(' & ',' and ').lower()
    # Strip off extra comments in title like "[Explicit version]"
    for stripString in (" (", " ["):
        i = stdAlbum.find(stripString)
        if i > 0: stdAlbum = stdAlbum[0:i]
    # Put trailing 'The' back in front (i.e. change "Slider, The" to "The Slider")
    if stdAlbum[-5:] == ", the":
        stdAlbum = "the " + stdAlbum[:-5]
    if stdAlbum[-4:] == ",the": # in case they left out the space
        stdAlbum = "the " + stdAlbum[:-4]
    # Strip out punctuation
    punctuation = '?:;,.\'"'
    s = stdAlbum
    stdAlbum = ""
    for char in s:
        if char not in punctuation:
            stdAlbum += char
    stdAlbum = string.join(stdAlbum.split())    # reduce multiple spaces to one
    return stdAlbum

def printAlbumDB2CSV(albumDB, stream = sys.stdout):
    "Write album list as comma separated values to stream"
    artistList = list(albumDB.keys())
    artistList.sort()
    for artist in artistList:
        for album in albumDB[artist]:
            stream.write(u'"' + artist + u'","' + album + u'"\n')
 
def capwords(astring):
    words = astring.split()
    capwordlist = [ word.capitalize() for word in words ]
    return u' '.join(capwordlist)
 
def newCDdb2html(newCDdb, filepath):
    "Write the list of new CDs to an HTML file"
    writer = codecs.getwriter('utf-8')
    of = writer(open(filepath, "w"))
    of.write("""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" /><style> body {font-family: sans-serif} </style>
    <title>CDs You Don't Have</title></head><body><h1>CDs You Don't Have</h1>\n""")
    artistList = list(newCDdb.keys())
    artistList.sort()
    for artist in artistList:
        of.write("<h3>%s</h3><table border='1'><tr><th></th><th>Album</th><th>Year</th><th>Genre</th><th>Tracks</th></tr>" % capwords(artist))
        for albumInfo in newCDdb[artist]:
            [year, title, genre, tracks, image, albumLink] = albumInfo
            # Add album to table
            try:
                of.write("<tr><td><a href='%s' target='_new'><img src='%s'/></a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                  % (albumLink, image, title, year, genre, tracks))
            except UnicodeEncodeError:
                pass
        of.write("</table>\n")
    of.write("</body></html>\n")
    of.close()

def artistNamesMatch(artist1, artist2):
    """Return true if artist names are essentially the same by ignoring case
    stripping off any leading 'The' (so 'Beatles' and 'The Beatles' match)"""
    match = False
    if DEBUG: print "Comparing %s <-> %s" % (artist1, artist2)
    a1 = artist1.lower()
    a2 = artist2.lower()
    if a1.find("the ") == 0: a1 = a1[4:]
    if a2.find("the ") == 0: a2 = a2[4:]
    a1 = a1.replace(' & ',' and ')
    a2 = a2.replace(' & ',' and ')
    if a1 == a2:
        match = True    # already match
    else:
        # No match but could be because one name has accented chars and the other doesn't
        try:
            # See if there are any non-ascii characters
            a1ascii = a1.encode('ascii')
            a2ascii = a2.encode('ascii')
            if DEBUG: print "No funny characters"
        except UnicodeEncodeError:
            if DEBUG: print "Unicode decode error!"
            # Funny character in one or both strings, replace them with periods
            a1regexp = a1.encode('ascii','replace').replace('?','.')
            a2regexp = a2.encode('ascii','replace').replace('?','.')
            # Now see if they match as regular expressions
            if DEBUG: print "doing re.match on %s <-> %s" % (a1regexp, a2regexp)
            match = re.match(a1regexp, a2regexp) is not None or re.match(a2regexp, a1regexp) is not None
    if DEBUG: print "match =", match
    return match

def standardizeArtistName(artist):
    """Prevent duplicate artist entries by ignoring case and
    stripping off any leading 'The' (so 'Beatles' and 'The Beatles' match)"""
    a = artist.lower()
    if a.find("the ") == 0: a = a[4:]
    n = a.find(", the")
    if (n > 0) and (n == (len(a) - 5)): a = a[:-5]
    n = a.find(",the")
    if (n > 0) and (n == (len(a) - 4)): a = a[:-4]
    a = a.replace(' & ',' and ')
    return a

def loadHistFile(path):
    """Load the iTunes data from our last run"""
    histData = {}
    if not os.path.exists(path):
        return histData
    f = codecs.open(path, 'r', 'utf8')
    while 1:
        line = f.readline()
        if not line: break
        line = line.strip()
        artist, album = line.split(u'\t')
        if artist in histData.keys():
            histData[artist].append(album)
        else:
            histData[artist] = [album]
    f.close()
    return histData

def saveHistFile(data, path):
    """Save all albums found in iTunes (for our artists)"""
    f = codecs.open(path, 'w', 'utf8')
    artists = list(data.keys())
    artists.sort()
    for artist in artists:
        albums = data[artist]
        for album in albums:
            f.write(artist + u"\t" + album + u"\n")
    f.close()
    
def progressDisplay(i, msg):
    print i, msg
    return True
     
    
class AlbumFinder:
    
    def __init__(self, options, progressFun = progressDisplay):

        self.MINTRACKS = options.MINTRACKS
        self.outputDir = options.outdir
        self.musicPath = options.tunesDir
        self.writeLogfile = DEBUG or options.writeLogfile
        self.minYear = options.minYear
        self.ignorePreviousRun = options.ignorePrevious
        self.progressFun = progressFun

        if self.outputDir == "Desktop" and sys.platform == "win32":
            self.outputDir = os.path.join(os.environ["USERPROFILE"], "Desktop")
        else:
            # This should work with most Linux/Unix versions
            self.outputDir = os.path.join(os.environ["HOME"], "Desktop")
            if not os.path.isdir(self.outputDir):
                self.outputDir = os.environ["HOME"]
       
        if not self.outputDir or not os.path.isdir(self.outputDir):
            err_exit(str(self.outputDir) + " is not a valid output file path.")
        if not self.musicPath:
            self.musicPath = raw_input("Please enter the top-level path to your MP3 files: ")
        if not os.path.isdir(self.musicPath):
            err_exit("Error: " + str(self.musicPath) + " is not a valid folder path for finding your MP3 files.")
            
        # Base URL for searching iTunes Store web service to find all albums by a given artist
        self.iTunesURL = "http://ax.phobos.apple.com.edgesuite.net/WebObjects/MZStoreServices.woa/wa/wsSearch?"
        self.iTunesURL += "{artistTerm}&media=music&entity=album&attribute=artistTerm"


        outFileName = "CDs You Don't Have.html"
        self.outFilePath = os.path.join(self.outputDir, outFileName)
        histFileName = "%s.dat" % (appName)
        self.histFilePath = os.path.join(self.musicPath, histFileName)
        
    def runSearch(self, albumDB):
        if self.ignorePreviousRun:
            histData = {}
        else:
            histData = loadHistFile(self.histFilePath)

        if self.writeLogfile:
            logFname = appName + ".log"
            logFstream = codecs.open(os.path.join(self.outputDir, logFname), "w", encoding='utf8')
        else:
            logFstream = sys.stdout
            
        if DEBUG:
            print "mintracks=", self.MINTRACKS, "outdir=", self.outputDir
            printAlbumDB2CSV(albumDB, logFstream)
            print "Dumped your album list to " + logFname
            #sys.exit()

        # use a copy to track which albums we have that weren't in the database
        CDsNotFound = copy.deepcopy(albumDB)

        newCDcount = 0

        newCDdb = {}     # CDs I don't have yet from artists I like
        uniqueAlbums = {}     # unique artist/album names to avoid duplicates found in iTunes

        artistList = list(albumDB.keys())
        artistList.sort()
        artistNum = len(artistList)
        aCount = 0
        iTunesResults = {}
        
        startTime = time.ctime()

        for artist in artistList:
            aCount += 1
            namePrinted = False
            newCDlist = []
            if not self.progressFun(aCount, string.capwords(artist)):
                return  # user aborted the search
            if self.writeLogfile: 
                logFstream.write("\nSearch iTunes for: " + artist + "\n")
            try:
                artistTerm = urllib.urlencode({"term":artist})
            except:
                a = artist.encode('utf8','replace')
                artistTerm = urllib.urlencode({"term":a})
            url = self.iTunesURL.replace("{artistTerm}", artistTerm)
            if self.writeLogfile: logFstream.write(url)
            f = urllib.urlopen(url)
            json_string = f.read().decode("utf-8")
            f.close()
            if self.writeLogfile: logFstream.write(json_string)
            data = json.loads(json_string)
            if DEBUG: print "found %d results" % data['resultCount']
            if data['resultCount'] == 0: continue
            if self.writeLogfile: logFstream.write("Have albums: " + repr(albumDB[artist]) + u"\n")
            albumList = data['results']
            allAlbums = []      # save all albums found in iTunes for this artist
            for album in albumList:
                name = album['artistName']
                # Itunes will return artists with names similar to the one we asked for.
                # Eliminate any that aren't exact matches.
                if not artistNamesMatch(name, artist):
                    try:
                        if self.writeLogfile: logFstream.write("want artist " + artist + " skipping " + name + '\n')
                    except UnicodeDecodeError:
                        if self.writeLogfile: logFstream.write("want artist " + repr(artist) + " skipping " + repr(name) + '\n')
                    continue
                title = album['collectionName']
                if title[-8:] == '- Single': 
                    if DEBUG: print 'Skipping single'
                    continue
                allAlbums.append(title)
                stdTitle = standardizeAlbumTitle(title)
                if DEBUG: print "  Checking album: ", stdTitle
                genre = album['primaryGenreName']
                tracks = album['trackCount']
                # Provide a way to skip singles and EPs
                if tracks < MINTRACKS:
                    if DEBUG: print "  Skipping ", stdTitle, " too few tracks"
                    continue
                if album['releaseDate']:
                    year = int(album['releaseDate'][0:4])
                else:
                    year = 0
                if copyright in album.keys():
                    match = re.search('\d\d\d\d ', album['copyright'])       # find 1st 4 digit string
                    if match: 
                        year2 = int(match.group(0))
                        # Often releaseDate reflects a re-release date and copyright is original date
                        if year > 0: year = min(year, year2)
                image = album['artworkUrl100']
                albumLink = album['collectionViewUrl']
                if year < self.minYear:
                    if DEBUG: print "  Skipping ", stdTitle, " too few tracks"
                    continue
                haveAlbums = map(standardizeAlbumTitle, albumDB[artist])
                if stdTitle in haveAlbums:
                    if self.writeLogfile: logFstream.write("   have -> " + title + "\n")
                    try:
                        CDsNotFound[artist].remove(stdTitle)
                    except:
                        # might have already deleted this album
                        pass
                    continue
                if artist in histData.keys() and title in histData[artist]:
                    if self.writeLogfile: logFstream.write("   previously saw -> " + title + "\n")
                    continue
                
                # Is it a duplicate?
                key = name.lower() + "," + stdTitle
                if key in uniqueAlbums.keys(): continue
                uniqueAlbums[key] = 1
                
                if DEBUG: print "New album: ", stdTitle, title, haveAlbums
                newCDcount += 1
                newCDlist.append([year, title, genre, tracks, image, albumLink])
            
            if len(newCDlist) > 0:                
                # Sort new CD list by release year (first field)
                newCDlist.sort(reverse=True)
            
                # Save list of new CDs for current artist
                newCDdb[artist] = newCDlist
                
            if len(allAlbums) > 0:
                iTunesResults[artist] = allAlbums
            
            if DEBUG and aCount > 30:
                print "DEBUG mode is enabled.  Stopping after first 30 artists."
                break

        # Output list of CDs we don't have
        if newCDcount:
            print "Generating HTML file: ", self.outFilePath
            newCDdb2html(newCDdb, self.outFilePath)
        print "Found %d CDs you don't have." % (newCDcount)

        # Save current iTunes data
        print "Saving iTunes data in", self.histFilePath
        saveHistFile(iTunesResults, self.histFilePath)
            
        if self.writeLogfile:
            logFstream.write("The following albums were not found in iTunes:")
            printAlbumDB2CSV(CDsNotFound, logFstream)
        print "Started at %s, finished at %s" % (startTime, time.ctime())
        return newCDcount
            
            
if __name__ == "__main__":
    options, args = parseCmdLine()
    DEBUG = options.debug
    if not USE_WX or options.nogui:
        af = AlbumFinder(options)
        if (options.albums_from_dir_structure):
            albumDB = generateAlbumDataFromPath(options.tunesDir)
        else:
            mp3s = id3tags.findMP3s(options.tunesDir)
            albumDB = generateAlbumDataFromMP3s(mp3s, progressFun)
        af.runSearch(albumDB)
    else:
        NewAlbumFinderGUI.main()
    
    
