import wx
from wx.lib.wordwrap import wordwrap
import wx.grid, webbrowser

import NewAlbumFinder, id3tags

import os

DEBUG = False

SHOW_ALL_ALBUMS = WRITE_LOGFILE = USE_TREE = False

class Options:
    "We'll fill this class's members to match the command line arguments"
    pass

class MyApp(wx.App):
    def __init__(self, redirect=False, filename=None):
        wx.App.__init__(self, redirect, filename)
        self.frame = MainWindow(None, title=NewAlbumFinder.appName, size=(600,700)) # was 600,500
         
class MainWindow(wx.Frame):
    
    firstScan = True
    
    def __init__(self, parent, title, size):
        wx.Frame.__init__(self, parent, title=title, size=size)

        self.panel = wx.Panel(self, wx.ID_ANY)
        
        # Add a status bar at bottom of window
        self.CreateStatusBar()
        
        # Create menu bar
        menuBar = wx.MenuBar()
        
        # Create file menu
        fileMenu = wx.Menu()
        exitItem = fileMenu.Append(wx.ID_EXIT, "E&xit", "Terminate the program")
        menuBar.Append(fileMenu, "&File")      # add it to the menu bar
        self.Bind(wx.EVT_MENU, self.Exit, exitItem)
        
        # Create help menu
        helpMenu = wx.Menu()
        aboutItem = helpMenu.Append(wx.ID_ABOUT, "&About", "About %s" % NewAlbumFinder.appName)
        menuBar.Append(helpMenu, "&Help")
        self.Bind(wx.EVT_MENU, self.ShowAbout, aboutItem)
        
        # Add menubar to window
        self.SetMenuBar(menuBar)
        
        # Create sizers to position elements within main panel
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer = mainSizer
        horSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        horSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        horSizer3 = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add a spacer to the sizer
        ##mainSizer.Add((5,5))
        
        # Add checkbox for using directory names to get artist/album list
        self.use_tree = wx.CheckBox(self.panel, label='Get artist/album list from directory names (faster)')
        self.Bind(wx.EVT_CHECKBOX, self.EvtUseTree, self.use_tree)
        mainSizer.Add(self.use_tree, flag=wx.ALL, border=10)
        
        # Add directory selector for top-level MP3 path
        dirSelectLbl = wx.StaticText(self.panel, label='Top-level MP3 directory:')
        horSizer1.Add(dirSelectLbl)
        self.mp3DirBox = wx.TextCtrl(self.panel, size=(300,-1), style=wx.TE_READONLY)
        horSizer1.Add(self.mp3DirBox)
        mp3BrowseBtn = wx.Button(self.panel, label="Browse")
        self.Bind(wx.EVT_BUTTON, self.EvtMp3Browse, mp3BrowseBtn)
        horSizer1.Add(mp3BrowseBtn)
        mainSizer.Add(horSizer1, flag=wx.ALL, border=10)
        
        # Add box to collect iTunes selection parameters
        iTparBox = wx.StaticBox(self.panel, label='iTunes Selection Preferences')
        iTparBoxSizer = wx.StaticBoxSizer(iTparBox, orient=wx.VERTICAL)
        self.iTparBoxSizer = iTparBoxSizer

        # Add Checkbox to request ALL albums (not just new ones)
        self.allAlbums = wx.CheckBox(self.panel, label="Find ALL albums (not just new ones)")
        self.Bind(wx.EVT_CHECKBOX, self.EvtAllAlbums, self.allAlbums)
        iTparBoxSizer.Add(self.allAlbums, flag=wx.ALL, border=10)
        
        # Add Checkbox to request a log file
        self.logFileCheck = wx.CheckBox(self.panel, label="Create log file")
        self.Bind(wx.EVT_CHECKBOX, self.EvtLogFile, self.logFileCheck)
        iTparBoxSizer.Add(self.logFileCheck, flag=wx.ALL, border=10)
        
        # Add spin control for setting min year
        yearLabel = wx.StaticText(self.panel, label='Earliest year to include:')
        self.yearSpin = wx.SpinCtrl(self.panel, min=1900, max=2100, value='1900')
        horSizer2.Add(yearLabel)
        horSizer2.Add(self.yearSpin)
        
        iTparBoxSizer.Add(horSizer2, flag=wx.ALL, border=10)
        
        # Add spin control for min tracks
        tracksLabel = wx.StaticText(self.panel, label='Disregard collections with fewer than this many tracks:')
        self.trackSpin = wx.SpinCtrl(self.panel, min=1, max=30, value='8')
        horSizer3.Add(tracksLabel)
        horSizer3.Add(self.trackSpin)
        
        iTparBoxSizer.Add(horSizer3, flag=wx.ALL, border=10)
        mainSizer.Add(iTparBoxSizer, flag=wx.ALL, border=10)
        
        # Add start iTunes search button
        searchButton = wx.Button(self.panel, wx.ID_ANY, "Search iTunes")
        self.searchButton = searchButton
        self.Bind(wx.EVT_BUTTON, self.EvtSearchiTunes, searchButton)
        mainSizer.Add(searchButton, flag=wx.ALL, border=10)
        self.searchButton.Enable(False)

        # Add grid for displaying users current artist/album collection
        self.AddGrid()
        
        self.panel.SetSizerAndFit(mainSizer)
        self.Show()
        
    def AddGrid(self):
        # Add grid to hold found albums
        albumGrid = wx.grid.Grid(self.panel , size=(-1, 200))
        albumGrid.AutoSize()
        albumGrid.CreateGrid(0,2)
        albumGrid.SetColLabelValue(0, 'Artist')
        albumGrid.SetColLabelValue(1, 'Album')
        self.mainSizer.Add(albumGrid, flag=wx.EXPAND)
        self.albumGrid = albumGrid
        self.mainSizer.Show(self.albumGrid, False) # don't show it until we've loaded it with data
 
    def EvtSearchiTunes(self, evt):
        if DEBUG: print 'Clicked search button'
        # Load options
        opts = Options()
        opts.tunesDir = self.mp3DirBox.GetValue()
        opts.ignorePrevious = SHOW_ALL_ALBUMS
        opts.albums_from_dir_structure = USE_TREE
        opts.MINTRACKS = int(self.trackSpin.GetValue())
        opts.outdir = "Desktop"
        opts.writeLogfile = DEBUG or WRITE_LOGFILE
        opts.minYear = int(self.yearSpin.GetValue())
        if DEBUG:
            print opts.__dict__
            return
        finder = NewAlbumFinder.AlbumFinder(opts, self.progressFun)
        self.progressDlg = wx.ProgressDialog(title="iTunes Search in Progress", 
            message="Searching iTunes by artist...", parent=self, 
            maximum=len(self.albumDB.keys()), style=wx.PD_CAN_ABORT|wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE)
        newCDcount = finder.runSearch(self.albumDB)
        self.progressDlg.Destroy()      # make sure progress dialog goes away
        if newCDcount == 0:
            msg = "No new albums were found."
            wx.MessageBox(msg, "iTunes Search Finished")
        elif os.path.exists(finder.outFilePath):
            msg = "Albums you don't have are in the file %s.  Click OK to open it in your web browser." % finder.outFilePath
            wx.MessageBox(msg, "iTunes Search Finished")
            webbrowser.open(finder.outFilePath)
   
    def progressFun(self, i, msg):
        (keep_going, x) = self.progressDlg.Update(i, msg)
        if not keep_going:
            self.progressDlg.Destroy()
        return keep_going      

        
    def ScanDirs(self):
        albumDB = NewAlbumFinder.generateAlbumDataFromPath(self.mp3DirBox.GetValue())
        self.albumDB = albumDB  # save the album data
        artists = albumDB.keys()
        artists.sort()
        self.artists = artists
        albumCount = 0
        for artist in artists:
            albumCount += len(albumDB[artist])
        msg = "Found %d artists and %d albums" % (len(artists), albumCount)
        wx.MessageBox(msg, 'Directory scan complete')
        return albumCount
        
    def ScanMp3s(self):
        mp3s = id3tags.findMP3s(self.mp3DirBox.GetValue())
        self.progressDlg = wx.ProgressDialog(title="Generating album list", message="MP3s scanned: ", 
            parent=self, maximum=len(mp3s), style=wx.PD_CAN_ABORT|wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE)
        albumDB = NewAlbumFinder.generateAlbumDataFromMP3s(mp3s, self.progressFun)
        self.progressDlg.Destroy()      # make sure progress dialog goes away
        self.albumDB = albumDB  # save the album data
        artists = albumDB.keys()
        artists.sort()
        self.artists = artists
        albumCount = 0
        for artist in artists:
            albumCount += len(albumDB[artist])
        msg = "Found %d artists and %d albums" % (len(artists), albumCount)
        wx.MessageBox(msg, 'MP3 scan complete')
        return albumCount
        
    def show_artist_album_grid(self):
        i = 0
        if self.firstScan:
            self.mainSizer.Show(self.albumGrid, True)
            self.mainSizer.Show(self.searchButton, True)
            self.mainSizer.Show(self.iTparBoxSizer, True)
            self.mainSizer.Layout()
            self.firstScan = False
        elif self.albumGrid.GetNumberRows():
            self.albumGrid.ClearGrid()
            self.albumGrid.DeleteRows(0, self.albumGrid.GetNumberRows())
        # Fill in grid with artist/album data
        for artist in self.artists:
            albums = self.albumDB[artist]
            albums.sort()
            for album in albums:
                self.albumGrid.AppendRows(1)
                self.albumGrid.SetCellValue(i, 0, artist)
                self.albumGrid.SetCellValue(i, 1, album)
                i = i + 1
        self.albumGrid.Fit()
        self.albumGrid.ForceRefresh()        
            
    def EvtMp3Browse(self, evt):
        if DEBUG: print 'Browsing for top-level MP3 directory'
        dlg = wx.DirDialog(self, "Select your top-level MP3 directory", "", style=wx.DD_DIR_MUST_EXIST)
        status = dlg.ShowModal()
        if status == wx.ID_OK:
            self.mp3DirBox.SetValue(dlg.GetPath())      # load selected path into textbox
        dlg.Destroy()
        if status != wx.ID_OK:
            return      # user cancelled w/out selecting directory
        if USE_TREE:
            albumCount = self.ScanDirs()
        else:
            albumCount = self.ScanMp3s()
        if albumCount > 0:
            self.searchButton.Enable(True)
            self.show_artist_album_grid()

    def EvtAllAlbums(self, evt):
        global SHOW_ALL_ALBUMS
        SHOW_ALL_ALBUMS = evt.Checked()
        if DEBUG: print "Show all albums is ", SHOW_ALL_ALBUMS
    
    def EvtLogFile(self, evt):
        global WRITE_LOGFILE
        WRITE_LOGFILE = evt.Checked()
        if DEBUG: print "Write Logfile is ", WRITE_LOGFILE

    def EvtUseTree(self, evt):
        global USE_TREE
        USE_TREE = evt.Checked()
                
    def Exit(self, evt):
        self.Close(True)

    def ShowAbout(self, evt):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = NewAlbumFinder.appName
        info.Version = NewAlbumFinder.appVersion
        info.Copyright = "(C) 2016 BHBsoftware"
        info.Description = wordwrap(
             "NewAlbumFinder uses the iTunes library to determine if there are "
             "new albums available by your favorite artists.  First, you scan "
             "your computer for MP3 files to generate the list of artists you "
             "like along with the albums you already have.  Then you search iTunes "
             "for all available albums by those artists.  NewAlbumFinder will "
             "generate an HTML file viewable in your web browser, that lists "
             "all the albums by each of your artists that you don't have.  "
             "You may click on the album images to go to the iTunes page for that "
             "album to get more information.  NewAlbumFinder saves the list of "
             "albums found on iTunes and will only show you new albums the next "
             "time you run it (unless you check ""show me ALL albums"").",
             350, wx.ClientDC(self.panel))
        info.WebSite = ("http://bhbsoftware.com/newalbumfinder", "NewAlbumFinder home page")
        info.Developers = [ "Brien Barton" ]
         
        licenseText = "Copyright 2016 BHBsoftware, all rights reserved.  Released under the GNU GPLv3 license."
        
        # change the wx.ClientDC to use self.panel instead of self
        info.License = wordwrap(licenseText, 500, wx.ClientDC(self.panel))

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)


def main():
    app = MyApp()
    app.MainLoop()
