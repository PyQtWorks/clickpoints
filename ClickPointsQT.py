
from __future__ import division
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "mediahandler"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "qextendedgraphicsview"))
try:
    from PyQt5 import QtGui, QtCore
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4 import QtGui, QtCore
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from QExtendedGraphicsView import QExtendedGraphicsView

import numpy as np
import os
from os.path import join

from PIL import Image,  ImageDraw
import ImageQt
from qimage2ndarray import array2qimage, rgb_view

from mediahandler import MediaHandler
import uuid

### parameter and path setup
# default settings
use_filedia = True
auto_mask_update = True
tracking = False
srcpath = None
filename = None
outputpath = None
logname_tag = '_pos.txt'
maskname_tag = '_mask.png'

# marker types
types = [["juveniles", [255, 0., 0], 0],
         ["adults", [0, .8 * 255, 0], 0],
         ["border", [0.8 * 255, 0.8 * 255, 0], 1],
         ["bgroup", [0.5 * 255, 0.5 * 255, 0], 0],
         ["horizon", [0.0, 0, 0.8 * 255], 0],
         ["iceberg", [0.0, 0.8 * 255, 0.8 * 255], 0]]
# painter types
draw_types = [[0, (0, 0, 0)],
              [255, [255, 255, 255]],
              [124, [124, 124, 255]]]

# possible addons
addons = []

# overwrite defaults with personal cfg if available
config_filename = 'cp_cfg.txt'
if len(sys.argv) >= 2:
    config_filename = sys.argv[1]
if os.path.exists(config_filename):
    with open(config_filename) as f:
        code = compile(f.read(), config_filename, 'exec')
        exec (code)

# parameter pre processing
if srcpath == None:
    srcpath = os.getcwd()
if outputpath != None and not os.path.exists(outputpath):
    os.makedirs(outputpath)  # recursive path creation

max_image_size = 2**12

type_counts = [0] * len(types)
active_type = 0

active_draw_type = 1

w = 1.
b = 7
r2 = 10
path1 = QPainterPath()
path1.addRect(-r2, -w, b, w * 2)
path1.addRect(r2, -w, -b, w * 2)
path1.addRect(-w, -r2, w * 2, b)
path1.addRect(-w, r2, w * 2, -b)
path1.addEllipse(-r2, -r2, r2 * 2, r2 * 2)
path1.addEllipse(-r2, -r2, r2 * 2, r2 * 2)
w = 2
b = 3
o = 3
path2 = QPainterPath()
path2.addRect(-b - o, -w * 0.5, b, w)
path2.addRect(+o, -w * 0.5, b, w)
path2.addRect(-w * 0.5, -b - o, w, b)
path2.addRect(-w * 0.5, +o, w, b)
r3 = 5
path3 = QPainterPath()
path3.addEllipse(-0.5*r3, -0.5*r3, r3, r3)  # addRect(-0.5,-0.5, 1, 1)
point_display_types = [path1, path2, path3]
point_display_type = 0

def disk(radius):
    disk = np.zeros((radius*2+1,radius*2+1))
    for x in range(radius*2+1):
        for y in range(radius*2+1):
            if np.sqrt( (radius-x)**2 + (radius-y)**2 ) < radius:
                disk[y,x] = True
    return disk

class BigImageDisplay():
    def __init__(self, origin, window):
        self.number_of_imagesX = 0
        self.number_of_imagesY = 0
        self.pixMapItems = []
        self.QImages = []
        self.QImageViews = []
        self.ImageSlices = []
        self.origin = origin
        self.window = window

        self.preview_pixMapItem = QGraphicsPixmapItem(self.origin)
        self.preview_pixMapItem.setZValue(10)
        self.preview_slice = None
        self.preview_qimage = None
        self.preview_qimageView = None

        self.gamma = 1
        self.min = 0
        self.max = 255

    def UpdatePixmapCount(self):
        # Create new subimages if needed
        for i in range(len(self.pixMapItems), self.number_of_imagesX * self.number_of_imagesY):
            if i == 0:
                new_pixmap = QGraphicsPixmapItem(self.origin)
            else:
                new_pixmap = QGraphicsPixmapItem(self.pixMapItems[0])
            self.pixMapItems.append(new_pixmap)
            self.ImageSlices.append(None)
            self.QImages.append(None)
            self.QImageViews.append(None)

            new_pixmap.setAcceptHoverEvents(True)

            new_pixmap.installSceneEventFilter(self.window.scene_event_filter)

        # Hide images which are not needed
        for i in range(self.number_of_imagesX * self.number_of_imagesY, len(self.pixMapItems)):
            im = np.zeros((1, 1, 1))
            self.pixMapItems[i].setPixmap(QPixmap(array2qimage(im)))
            self.pixMapItems[i].setOffset(0, 0)

    def SetImage(self, image):
        if len(image.shape) == 2:
            image = image.reshape((image.shape[0],image.shape[1],1))
        self.number_of_imagesX = int(np.ceil(image.shape[1] / max_image_size))
        self.number_of_imagesY = int(np.ceil(image.shape[0] / max_image_size))
        self.UpdatePixmapCount()
        self.image = image

        for y in range(self.number_of_imagesY):
            for x in range(self.number_of_imagesX):
                i = y * self.number_of_imagesX + x
                startX = x * max_image_size
                startY = y * max_image_size
                endX = min([(x + 1) * max_image_size, image.shape[1]])
                endY = min([(y + 1) * max_image_size, image.shape[0]])
                self.ImageSlices[i] = image[startY:endY, startX:endX, :]
                self.QImages[i] = array2qimage(image[startY:endY, startX:endX, :])
                self.QImageViews[i] = rgb_view(self.QImages[i])
                self.pixMapItems[i].setPixmap(QPixmap(self.QImages[i]))
                self.pixMapItems[i].setOffset(startX, startY)
        self.preview_pixMapItem.setPixmap(QPixmap())
        self.preview_slice = None

    def PreviewRect(self):
        startX, startY, endX, endY = self.window.view.GetExtend()
        if startX < 0: startX = 0
        if startY < 0: startY = 0
        if endX > self.image.shape[1]: endX = self.image.shape[1]
        if endY > self.image.shape[0]: endY = self.image.shape[0]
        if endX > startX+max_image_size: endX = startX+max_image_size
        if endY > startY+max_image_size: endY = startY+max_image_size
        self.preview_slice = self.image[startY:endY,startX:endX,:]
        self.preview_qimage = array2qimage(self.image[startY:endY,startX:endX, :])
        self.preview_qimageView = rgb_view(self.preview_qimage)
        self.preview_pixMapItem.setPixmap(QPixmap(self.preview_qimage))
        self.preview_pixMapItem.setOffset(startX, startY)
        self.ChangeGamma(self.gamma)
        self.hist = np.histogram(self.preview_slice.flatten(), bins=range(0,256), normed=True)

    def ChangeGamma(self, value):
        import time
        t = time.time()
        self.gamma = value
        print(value)
        conversion = np.power(np.arange(0,256)/256.,value)*256
        for i in range(self.number_of_imagesX * self.number_of_imagesY):
            self.QImageViews[i][:, :, :] = conversion[self.ImageSlices[i]]
            self.pixMapItems[i].setPixmap(QPixmap(self.QImages[i]))
        self.window.view.scene.update()
        print time.time()-t

    def Change(self, gamma=None, min=None, max=None):
        if self.preview_slice is None:
            self.PreviewRect()
        import time
        t = time.time()
        if gamma is not None:
            if gamma > 1:
                gamma = 1./(1-(gamma-1)+0.00001)
            self.gamma = gamma
        if min is not None:
            self.min = int(min)
        if max is not None:
            self.max = int(max)
        color_range = self.max-self.min
        conversion = np.arange(0,256)
        conversion[:self.min] = 0
        conversion[self.min:self.max] = np.power(np.arange(0,color_range)/color_range,self.gamma)*256
        conversion[self.max:] = 255
        for i in range(self.number_of_imagesX * self.number_of_imagesY):
            self.preview_qimageView[:, :, :] = conversion[self.preview_slice]
            self.preview_pixMapItem.setPixmap(QPixmap(self.preview_qimage))
        self.window.view.scene.update()
        self.conversion = conversion
        print "Time", time.time()-t

class BigPaintableImageDisplay():
    def __init__(self, origin):
        self.number_of_imagesX = 0
        self.number_of_imagesY = 0
        self.pixMapItems = []
        self.origin = origin
        self.full_image = None
        self.images = []
        self.DrawImages = []
        self.qimages = []

        self.opacity = 0
        self.colormap = [QColor(i, i, i).rgba() for i in range(256)]
        for drawtype in draw_types:
            self.colormap[drawtype[0]] = QColor(*drawtype[1]).rgba()

    def UpdatePixmapCount(self):
        # Create new subimages if needed
        for i in range(len(self.pixMapItems), self.number_of_imagesX * self.number_of_imagesY):
            self.images.append(None)
            self.DrawImages.append(None)
            self.qimages.append(None)
            if i == 0:
                new_pixmap = QGraphicsPixmapItem(self.origin)
            else:
                new_pixmap = QGraphicsPixmapItem(self.origin)
            self.pixMapItems.append(new_pixmap)
            new_pixmap.setOpacity(self.opacity)
        # Hide images which are not needed
        for i in range(self.number_of_imagesX * self.number_of_imagesY, len(self.pixMapItems)):
            im = np.zeros((1, 1, 1))
            self.pixMapItems[i].setPixmap(QPixmap(array2qimage(im)))
            self.pixMapItems[i].setOffset(0, 0)

    def SetImage(self, image):
        self.number_of_imagesX = int(np.ceil(image.size[0] / max_image_size))
        self.number_of_imagesY = int(np.ceil(image.size[1] / max_image_size))
        self.UpdatePixmapCount()
        self.full_image = image

        for y in range(self.number_of_imagesY):
            for x in range(self.number_of_imagesX):
                i = y * self.number_of_imagesX + x
                startX = x * max_image_size
                startY = y * max_image_size
                endX = min([(x + 1) * max_image_size, image.size[0]])
                endY = min([(y + 1) * max_image_size, image.size[1]])

                self.images[i] = image.crop((startX, startY, endX, endY))
                self.DrawImages[i] = ImageDraw.Draw(self.images[i])
                self.pixMapItems[i].setOffset(startX, startY)
        self.UpdateImage()

    def UpdateImage(self):
        for i in range(self.number_of_imagesY * self.number_of_imagesX):
            self.qimages[i] = ImageQt.ImageQt(self.images[i])
            qimage = QImage(self.qimages[i])
            qimage.setColorTable(self.colormap)
            pixmap = QPixmap(qimage)
            self.pixMapItems[i].setPixmap(pixmap)

    def DrawLine(self, x1, x2, y1, y2, size):
        for y in range(self.number_of_imagesY):
            for x in range(self.number_of_imagesX):
                i = y * self.number_of_imagesX + x
                if x * max_image_size < x1 < (x + 1) * max_image_size or x * max_image_size < x2 < (
                    x + 1) * max_image_size:
                    if y * max_image_size < y1 < (y + 1) * max_image_size or y * max_image_size < y2 < (
                        y + 1) * max_image_size:
                        draw = self.DrawImages[i]
                        draw.line((x1 - x * max_image_size, y1 - y * max_image_size, x2 - x * max_image_size,
                                   y2 - y * max_image_size), fill=draw_types[active_draw_type][0], width=size + 1)
                        draw.ellipse((x1 - x * max_image_size - size // 2, y1 - y * max_image_size - size // 2,
                                      x1 - x * max_image_size + size // 2, y1 - y * max_image_size + size // 2),
                                     fill=draw_types[active_draw_type][0])
        draw = ImageDraw.Draw(self.full_image)
        draw.line((x1, y1, x2, y2), fill=draw_types[active_draw_type][0], width=size + 1)
        draw.ellipse((x1 - size // 2, y1 - size // 2, x1 + size // 2, y1 + size // 2), fill=draw_types[active_draw_type][0])

    def GetColor(self, x1, y1):
        if x1 > 0 and y1 > 0 and x1 < self.full_image.size[0] and y1 < self.full_image.size[1]:
            return self.full_image.getpixel((x1, y1))
        return None

    def setOpacity(self, opacity):
        self.opacity = opacity
        for pixmap in self.pixMapItems:
            pixmap.setOpacity(opacity)

    def save(self, filename):
        self.full_image.save(filename)

class MyMarkerItem(QGraphicsPathItem):
    def __init__(self, x, y, parent, window, point_type):
        global type_counts, types, point_display_type

        QGraphicsPathItem.__init__(self, parent)
        self.UpdatePath()

        self.type = point_type
        self.window = window
        if len(self.window.counter):
            self.window.counter[self.type].AddCount(1)

        self.setBrush(QBrush(QColor(*types[self.type][1])))
        self.setPen(QPen(QColor(0, 0, 0, 0)))

        self.setPos(x, y)
        self.setZValue(20)
        self.imgItem = parent
        self.dragged = False

        self.UseCrosshair = True

        self.partner = None
        self.rectObj = None
        if types[self.type][2] == 1 or types[self.type][2] == 2:
            for point in self.window.points:
                if point.type == self.type:
                    if point.partner is None:
                        self.partner = point
                        point.partner = self
                        self.UseCrosshair = False
                        self.partner.UseCrosshair = False

        if self.partner:
            if types[self.type][2] == 1:
                self.rectObj = QGraphicsRectItem(self.imgItem)
                self.rectObj.setPen(QPen(QColor(*types[self.type][1]), 2))
                self.UpdateRect()
            if types[self.type][2] == 2:
                self.rectObj = QGraphicsLineItem(self.imgItem)
                self.rectObj.setPen(QPen(QColor(*types[self.type][1]), 2))
                self.UpdateRect()

        self.window.PointsUnsaved = True
        self.setAcceptHoverEvents(True)
        if tracking == True:
            self.track = {self.window.MediaHandler.getCurrentPos(): [x,y, point_type]}
            self.pathItem = QGraphicsPathItem(self.imgItem)
            self.path = QPainterPath()
            self.path.moveTo(x, y)
        self.id = uuid.uuid4().hex
        self.active = True

    def setInvalidNewPoint(self):
        self.addPoint(self.pos().x(), self.pos().y(), -1)

    def UpdateLine(self):
        self.track[self.window.MediaHandler.getCurrentPos()][:2] = [self.pos().x(),self.pos().y()]
        self.path = QPainterPath()
        frames = sorted(self.track.keys())
        last_active = False
        circle_width = self.scale_value*10
        for frame in frames:
            x,y,type = self.track[frame]
            if type != -1:
                if last_active:
                    self.path.lineTo(x,y)
                else:
                    self.path.moveTo(x,y)
                if frame != self.window.MediaHandler.getCurrentPos():
                    self.path.addEllipse(x-.5*circle_width, y-.5*circle_width, circle_width, circle_width)
                self.path.moveTo(x,y)
            last_active = type != -1
        self.pathItem.setPath(self.path)

    def SetTrackActive(self, active):
        if active is False:
            self.active = False
            self.setOpacity(0.5)
            self.pathItem.setOpacity(0.25)
            self.track[self.window.MediaHandler.getCurrentPos()][2] = -1
        else:
            self.active = True
            self.setOpacity(1)
            self.pathItem.setOpacity(0.5)
            self.track[self.window.MediaHandler.getCurrentPos()][2] = self.type

    def addPoint(self, x, y, type):
        if type == -1:
            x, y = self.pos().x(), self.pos().y()
        self.setPos(x, y)
        self.track[self.window.MediaHandler.getCurrentPos()] = [x,y,type]
        if type == -1:
            self.SetTrackActive(False)
        else:
            self.SetTrackActive(True)
            self.setOpacity(1)
        self.UpdateLine()

    def OnRemove(self):
        self.window.counter[self.type].AddCount(-1)
        if self.partner and self.partner.rectObj:
            self.window.local_scene.removeItem(self.partner.rectObj)
            self.partner.rectObj = None
            self.partner.partner = None
        if self.rectObj:
            self.partner.partner = None
            self.window.local_scene.removeItem(self.rectObj)

    def UpdateRect(self):
        x, y = self.pos().x(), self.pos().y()
        x2, y2 = self.partner.pos().x(), self.partner.pos().y()
        if types[self.type][2] == 1:
            self.rectObj.setRect(x, y, x2 - x, y2 - y)
        if types[self.type][2] == 2:
            self.rectObj.setLine(x, y, x2, y2)

    def mousePressEvent(self, event):
        if event.button() == 2:
            if tracking == True:
                self.SetTrackActive(self.active==False)
                self.window.PointsUnsaved = True#
                self.UpdateLine()
                valid_frame_found = False
                for frame in self.track:
                    if self.track[frame][2] != -1:
                        valid_frame_found = True
                if not valid_frame_found:
                    self.window.RemovePoint(self)
            else:
                self.window.RemovePoint(self)
        if event.button() == 1:
            self.dragged = True
            self.setCursor(QCursor(QtCore.Qt.BlankCursor))
            if self.UseCrosshair:
                self.window.Crosshair.MoveCrosshair(self.pos().x(), self.pos().y())
                self.window.Crosshair.Show(self.type)
            pass

    def mouseMoveEvent(self, event):
        if not self.dragged:
            return
        if tracking:
            self.SetTrackActive(True)
        pos = self.window.origin.mapFromItem(self, event.pos())
        self.setPos(pos.x(), pos.y())
        if tracking:
            self.UpdateLine()
        self.window.Crosshair.MoveCrosshair(pos.x(), pos.y())
        if self.partner:
            if self.rectObj:
                self.UpdateRect()
            else:
                self.partner.UpdateRect()
                self.partner.setPos(self.partner.pos())

    def mouseReleaseEvent(self, event):
        if not self.dragged:
            return
        if event.button() == 1:
            self.window.PointsUnsaved = True
            self.dragged = False
            self.setCursor(QCursor(QtCore.Qt.OpenHandCursor))
            self.window.Crosshair.Hide()
            pass

    def SetActive(self, active):
        if active:
            self.setAcceptedMouseButtons(Qt.MouseButtons(3))
            self.setCursor(QCursor(QtCore.Qt.OpenHandCursor))
        else:
            self.setAcceptedMouseButtons(Qt.MouseButtons(0))
            self.unsetCursor()

    def UpdatePath(self):
        self.setPath(point_display_types[point_display_type])
        self.SetActive(point_display_type != len(point_display_types) - 1)

    def setScale(self, scale):
        self.scale_value = scale
        if self.rectObj:
            self.rectObj.setPen(QPen(QColor(*types[self.type][1]), 2*scale))
        if tracking is True:
            self.pathItem.setPen(QPen(QColor(*types[self.type][1]), 2*scale))
            self.UpdateLine()
        super(QGraphicsPathItem, self).setScale(scale)

class Crosshair():
    def __init__(self, parent, scene, window):
        self.parent = parent
        self.scene = scene
        self.window = window
        self.origin = window.origin

        self.a = self.window.im[-102:-1, 0:101].copy()
        self.b = disk(50) * 255
        self.c = np.concatenate((self.a, self.b[:, :, None]), axis=2)
        self.CrosshairX = array2qimage(self.c)
        self.d = rgb_view(self.CrosshairX)

        self.Crosshair = QGraphicsPixmapItem(QPixmap(self.CrosshairX), self.origin)
        self.d[:, :, 0] = 255
        self.Crosshair.setOffset(-50, -50)
        self.Crosshair.setZValue(30)
        self.Crosshair.setScale(3)

        self.pathCrosshair = QPainterPath()
        self.pathCrosshair.addEllipse(-50, -50, 100, 100)

        w = 0.333 * 0.5
        b = 40
        r2 = 50
        self.pathCrosshair2 = QPainterPath()
        self.pathCrosshair2.addRect(-r2, -w, b, w * 2)
        self.pathCrosshair2.addRect(r2, -w, -b, w * 2)
        self.pathCrosshair2.addRect(-w, -r2, w * 2, b)
        self.pathCrosshair2.addRect(-w, r2, w * 2, -b)

        self.CrosshairPathItem = QGraphicsPathItem(self.pathCrosshair, self.Crosshair)
        self.CrosshairPathItem.setBrush(QBrush(QColor(0, 0, 0, 0)))
        self.CrosshairPathItem.setPen(QPen(QColor(*types[0][1]), 5))

        self.CrosshairPathItem2 = QGraphicsPathItem(self.pathCrosshair2, self.Crosshair)
        self.CrosshairPathItem2.setBrush(QBrush(QColor(0, 0, 0, 0)))
        self.CrosshairPathItem2.setPen(QPen(QColor(*types[0][1]), 5))

        self.Crosshair.setScale(0)

    def MoveCrosshair(self, x, y):
        self.d[:, :, :] = 0
        self.Crosshair.setPos(x, y)
        x, y = int(x), int(y)
        h, w = self.window.im.shape[:2]
        y1 = y - 50
        y1b = 0
        x1 = x - 50
        x1b = 0
        y2 = y + 50 + 1
        y2b = 101
        x2 = x + 50 + 1
        x2b = 101
        if x2 > 0 and y2 > 0 and x1 < w and y1 < h:
            if y1 < 0:
                y1b = -y1
                y1 = 0
            if x1 < 0:
                x1b = -x1
                x1 = 0
            if y2 >= h:
                y2 = h - 1
                y2b = y2 - y1 + y1b
            if x2 >= w:
                x2 = w - 1
                x2b = x2 - x1 + x1b
            self.d[y1b:y2b, x1b:x2b, :] = self.window.im[y1:y2, x1:x2, :]
        self.Crosshair.setPixmap(QPixmap(self.CrosshairX))

    def Hide(self):
        self.Crosshair.setScale(0)

    def Show(self, type):
        self.Crosshair.setScale(2 / self.window.view.getOriginScale())
        self.CrosshairPathItem2.setPen(QPen(QColor(*types[type][1]), 1))
        self.CrosshairPathItem.setPen(QPen(QColor(*types[type][1]), 3))


class MyCounter():
    def __init__(self, parent, window, point_type):
        self.parent = window.view.hud
        self.window = window
        self.type = point_type
        self.count = 0

        self.font = QFont()
        self.font.setPointSize(14)

        self.text = QGraphicsSimpleTextItem(self.parent)
        self.text.setText(types[self.type][0] + " %d" % 0)
        self.text.setFont(self.font)
        self.text.setBrush(QBrush(QColor(*types[self.type][1])))
        self.text.setPos(10, 10 + 25 * self.type)
        self.text.setZValue(10)

        self.rect = QGraphicsRectItem(self.parent)
        self.rect.setBrush(QBrush(QColor(0, 0, 0, 128)))
        self.rect.setPos(10, 10 + 25 * self.type)
        self.rect.setZValue(9)

        count = 0
        for point in self.window.points:
            if point.type == self.type:
                count += 1
        self.AddCount(count)

    def AddCount(self, new_count):
        self.count += new_count
        self.text.setText(types[self.type][0] + " %d" % self.count)
        rect = self.text.boundingRect()
        rect.setX(-5)
        rect.setWidth(rect.width() + 5)
        self.rect.setRect(rect)

    def SetToActiveColor(self):
        self.rect.setBrush(QBrush(QColor(255, 255, 255, 128)))

    def SetToInactiveColor(self):
        self.rect.setBrush(QBrush(QColor(0, 0, 0, 128)))

class HelpText(QGraphicsRectItem):
    def __init__(self, window):
        QGraphicsPathItem.__init__(self, window.view.hud)

        self.setCursor(QCursor(QtCore.Qt.ArrowCursor))

        self.help_text = QGraphicsSimpleTextItem(self)
        self.help_text.setFont(QFont("", 11))
        self.help_text.setPos(0, 10)

        self.setBrush(QBrush(QColor(255, 255, 255, 255-32)))
        self.setPos(100, 100)
        self.setZValue(19)

        self.UpdateText()
        BoxGrabber(self)
        self.setVisible(False)

    def ShowHelpText(self):
        if self.isVisible():
            self.setVisible(False)
        else:
            self.setVisible(True)

    def UpdateText(self):
        import re
        text = ""
        with open(__file__) as fp:
            for line in fp.readlines():
                m = re.match(r'\w*#@key (.*)$', line.strip())
                if m:
                    text += m.groups()[0]+"\n"
        self.help_text.setText(text[:-1])
        rect = self.help_text.boundingRect()
        rect.setX(-5)
        rect.setWidth(rect.width() + 5)
        rect.setHeight(rect.height() + 15)
        self.setRect(rect)

    def mousePressEvent(self, event):
        pass
    def mouseMoveEvent(self, event):
        pass
    def mouseReleaseEvent(self, event):
        pass

class MySlider(QGraphicsRectItem):
    def __init__(self, parent, name="", maxValue=100, minValue=0):
        QGraphicsRectItem.__init__(self, parent)

        self.parent = parent
        self.name = name
        self.maxValue = maxValue
        self.minValue = minValue
        self.format = "%.2f"

        self.setCursor(QCursor(QtCore.Qt.OpenHandCursor))
        self.setPen(QPen(QColor(255, 255, 255, 0)))

        self.text = QGraphicsSimpleTextItem(self)
        self.text.setFont(QFont("",11))
        self.text.setPos(0, -23)

        self.sliderMiddel = QGraphicsRectItem(self)
        self.sliderMiddel.setRect(QRectF(0,0,100,1))

        path = QPainterPath()
        path.addEllipse(-5, -5, 10, 10)
        self.slideMarker = QGraphicsPathItem(path,self)
        self.slideMarker.setBrush(QBrush(QColor(255, 0, 0, 255)))

        self.setRect(QRectF(-5,-5,110,10))
        self.dragged = False

        self.setValue( (self.maxValue+self.minValue)*0.5 )

    def mousePressEvent(self, event):
        if event.button() == 1:
            self.dragged = True

    def mouseMoveEvent(self, event):
        if self.dragged:
            pos = event.pos()
            x = pos.x()
            if x < 0: x = 0
            if x > 100: x = 100
            self.setValue(x/100.*self.maxValue+self.minValue)

    def setValue(self, value):
        self.value = value
        self.text.setText(self.name+": "+self.format%value)
        self.slideMarker.setPos((value-self.minValue)*100/self.maxValue, 0)
        self.valueChanged(value)

    def valueChanged(self, value):
        pass

    def mouseReleaseEvent(self, event):
        self.dragged = False

class BoxGrabber(QGraphicsRectItem):
    def __init__(self, parent):
        QGraphicsRectItem.__init__(self, parent)

        self.parent = parent
        self.setCursor(QCursor(QtCore.Qt.OpenHandCursor))
        width = parent.rect().width()
        self.setRect(QRectF(0,0, width,10))
        self.setPos(parent.rect().x(), 0)

        self.setBrush(QBrush(QColor(255, 255, 255, 255-32)))

        path = QPainterPath()
        path.addRect(QRectF(5,3, width-10,1))
        path.addRect(QRectF(5,6, width-10,1))
        QGraphicsPathItem(path, self)

        self.dragged = False

    def mousePressEvent(self, event):
        if event.button() == 1:
            self.dragged = True
            self.drag_offset = self.parent.mapToParent(self.mapToParent(event.pos()))-self.parent.pos()

    def mouseMoveEvent(self, event):
        if self.dragged:
            pos = self.parent.mapToParent(self.mapToParent(event.pos()))-self.drag_offset
            self.parent.setPos(pos.x(), pos.y())

    def mouseReleaseEvent(self, event):
        self.dragged = False

class SliderBox(QGraphicsRectItem):
    def __init__(self, parent, image):
        QGraphicsRectItem.__init__(self, parent)

        self.image = image
        self.setCursor(QCursor(QtCore.Qt.ArrowCursor))

        self.setBrush(QBrush(QColor(255, 255, 255, 255-32)))
        self.setPos(100, 100)
        self.setZValue(19)

        self.hist = QGraphicsPathItem(self)
        self.hist.setPen(QPen(QColor(0,0,0, 0)))
        self.hist.setBrush(QBrush(QColor(0,0,0, 128)))
        self.hist.setPos(0, 110)

        self.conv = QGraphicsPathItem(self)
        self.conv.setPen(QPen(QColor(255,0,0, 128), 2))
        self.conv.setBrush(QBrush(QColor(0,0,0, 0)))
        self.conv.setPos(0, 110)

        self.sliders = []
        functions = [self.updateGamma, self.updateBrightnes, self.updateContrast]
        minMax = [[0,2],[0,255],[0,255]]
        start = [1,255,0]
        formats = ["%.2f", "%d", "%d"]
        for i,name in enumerate(["Gamma","Max","Min"]):
            slider = MySlider(self, name, maxValue=minMax[i][1], minValue=minMax[i][0])
            slider.format = formats[i]
            slider.setValue(start[i])
            slider.setPos(5, 40+i*30)
            slider.valueChanged = functions[i]
            self.sliders.append(slider)

        self.setRect(QRectF(0, 0, 110, 110))
        BoxGrabber(self)
        self.dragged = False

    def updateHist(self, hist):
        histpath = QPainterPath()
        w = 100/256.
        for i,h in enumerate(hist[0]):
            histpath.addRect(i*w+5, 0, w, -h*100/max(hist[0]))
        self.hist.setPath(histpath)

    def updateConv(self):
        convpath = QPainterPath()
        w = 100/256.
        for i,h in enumerate(self.image.conversion):
            convpath.lineTo(i*w+5,-h*98/255.)
        self.conv.setPath(convpath)

    def updateGamma(self, value):
        self.image.Change(gamma=value)
        self.updateConv()

    def updateBrightnes(self, value):
        self.image.Change(max=value)
        self.updateConv()

    def updateContrast(self, value):
        self.image.Change(min=value)
        self.updateConv()

    def onImageChange(self):
        self.hist.setPath(QPainterPath())
        self.conv.setPath(QPainterPath())

    def mousePressEvent(self, event):
        pass
    def mousePressEvent(self, event):
        pass
    def mousePressEvent(self, event):
        pass

class GraphicsItemEventFilter(QGraphicsItem):
    def __init__(self, parent, window):
        super(GraphicsItemEventFilter, self).__init__(parent)
        self.window = window
        self.last_x = 0
        self.last_y = 0
    def paint(self, *args):
        pass
    def boundingRect(self):
        return QRectF(0,0,0,0)
    def sceneEventFilter(self, object, event):
        if event.type() == 156:#QtCore.QEvent.MouseButtonPress:
            if event.button() == 1:
                if not self.window.DrawMode:
                    self.window.points.append(MyMarkerItem(event.pos().x(), event.pos().y(), self.window.MarkerParent, self.window, active_type))
                    self.window.points[-1].setScale(1/self.window.view.getOriginScale())
                    return True
                else:
                    self.last_x = event.pos().x()
                    self.last_y = event.pos().y()
                    return True
        if event.type() == 155:# Mouse Move
            if self.window.DrawMode:
                pos_x = event.pos().x()
                pos_y = event.pos().y()
                self.window.drawPath.moveTo(self.last_x, self.last_y)
                self.window.drawPath.lineTo(pos_x, pos_y)
                self.window.MaskChanged = True
                self.window.MaskUnsaved = True

                self.window.MaskDisplay.DrawLine(pos_x, self.last_x, pos_y, self.last_y, self.window.DrawCursorSize)
                self.last_x = pos_x
                self.last_y = pos_y
                self.window.drawPathItem.setPath(self.window.drawPath)
                self.window.DrawCursor.setPos(event.pos())
                if auto_mask_update:
                    self.window.RedrawMask()
                return True
        if event.type() == 161:# Mouse Hover
            self.window.DrawCursor.setPos(event.pos())
            color = self.window.MaskDisplay.GetColor(event.pos().x(), event.pos().y())
            if color is not None:
                self.window.color_under_cursor = color
        return False

class DrawImage(QMainWindow):

    def zoomEvent(self, scale, pos):
        for point in self.points:
            point.setScale(1/self.view.getOriginScale())

    def __init__(self, parent=None):
        super(QMainWindow, self).__init__(parent)
        self.setWindowTitle('Select Window')

        self.view = QExtendedGraphicsView()
        self.view.zoomEvent = self.zoomEvent
        self.setCentralWidget(self.view)
        self.local_scene = self.view.scene
        self.origin = self.view.origin

        self.scene_event_filter = GraphicsItemEventFilter(self.origin, self)

        self.points = []

        self.mask_opacity = 0
        self.last_maskname = None
        self.last_logname = None
        self.color_under_cursor = None

        self.local_images = []
        self.pixMapItems = []
        self.ImageDisplay = BigImageDisplay(self.origin, self)
        self.MaskDisplay = BigPaintableImageDisplay(self.origin)

        self.counter = []

        self.MarkerParent = QGraphicsPixmapItem(QPixmap(array2qimage(np.zeros([1, 1, 4]))), self.origin)
        self.MarkerParent.setZValue(10)

        self.MediaHandler = MediaHandler(join(srcpath, filename))
        self.UpdateImage()

        if len(types):
            self.Crosshair = Crosshair(self.MarkerParent, self.local_scene, self)

            self.counter = [MyCounter(self.local_scene, self, i) for i in range(len(types))]
            self.counter[active_type].SetToActiveColor()

        self.DrawCursorSize = 10
        self.drawPathItem = QGraphicsPathItem(self.MarkerParent)
        self.drawPathItem.setBrush(QBrush(QColor(255, 255, 255)))

        self.drawPath = self.drawPathItem.path()
        self.drawPathItem.setPath(self.drawPath)
        self.drawPathItem.setZValue(10)

        self.DrawCursorPath = QPainterPath()
        self.DrawCursorPath.addEllipse(-self.DrawCursorSize * 0.5, -self.DrawCursorSize * 0.5, self.DrawCursorSize,
                                       self.DrawCursorSize)

        self.DrawCursor = QGraphicsPathItem(self.DrawCursorPath, self.MarkerParent)
        self.DrawCursor.setBrush(QBrush(QColor(0, 0, 0, 0)))
        self.DrawCursor.setPen(QPen(QColor(0, 0, 255)))
        self.DrawCursor.setScale(0)

        self.UpdateDrawCursorSize()
        self.DrawMode = False
        if len(types):
            self.SetDrawMode(False)
        else:
            self.SetDrawMode(True)
            self.mask_opacity = 0.5
            self.MaskDisplay.setOpacity(self.mask_opacity)
        self.MaskChanged = False
        self.MaskUnsaved = False
        self.PointsUnsaved = False

        self.HelpText = HelpText(self)

        self.slider = SliderBox(self.view.hud_lowerRight, self.ImageDisplay)
        self.slider.setPos(-140, -140)

    def UpdateImage(self):
        self.MaskChanged = False

        filepath, filename = self.MediaHandler.getCurrentFilename()
        base_filename = os.path.splitext(filename)[0]
        self.current_maskname = os.path.join(outputpath, base_filename + maskname_tag)
        self.current_logname = os.path.join(outputpath, base_filename + logname_tag)

        self.setWindowTitle(filename)

        self.LoadImage(filename)
        self.LoadMask(self.current_maskname)
        self.LoadLog(self.current_logname)

    def LoadImage(self, filename):
        self.im = self.MediaHandler.getCurrentImg()
        self.ImageDisplay.SetImage(self.im)

    def LoadMask(self, maskname):
        self.current_maskname = maskname
        mask_valid = False
        print(maskname)
        if os.path.exists(maskname):
            print("Load Mask")
            try:
                self.image_mask_full = Image.open(maskname)
                print(self.image_mask_full)
                mask_valid = True
            except:
                mask_valid = False
                print("ERROR: Can't read mask file")
            print("...done")
        if mask_valid == False:
            self.image_mask_full = Image.new('L', (self.im.shape[1],self.im.shape[0]))
        self.MaskUnsaved = False

        self.MaskDisplay.SetImage(self.image_mask_full)

    def LoadLog(self, logname):
        self.current_logname = logname
        print(logname)
        if not tracking:
            while len(self.points):
                self.RemovePoint(self.points[0])
        if os.path.exists(logname):
            if tracking:
                for point in self.points:
                    point.setInvalidNewPoint()
            with open(logname) as fp:
                for index, line in enumerate(fp.readlines()):
                    line = line.strip().split(" ")
                    x = float(line[0])
                    y = float(line[1])
                    type = int(line[2])
                    if len(line) == 3:
                        if index >= len(self.points):
                            self.points.append(MyMarkerItem(x, y, self.MarkerParent, self, type))
                            self.points[-1].setScale(1/self.view.getOriginScale())
                        else:
                            self.points[index].addPoint(x,y,type)
                        continue
                    active = int(line[3])
                    if type == -1 or active == 0:
                        continue
                    id = line[4]
                    found = False
                    for point in self.points:
                        if point.id == id:
                            point.addPoint(x, y, type)
                            found = True
                            break
                    if not found:
                        self.points.append(MyMarkerItem(x, y, self.MarkerParent, self, type))
                        self.points[-1].setScale(1/self.view.getOriginScale())
                        self.points[-1].id = id
                        self.points[-1].setActive(active)
        else:
            for index in range(0, len(self.points)):
                self.points[index].setInvalidNewPoint()
        print("...done")
        self.PointsUnsaved = False

    def UpdateDrawCursorSize(self):
        global active_draw_type
        pen = QPen(QColor(*draw_types[active_draw_type][1]), self.DrawCursorSize)
        pen.setCapStyle(32)
        self.drawPathItem.setPen(pen)
        self.DrawCursorPath = QPainterPath()
        self.DrawCursorPath.addEllipse(-self.DrawCursorSize * 0.5, -self.DrawCursorSize * 0.5, self.DrawCursorSize,
                                       self.DrawCursorSize)

        self.DrawCursor.setPen(QPen(QColor(*draw_types[active_draw_type][1])))
        self.DrawCursor.setPath(self.DrawCursorPath)

    def RemovePoint(self, point):
        point.OnRemove()
        self.points.remove(point)
        self.local_scene.removeItem(point)
        self.PointsUnsaved = True

    def SaveMaskAndPoints(self):
        if self.PointsUnsaved:
            if len(self.points) == 0:
                if os.path.exists(self.current_logname):
                    os.remove(self.current_logname)
            else:
                data = ["%f %f %d %d %s\n" % (point.pos().x(), point.pos().y(), point.type, point.active, point.id) for point in self.points if point.active]
                with open(self.current_logname, 'w') as fp:
                    for line in data:
                        fp.write(line)
            print(self.current_logname, " saved")
            self.PointsUnsaved = False

        if self.MaskUnsaved:
            self.MaskDisplay.save(self.current_maskname)
            print(self.current_maskname, " saved")
            self.MaskUnsaved = False

    def SetDrawMode(self, doset):
        if doset is False:
            self.DrawMode = False
            self.DrawCursor.setScale(0)

            for point in self.points:
                point.SetActive(True)
            self.view.setCursor(QCursor(QtCore.Qt.ArrowCursor))
        else:
            self.DrawMode = True
            self.DrawCursor.setScale(1)

            for point in self.points:
                point.SetActive(False)
            self.view.setCursor(QCursor(QtCore.Qt.BlankCursor))

    def JumpFrames(self, amount):
        last_maskname = self.current_maskname
        last_logname = self.current_logname
        self.SaveMaskAndPoints()
        self.drawPath = QPainterPath()
        self.drawPathItem.setPath(self.drawPath)

        if self.MediaHandler.setCurrentPos(self.MediaHandler.getCurrentPos() + amount):
            self.UpdateImage()
            self.last_maskname = last_maskname
            self.last_logname = last_logname
        self.slider.onImageChange()

    def keyPressEvent(self, event):
        global active_type, point_display_type, active_draw_type
        sys.stdout.flush()

        #@key ---- General ----
        if event.key() == QtCore.Qt.Key_F1:
            #@key F1: toggle help window
            self.HelpText.ShowHelpText()

        numberkey = event.key() - 49

        if event.key() == QtCore.Qt.Key_S:
            #@key S: save marker and mask
            self.SaveMaskAndPoints()

        if event.key() == QtCore.Qt.Key_L:
            #@key L: load marker and mask from last image
            if self.last_logname:
                # saveguard/confirmation with MessageBox
                reply = QMessageBox.question(None, 'Warning', 'Load Mask & Points of last Image?', QMessageBox.Yes,
                                             QMessageBox.No)
                if reply == QMessageBox.Yes:
                    print('Loading last mask & points ...')
                    # load mask and log of last image
                    current_maskname = self.current_maskname
                    current_logname = self.current_logname
                    self.LoadMask(self.last_maskname)
                    self.LoadLog(self.last_logname)
                    self.current_maskname = current_maskname
                    self.current_logname = current_logname
                    # force save of mask and log
                    self.MaskUnsaved = True
                    self.PointsUnsaved = True
                    # refresh display
                    self.RedrawMask()

        #@key ---- Marker ----
        if self.DrawMode is False and 0 <= numberkey < len(types):
            #@key 0-9: change marker type
            self.counter[active_type].SetToInactiveColor()
            active_type = numberkey
            self.counter[active_type].SetToActiveColor()

        if event.key() == QtCore.Qt.Key_T:
            #@key T: toggle marker shape
            point_display_type += 1
            if point_display_type >= len(point_display_types):
                point_display_type = 0
            for point in self.points:
                point.UpdatePath()

        #@key ---- Painting ----
        if event.key() == QtCore.Qt.Key_P:
            #@key P: toogle brush mode
            if len(types):
                self.SetDrawMode(self.DrawMode is False)
                self.RedrawMask()

        if self.DrawMode is True and 0 <= numberkey < len(draw_types):
            #@key 0-9: change brush type
            active_draw_type = numberkey
            self.RedrawMask()
            print("Changed Draw type", active_draw_type)
            self.UpdateDrawCursorSize()

        if event.key() == QtCore.Qt.Key_K:
            #@key K: pick color of brush
            for index,type in enumerate(draw_types):
                if type[0] == self.color_under_cursor:
                    active_draw_type = index
                    break
            self.RedrawMask()
            print("Changed Draw type", active_draw_type)
            self.UpdateDrawCursorSize()
            self.color_under_cursor

        if event.key() == QtCore.Qt.Key_Plus:
            #@key +: increase brush radius
            self.DrawCursorSize += 1
            self.UpdateDrawCursorSize()
            if self.MaskChanged:
                self.RedrawMask()
        if event.key() == QtCore.Qt.Key_Minus:
            #@key -: decrease brush radius
            self.DrawCursorSize -= 1
            self.UpdateDrawCursorSize()
            if self.MaskChanged:
                self.RedrawMask()
        if event.key() == QtCore.Qt.Key_O:
            #@key O: increase mask transparency
            self.mask_opacity += 0.1
            if self.mask_opacity >= 1:
                self.mask_opacity = 1
            self.MaskDisplay.setOpacity(self.mask_opacity)

        if event.key() == QtCore.Qt.Key_I:
            #@key I: decrease mask transparency
            self.mask_opacity -= 0.1
            if self.mask_opacity <= 0:
                self.mask_opacity = 0
            self.MaskDisplay.setOpacity(self.mask_opacity)

        if event.key() == QtCore.Qt.Key_M:
            #@key M: redraw the mask
            self.RedrawMask()
        if event.key() == QtCore.Qt.Key_F:
            #@key F: fit image to view
            self.view.fitInView()

        #@key ---- Frame jumps ----
        if event.key() == QtCore.Qt.Key_Left:
            #@key Left: previous image
            self.JumpFrames(-1)
        if event.key() == QtCore.Qt.Key_Right:
            #@key Right: next image
            self.JumpFrames(+1)

        # JUMP keys
        if event.key() == Qt.Key_2 and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad 2: Jump -1 frame
            self.JumpFrames(-1)
            print('-1')
        if event.key() == Qt.Key_3 and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad 3: Jump +1 frame
            self.JumpFrames(+1)
            print('+1')
        if event.key() == Qt.Key_5 and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad 5: Jump -10 frame
            self.JumpFrames(-10)
            print('-10')
        if event.key() == Qt.Key_6 and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad 6: Jump +10 frame
            self.JumpFrames(+10)
            print('+10')
        if event.key() == Qt.Key_8 and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad 8: Jump -100 frame
            self.JumpFrames(-100)
            print('-100')
        if event.key() == Qt.Key_9 and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad 9: Jump +100 frame
            self.JumpFrames(+100)
            print('+100')
        if event.key() == Qt.Key_Slash and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad /: Jump -1000 frame
            self.JumpFrames(-1000)
            print('-1000')
        if event.key() == Qt.Key_Asterisk and event.modifiers() == Qt.KeypadModifier:
            #@key Numpad *: Jump +1000 frame
            self.JumpFrames(+1000)
            print('+1000')

        #@key ---- Gamma/Brightness Adjustment ---
        if event.key() == Qt.Key_Space:
            #@key Space: update rect
            self.ImageDisplay.PreviewRect()
            self.ImageDisplay.Change()
            self.slider.updateHist(self.ImageDisplay.hist)

    def RedrawMask(self):
        self.MaskDisplay.UpdateImage()
        self.drawPath = QPainterPath()
        self.drawPathItem.setPath(self.drawPath)
        self.MaskChanged = False


for addon in addons:
    with open(addon + ".py") as f:
        code = compile(f.read(), addon + ".py", 'exec')
        exec (code)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    if use_filedia is True or filename is None:
        tmp = QFileDialog.getOpenFileName(None, "Choose Image", srcpath)
        srcpath = os.path.split(str(tmp))[0]
        filename = os.path.split(str(tmp))[-1]
        print(srcpath)
        print(filename)
    if outputpath is None:
        outputpath = srcpath

    window = DrawImage()
    window.show()
    app.exec_()
