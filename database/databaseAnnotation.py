from __future__ import division, print_function
import os
import re
import glob

try:
    from PyQt5 import QtGui, QtCore
    from PyQt5.QtWidgets import QWidget, QTextStream, QGridLayout
    from PyQt5.QtCore import Qt
except ImportError:
    from PyQt4 import QtGui, QtCore
    from PyQt4.QtGui import QWidget, QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QTableWidget, QHeaderView, QTableWidgetItem
    from PyQt4.QtCore import Qt, QTextStream, QFile, QStringList

from abc import abstractmethod

from peewee import *
from datetime import datetime


class SQLAnnotation(Model):
        timestamp = DateTimeField()
        system = CharField()
        camera = CharField()
        tags =  CharField()
        rating = IntegerField()
        reffilename = CharField()
        reffileext = CharField()
        comment = TextField()
        fileid = IntegerField()

        class Meta:
            database = None

class tags(Model):
    name = CharField()

class tagassociation(Model):
    annotation_id = IntegerField()
    tag_id = IntegerField()

# TODO: make sure this doesn't overwrite actual config!
class config:
    def __init__(self):
        self.sql_dbname = 'annotation'
        self.sql_host = '131.188.117.94'
        self.sql_port = 3306
        self.sql_user = 'clickpoints'
        self.sql_pwd = '123456'

class DatabaseAnnotation:
    def __init__(self,config):
        self.config = config

        # init db connection
        self.db = MySQLDatabase(self.config.sql_dbname,
                                host=self.config.sql_host,
                                port=self.config.sql_port,
                                user=self.config.sql_user,
                                passwd=self.config.sql_pwd)

        self.db.connect()

        if self.db.is_closed():
            raise Exception("Couldn't open connection to DB %s on host %s",self.config.sql_dbname,self.config.sql_host)
        else:
            print("connection established")

        # generate acess class
        self.SQLAnnotation = SQLAnnotation
        self.SQLAnnotation._meta.database=self.db
        self.SQLTags = tags
        self.SQLTags._meta.database = self.db
        self.SQLTagAssociation = tagassociation
        self.SQLTagAssociation._meta.database = self.db

        self.tag_dict_byID = {}
        self.tag_dict_byName = {}
        self.updateTagDict()

    ''' Annotation Handling '''
    # TODO add annotation utility function
    def getAnnotationByID(self,id):
        item=self.SQLAnnotation.get(self.SQLAnnotation.id==id)

        comment=item.comment
        results={}
        results['timestamp']=datetime.strftime(item.timestamp,'%Y%m%d-%H%M%S')
        results['system']=item.system
        results['camera']=item.camera
        results['rating']=item.rating
        results['reffilename']=item.reffilename
        results['feffileext']=item.reffileext

        tag_list=self.getTagsForAnnotationID(item.id)
        results['tags']= tag_list
        return results, comment



    def getAnnotationByBasename(self,basename):
        item=self.SQLAnnotation.get(self.SQLAnnotation.reffilename==basename)

        comment=item.comment
        results={}
        results['timestamp']=datetime.strftime(item.timestamp,'%Y%m%d-%H%M%S')
        results['system']=item.system
        results['camera']=item.camera
        results['rating']=item.rating
        results['reffilename']=item.reffilename
        results['feffileext']=item.reffileext

        tag_list=self.getTagsForAnnotationID(item.id)
        results['tags']= tag_list
        return results, comment


    ''' Tag Handling'''
    def updateTagDict(self):
        self.tag_dict_byID = {}
        self.tag_dict_byName = {}

        res = self.SQLTags.select()
        for item in res:
            self.tag_dict_byName[item.name] = item.id
        # add inverted dictionary
        self.tag_dict_byID =  {v: k for k, v in self.tag_dict_byName.items()}

    def getTagID(self,tag_name):
        return self.tag_dict_byName[tag_name]

    def getTagName(self,id):
        return self.tag_dict_byID[id]

    def getTagList(self):
        return self.tag_dict_byID.values()

    def newTag(self,tag_name):
        tag_id = self.SQLTags.create(name=tag_name).id
        self.updateTagDict()
        return tag_id

    def updateTagTable(self,tag_list):
        # check for all tags in list
        for tag in tag_list:
            # if tag does not exist - add
            if not tag in self.tag_dict_byID.values():
                self.newTag(tag)

    def getTagsFromIDs(self,id_list):
        tags=[]
        for id in id_list:
            try:
                tags.append(self.getTagName(id))
            except:
                raise Exception("requested tag id: %d not found" % id)

        return tags

    def getIDsFromTags(self,tag_list):
        ids=[]
        for tag in tag_list:
            try:
                ids.append(self.getTagID(tag))
            except:
                raise Exception("requested tag name: %s not found" % tag)
        return ids

    ''' tag association '''
    def getTagsForAnnotationID(self,id):
        self.updateTagDict()

        tagIDs = self.SQLTagAssociation.select().where(self.SQLTagAssociation.annotation_id==id)
        tag_list= [self.tag_dict_byID[item.tag_id] for item in tagIDs]
        print(tag_list)
        return tag_list

    def setTagsForAnnotationID(self,id,tag_list):
        tagIDs = self.SQLTagAssociation.select().where(self.SQLTagAssociation.annotation_id==id)

        #TODO: discuss if this is bad practice?
        # delete all old tags
        for item in tagIDs:

            item.delete_instance()

        # add new tags
        tag_id_list = [ self.tag_dict_byName[tag] for tag in tag_list]
        for tag in tag_id_list:
            self.SQLTagAssociation.create(annotation_id=id,tag_id=tag)









if __name__ == '__main__':
    database = DatabaseAnnotation(config())