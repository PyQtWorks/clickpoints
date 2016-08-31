#!/usr/bin/env python
# -*- coding: utf-8 -*-
# FilelistLoader.py

# Copyright (c) 2015-2016, Richard Gerum, Sebastian Richter
#
# This file is part of ClickPoints.
#
# ClickPoints is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ClickPoints is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ClickPoints. If not, see <http://www.gnu.org/licenses/>

from __future__ import division, print_function, unicode_literals
import os
import glob
import time
from datetime import datetime

from includes import BroadCastEvent2

from qtpy import QtGui, QtCore, QtWidgets
import qtawesome as qta
from QtShortCuts import AddQLabel, AddQSpinBox, AddQCheckBox, AddQHLine, AddQLineEdit

class OptionEditor(QtWidgets.QWidget):
    def __init__(self, window, data_file):
        QtWidgets.QWidget.__init__(self)
        self.window = window
        self.data_file = data_file

        # Widget
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.setWindowTitle("Options - ClickPoints")

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.list_layout = QtWidgets.QVBoxLayout()
        self.stackedLayout = QtWidgets.QStackedLayout()
        self.top_layout = QtWidgets.QHBoxLayout()
        self.top_layout.addLayout(self.list_layout)
        self.main_layout.addLayout(self.top_layout)

        layout = QtWidgets.QHBoxLayout()
        layout.addStretch()
        self.button_ok = QtWidgets.QPushButton("Ok")
        self.button_ok.clicked.connect(self.Ok)
        layout.addWidget(self.button_ok)
        self.button_cancel = QtWidgets.QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.Cancel)
        layout.addWidget(self.button_cancel)
        self.button_apply = QtWidgets.QPushButton("Apply")
        self.button_apply.clicked.connect(self.Apply)
        self.button_apply.setDisabled(True)
        layout.addWidget(self.button_apply)
        self.main_layout.addLayout(layout)

        self.list = QtWidgets.QListWidget()
        self.list_layout.addWidget(self.list)
        self.list.setMaximumWidth(80)

        self.list.currentRowChanged.connect(self.stackedLayout.setCurrentIndex)
        self.top_layout.addLayout(self.stackedLayout)

        self.setWindowIcon(qta.icon("fa.gears"))

        self.edits = []

        for category in self.data_file._options:
            item = QtWidgets.QListWidgetItem(category, self.list)

            group = QtWidgets.QGroupBox(category)
            group.setFlat(True)
            self.layout = QtWidgets.QVBoxLayout()
            group.setLayout(self.layout)
            self.stackedLayout.addWidget(group)

            for option in self.data_file._options[category]:
                if option.hidden:
                    continue
                value = option.value if option.value is not None else option.default
                if option.value_type == "int":
                    if option.value_count > 1:
                        edit = AddQLineEdit(self.layout, option.display_name, ", ".join(str(v) for v in value))
                        edit.textChanged.connect(lambda value, edit=edit, option=option: self.Changed(edit, value, option))
                        QtWidgets.QToolTip.showText(QtCore.QPoint(0, 0), "heyho", edit)
                    else:
                        edit = AddQSpinBox(self.layout, option.display_name, int(value), float=False)
                        if option.min_value is not None:
                            edit.setMinimum(option.min_value)
                        if option.max_value is not None:
                            edit.setMaximum(option.max_value)
                        edit.valueChanged.connect(lambda value, edit=edit, option=option: self.Changed(edit, value, option))
                if option.value_type == "float":
                    edit = AddQSpinBox(self.layout, option.display_name, float(value), float=True)
                    if option.min_value is not None:
                        edit.setMinimum(option.min_value)
                    if option.max_value is not None:
                        edit.setMaximum(option.max_value)
                    edit.valueChanged.connect(lambda value, edit=edit, option=option: self.Changed(edit, value, option))
                if option.value_type == "bool":
                    edit = AddQCheckBox(self.layout, option.display_name, value)
                    edit.stateChanged.connect(lambda value, edit=edit, option=option: self.Changed(edit, value, option))
                if option.value_type == "string":
                    edit = AddQLineEdit(self.layout, option.display_name, value)
                    edit.textChanged.connect(lambda value, edit=edit, option=option: self.Changed(edit, value, option))
                if option.tooltip:
                    edit.setToolTip(option.tooltip)
                edit.current_value = None
                edit.option = option
                edit.error = None
                edit.has_error = False
                self.edits.append(edit)
            self.layout.addStretch()

    def list_selected(self):
        pass

    def ShowFieldError(self, field, error):
        if field.error is None:
            field.error = QtWidgets.QLabel(error, self)
            field.error.setStyleSheet("background-color: #FDD; border-width: 1px; border-color: black; border-style: outset;")
            field.error.move(field.pos().x() + field.error.width(), field.pos().y() + field.error.height() + 5)
            field.error.setMinimumWidth(180)
        field.error.setText(error)
        field.error.show()

    def Changed(self, field, value, option):
        if field.error is not None:
            field.error.hide()
        field.has_error = False
        if option.value_type == "int":
            if option.value_count > 1:
                value = value.strip()
                if (value.startswith("(") and value.endswith(")")) or (value.startswith("[") and value.endswith("]")):
                    value = value[1:-1].strip()
                if value.endswith(","):
                    value = value[:-1].strip()
                try:
                    value = [int(v) for v in value.split(",")]
                except ValueError:
                    field.setStyleSheet("background-color: #FDD;")
                    for v in value.split(","):
                        try:
                            int(v)
                        except ValueError:
                            self.ShowFieldError(field, "Only <b>integer</b> values are allowed.<br/>'%s' can't be parsed as an int." % v.strip())
                    field.has_error = True
                    return
                if len(value) != option.value_count:
                    field.setStyleSheet("background-color: #FDD;")
                    self.ShowFieldError(field, "The field needs <b>%d integers</b>,<br/>but %d are provided." % (option.value_count, len(value)))
                    field.has_error = True
                    return
                else:
                    field.setStyleSheet("")
            else:
                value = int(value)
        if option.value_type == "float":
            value = float(value)
        if option.value_type == "bool":
            value = bool(value)
        field.current_value = value
        self.button_apply.setDisabled(False)

    def Apply(self):
        for edit in self.edits:
            if edit.has_error:
                QtWidgets.QMessageBox.critical(None, 'Error',
                                               'Input field \'%s\' contain errors, settings can\'t be saved.' % edit.option.display_name,
                                               QtWidgets.QMessageBox.Ok)
                return False
        for edit in self.edits:
            if edit.current_value is not None:
                self.data_file.setOption(edit.option.key, edit.current_value)
        self.button_apply.setDisabled(True)
        self.window.JumpFrames(0)
        return True

    def Ok(self):
        if self.Apply():
            self.close()

    def Cancel(self):
        self.close()