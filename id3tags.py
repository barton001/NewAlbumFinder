#!/usr/bin/python
#
"Class for reading ID3 tags from MP3 files"

import sys, struct, glob, os

DEBUG = False
DEBUG2 = False

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

# Note: TCON is used for the genre
FID2longName = {'TALB':'Album Title','TCOM':'Composer','TDAT':'Date','TYER':'Year',
    'TENC':'Encoded By','TPE2':'Band/Accompaniment','TRCK':'Track No.',
    'TPUB':'Publisher','TPE1':'Lead Performer','TCON':'Content Type',
    'TIT2':'Title','TSSE':'SW/HW Settings','COMM':'Comments'}
FID2name = {'TALB':'album','TCOM':'composer','TDAT':'date','TYER':'year',
    'TENC':'encoder','TPE2':'band','TRCK':'tracknum',
    'TPUB':'publisher','TPE1':'artist','TCON':'content',
    'TIT2':'title','TSSE':'settings','COMM':'comments'}
# List of genres defined for ID3V1 where they would be stored by their index number
# (i.e. a byte with the value 2 would indicate "Country").  In V2, the actual strings are stored in TCON, although
# it's also legal to use a V1 number in parentheses, so either "Country" or "(2)".
Genres = ["Blues","Classic Rock","Country","Dance","Disco","Funk","Grunge","Hip-Hop","Jazz","Metal", \
         "New Age","Oldies","Other","Pop","R&B","Rap","Reggae","Rock","Techno","Industrial","Alternative", \
         "Ska","Death Metal","Pranks","Soundtrack","Euro-Techno","Ambient","Trip-Hop","Vocal","Jazz+Funk","Fusion", \
         "Trance","Classical","Instrumental","Acid","House","Game","Sound Clip","Gospel","Noise","AlternRock", \
         "Bass","Soul","Punk","Space","Meditative","Instrumental Pop","Instrumental Rock","Ethnic","Gothic","Darkwave", \
         "Techno-Industrial","Electronic","Pop-Folk","Eurodance","Dream","Southern Rock","Comedy","Cult","Gangsta","Top 40", \
         "Christian Rap","Pop/Funk","Jungle","Native American","Cabaret","New Wave","Psychedelic","Rave","Showtunes","Trailer", \
         "Lo-Fi","Tribal","Acid Punk","Acid Jazz","Polka","Retro","Musical","Rock & Roll","Hard Rock"]

assert len(Genres) == 80

# Generate dictionary translating genre name to its index in the list above
Genre2Num = {}
for i in range(len(Genres)):
    Genre2Num[Genres[i]] = i

# Function for translating genre string to number
def genre2num(genre_string):
    if Genre2Num.has_key(genre_string):
        return Genre2Num[genre_string]
    else:
        return 12 # "Other"
    
# Utility function for returning a list of all MP3 files under a given directory path
def findMP3s(path):
    "Return a list of filepaths of MP3 files under path"
    mp3list = []
    # Need to use a unicode string for path in order to get 
    #  unicode for the filepaths which you'll need for accented chars
    os.path.walk(unicode(path), addMP3s, mp3list)
    return mp3list
    
def addMP3s(mp3list, dirname, files):
    "Works with os.path.walk to add the full path of all MP3 file in dirpath to mp3list"
    for file in files:
        if file.lower()[-4:] == ".mp3":
            mp3list.append(os.path.join(dirname, file))


class ListDict:
    """Like normal dictionary, but automatically add key if not present
    and values are kept in a list and only added if unique"""
    def __init__(self):
        self.dict = {}
    
    def __getitem__(self, key):
        return self.dict[key]
                
    def add(self, key, value):
        if key in self.dict:
            if value not in self.dict[key]:
                self.dict[key].append(value)
        else:
            self.dict[key] = [value]
            
    def keys(self):
        return self.dict.keys()

class ID3V1tag:
    """Read/write ID3 version 1 tags in mp3 files."""
    # Format of tag (starts 128 bytes from end of file)
    # "TAG"       3 characters
    # Song Title  30 characters
    # Artist      30 characters
    # Album       30 characters
    # Year        4 characters
    # Comment     30 characters
    # Genre       1 byte (see codes at end of this file)
    
    loaded = False
    album = artist = title = mp3path = 'N/A'
    genreCode = 0
    track = 0
    
    def __init__(self, mp3path):
        self.mp3path = mp3path
        f = open(mp3path, "rb")
        f.seek(-128, SEEK_END)
        tagData = f.read(128)
        f.close()
        if DEBUG: print tagData
        if tagData[0:3] != 'TAG': return
        self.title = tagData[3:33].rstrip(' \t\0')
        self.artist = tagData[33:63].rstrip(' \t\0')
        self.album = tagData[63:93].rstrip(' \t\0')
        self.year = tagData[93:97].rstrip(' \t\0')
        self.comment = tagData[97:127]
        if self.comment[-2] == '\0' and self.comment[-1] != '\0':
            self.track = ord(self.comment[-1])
            self.comment = self.comment[:-2].rstrip(' \t\0')
        else:
            self.track = 0
            self.comment = self.comment.rstrip(' \t\0')
        self.genreCode = ord(tagData[-1])
        self.loaded = True
        
    def write(self):
        # Build the tag
        tag = 'TAG'
        tag += self.title.ljust(30,'\0')
        tag += self.artist.ljust(30,'\0')
        tag += self.album.ljust(30,'\0')
        tag += self.year.ljust(4)
        tag += self.comment.ljust(29, '\0')
        tag += chr(self.track)
        tag += chr(self.genreCode)
        if len(tag) != 128:
            print "Whoops, created an incorrectly sized ID3v1 tag"
            return
        if self.loaded:
            # Already had tag, overwrite it
            f = open(self.mp3path, 'wb')
            f.seek(-128, SEEK_END)
        else:
            # New tag, append it
            f = open(self.mp3path, 'ab')
        f.write(tag)
        f.close()
        
    def buildFromV2tag(self, v2tag):
        self.title = v2tag.title[:30]
        self.album = v2tag.album[:30]
        self.artist = v2tag.artist[:30]
        self.year = v2tag.year[:4]
        self.track = int(v2tag.tracknum.split('/')[0])
        self.comment = 'copied from ID3v2 tag'
        self.genreCode = genre2num(v2tag.content)
        
    def __str__(self):
        s = "Artist: %s, Album: %s, Song: %s, Year: %s, Trk: %d, Genre: %d, Comment: %s" % \
            (self.artist, self.album, self.title, self.year, self.track, self.genreCode, self.comment)
        return s
                    
        
class ID3V2tag:
    
    loaded = False
    size = 0
    bytesIn = 0
    album = artist = title = 'N/A'
    rawData = {}
    
    def __init__(self, mp3path):
        self.file = mp3path
        self.f = open(mp3path, "rb")
        header = self.f.read(10)     # read the 10 byte header
        if header[:3] != "ID3":
            self.f.close()
            raise Exception("ID3v2 tag not found in file %s" % mp3path)
        major = struct.unpack('B', header[3])[0]
        minor = struct.unpack('B', header[4])[0]
        self.version = '2.%01d.%01d' % (major, minor)
        self.flags = struct.unpack('B', header[5])[0]
        self.size = self.calcsize(header[6:10])
        if DEBUG:
            print "Tag version: %s, size: %d, flags: %x" % (self.version, self.size, self.flags)
        if self.flags & 0x40:
            # Extended header flag set
            extHdr = self.read(10)
        # Start reading frame headers
        while self.bytesIn < self.size:
            frameHdr = self.read(10)
            frameID = frameHdr[0:4]
            if frameID[0] == '\0':
                if DEBUG: print 'Found end of tag (NUL frameID)'
                break # no more frames
            frameSize = struct.unpack(">L", frameHdr[4:8])[0]
            if frameSize == 0: break    # no more frames
            frameData = self.read(frameSize)
            self.rawData[frameID] = frameData
            if DEBUG: print frameID, frameSize
            if frameID[0] == 'T':
                text = self.getTextInfo(frameData)
                self.rawData[frameID] = text
                if frameID in FID2name:
                    if DEBUG: print FID2name[frameID], text
                    # E.g. if FID is 'TALB', this creates a class member
                    #  called 'album' with the value of the framedata
                    self.__dict__[FID2name[frameID]] = text
            if DEBUG and self.bytesIn >= self.size:
                print "End of tag, size bytes have been read in"
        if not self.__dict__.has_key('year'):
            if self.__dict__.has_key('date'):
                self.year = self.date[:4]
            else:
                self.year = '0000'
                self.date = '0000-00-00'
        if not self.__dict__.has_key('tracknum'):
            self.tracknum = '1/1'
        self.loaded = True
        self.f.close()

    def write(self, outfile):
        "Write our rawData as a proper V2 tag to open file object outfile (this is called from rewrite)"
        tag = "ID3\03\00" # ID3 v2.3.0
        tag += struct.pack('B', self.flags)
        tagData = ""
        for frameID in self.rawData.keys():
            tagData += frameID
            frameData = self.rawData[frameID]
            if frameID[0] == 'T':       # if a Text frame
                if type(frameData) == type(u"unicode"):
                    frameData = "\01" + frameData.encode('utf-16')
                else:
                    frameData = "\00" + frameData   # add the byte to indicate the encoding
            tagData += struct.pack(">L", len(frameData))
            tagData += "\0\0" + frameData
        
        tagData += "\0" * 10   # Add empty frame as terminator
        tagData += "\0" * 256  # Add some padding
        size = len(tagData)
        tag += self.makesize(size)
        tag += tagData
        outfile.write(tag)
                    
    def rewrite(self, mp3out):
        "Replace the V2 tag in our file with our rawData and write to mp3out"
        outfile = open(mp3out, "wb")
        self.write(outfile)
        infile = open(self.file, "rb")
        header = infile.read(10)
        size = self.calcsize(header[6:10])
        infile.seek(size, SEEK_CUR)  # skip remainder of tag
        while True:
            data = infile.read(1024)
            outfile.write(data)
            if len(data) < 1024:
                break
        infile.close()
        outfile.close()
     
    def getTextInfo(self, data):
        "Extract the text from a text information frame and convert to UTF-8"
        text = ''
        # First byte indicates text encoding
        if data[0] == '\0':
            # ISO-8859-1 encoding
            lastChar = len(data)
            for i in range(1, len(data)):
                if DEBUG: print i, data[i]
                if data[i] == '\0':
                    lastChar = i
                    break
            text = data[1:lastChar]
            text = unicode(text, 'ISO-8859-1')
        elif data[0] == '\01':
            # Unicode UTF-16 encoding
            if DEBUG:
                print "UTF-16 encoded text"
            text = unicode(data[3:], 'utf-16').rstrip(u'\x00')
        return text
    
    def read(self, n):
        "Read n bytes from MP3 file"
        if self.bytesIn >= self.size:
            return ''   # don't read past end of tag
        s = self.f.read(n)
        if len(s) != n:
            print "Error reading %d bytes from MP3 file" % n
        self.bytesIn += n
        if DEBUG2: print "read %d bytes so far" % self.bytesIn
        return s
        
    def __str__(self):
        s = "Artist: %s, Album: %s, Song: %s" % \
            (self.artist, self.album, self.title)
        return s
    
    def calcsize(self, s):
        "Convert a 4 byte string representing an ID3 size into an integer"
        bytes = struct.unpack('BBBB', s)
        #print bytes
        size = bytes[3] + (bytes[2] << 7) + (bytes[1] << 14) + (bytes[0] << 21)
        return size

    def makesize(self, n):
        "Does reverse of calcsize, converting integer n to a 4 byte string"
        b0 = (n & 0x0fe00000) >> 21
        b1 = (n & 0x001fc000) >> 14
        b2 = (n & 0x00003f80) >> 7
        b3 = (n & 0x0000007f)
        return struct.pack('BBBB', b0, b1, b2, b3)
    
if __name__ == "__main__":
    albumDB = ListDict()
    dirname = sys.argv[1]
    files = glob.glob(dirname + os.path.sep + "*.mp3")
    nfiles = len(files)
    i = 0
    for file in files:
        tag = ID3V2tag(file)
        if tag.loaded:
            if DEBUG: print tag
            albumDB.add(tag.artist, tag.album)
        else:
            print "ID3 v2 tag not found in " + file
        v1tag = ID3V1tag(file)
        if not v1tag.loaded:
            print "No v1 tag found in ", file
        elif DEBUG2: 
            print "V1 tag: ", v1tag
        i += 1
        if (i % 100) == 0: print 'File %s of %s' % (i, nfiles)
    artists = albumDB.keys()
    artists.sort()
    for artist in artists:
        print artist, albumDB[artist]
        
##  Example of modifying V2 tags in a file:
##        tag = id3tags.ID3V2tag(fpath)
##        # Update tag info
##        tag.rawData["TCON"] = "Latin"
##        tag.rawData["TPE1"] = "Various artists"
##        # Write MP3 file containing updated ID3 tag
##        tag.rewrite(outpath)
   
