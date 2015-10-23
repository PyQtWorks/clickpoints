from __future__ import division, print_function
import os
import sys
import glob

try:
    from PyQt5 import QtCore
except ImportError:
    from PyQt4 import QtCore

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "mediahandler"))
from mediahandler import MediaHandler

from Tools import BroadCastEvent

class FolderBrowser:
    def __init__(self, window, media_handler, modules, config=None):
        # default settings and parameters
        self.window = window
        self.media_handler = media_handler
        self.config = config
        self.modules = modules
        self.index = 0
        self.folder_list = []
        for folder in config.folder_list:
            if folder.find("*") != -1:
                self.folder_list.extend(glob.glob(folder))
            else:
                self.folder_list.append(folder)

        self.media_handler_list = []
        folder_found = False
        srcpath_folder = self.config.srcpath
        if type("srcpath_folder") == type("") and srcpath_folder.lower().endswith((".jpg", ".png", ".tif", ".tiff")):
            srcpath_folder = os.path.dirname(srcpath_folder)+os.path.sep
        for index, folder in enumerate(self.folder_list):
            folder = os.path.abspath(folder)+os.path.sep
            print("FOlder", folder, srcpath_folder)
            if folder == srcpath_folder:
                self.media_handler_list.append(self.window.media_handler)
                self.index = index
                folder_found = True
                print("Folder found!")
            else:
                self.media_handler_list.append(MediaHandler(folder, filterparam=self.config.filterparam))
        if not folder_found:
            print("Folder not found!")
            self.media_handler_list.insert(0, self.window.media_handler)

    def LoadFolder(self):
        self.window.save()
        if self.config.relative_outputpath:
            self.config.outputpath = os.path.dirname(self.folder_list[self.index])
        self.config.srcpath = self.folder_list[self.index]
        index = self.window.media_handler.getCurrentPos()
        self.window.media_handler = self.media_handler_list[self.index]
        BroadCastEvent(self.modules, "FolderChangeEvent")
        self.window.JumpToFrame(index)
        self.window.setWindowTitle(self.folder_list[self.index])

    def keyPressEvent(self, event):

        # @key Page Down: Next folder
        if event.key() == QtCore.Qt.Key_PageDown:
            if self.index < len(self.folder_list)-1:
                self.index += 1
            self.LoadFolder()

        # @key Page Up: Previous folder
        if event.key() == QtCore.Qt.Key_PageUp:
            if self.index > 0:
                self.index -= 1
            self.LoadFolder()

    @staticmethod
    def file():
        return __file__

    @staticmethod
    def can_create_module(config):
        return len(config.folder_list) > 0
