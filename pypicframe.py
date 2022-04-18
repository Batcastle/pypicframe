#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  pypicframe.py
#
#  Copyright 2022 Thomas Castleman <contact@draugeros.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
"""Smart Picture Frame software for the Raspberry Pi and similar SBCs"""
from __future__ import print_function
import sys
import random as rand
import os
import json
import subprocess
import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GdkPixbuf, Gdk


def __eprint__(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=sys.stderr, **kwargs)


if sys.version_info[0] == 2:
    __eprint__("Please run with Python 3 as Python 2 is End-of-Life.")
    exit(2)


def index_folder(folder):
    """Get contents of all necessary files in remote settings folder"""
    db = {}
    top_level = os.listdir(folder)
    folders = ["x", "xx", "xxx", "xxxx", "xxxxx"]
    for each in folders:
        if each in top_level:
            new = os.listdir(folder + "/" + each)
            if new == []:
                continue
            db[each] = new
            for each1 in enumerate(db[each]):
                if os.path.isdir(folder + "/" + each + "/" + each1[1]):
                    del db[each][each1[0]]
    return db

def __mount__(device, path_dir):
    """Mount device at path
    It would be much lighter weight to use ctypes to do this
    But, that keeps throwing an 'Invalid Argument' error.
    Calling Mount with check_call is the safer option.
    """
    try:
        subprocess.check_call(["sudo", "mount", device, path_dir])
    except subprocess.CalledProcessError:
        pass


class PyPicFrame(Gtk.Window):
    """Main UI Window"""
    def __init__(self, errors, image_index, image_override=None):
        """Initialize the Window"""
        Gtk.Window.__init__(self, title="PyPicFrame")
        self.grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.grid)
        self.errors = []
        self.image_index = image_index
        if ((image_index == {}) and (image_override is None)):
            image_override = 2
        self.grab_errors(errors)
        self.main(image_override)

    def grab_errors(self, errors):
        """Grab error files and pull them into memory"""
        for each in errors["errors"]:
            self.errors.append(GdkPixbuf.Pixbuf.new_from_file("errors/" + each))

    def main(self, image_override):
        """Window for PyPicFrame"""
        if image_override is not None:
            image1 = Gtk.Image.new_from_pixbuf(self.errors[image_override])
            self.grid.attach(image1, 1, 1, 1, 1)
            self.show_all()

    def exit(self, button):
        """Exit"""
        Gtk.main_quit("delete-event")
        self.destroy()


def show_window(errors, index, override):
    """Show Main UI"""
    window = PyPicFrame(errors, index, image_override=override)
    window.set_decorated(False)
    window.set_resizable(False)
    window.fullscreen()
    window.set_position(Gtk.WindowPosition.CENTER)
    window.show_all()
    Gtk.main()


override=None
try:
    try:
        with open("/etc/pypicframe/internal_settings.json", "r") as file:
            part = json.load(file)["part"]
    except FileNotFoundError:
        try:
            with open("internal_settings.json", "r") as file:
                part = json.load(file)["part"]
        except FileNotFoundError:
            print("Cannot Find Internal Settings File. Defaulting 'part' to /dev/sda1...")
            part = "/dev/sda1"
except json.decoder.JSONDecodeError:
    print("Error Reading Internal Settings File. Defaulting 'part' to /dev/sda1...")
    part = "/dev/sda1"
    override = 0

__mount__(part, "/mnt")
index_main = index_folder("/mnt")
index_errors = {"errors": ["json_error.svg", "no_drive.svg", "no_pics.svg"]}
show_window(index_errors, index_main, override)
