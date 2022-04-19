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
import time
import shutil
import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GdkPixbuf, GLib


def __eprint__(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=sys.stderr, **kwargs)


if sys.version_info[0] == 2:
    __eprint__("Please run with Python 3 as Python 2 is End-of-Life.")
    exit(2)

# supported file types
file_types = ("jpg", "jpeg", "jpe", "png", "svg", "gif", "tif", "tiff")

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
                if each1[1].split(".")[-1].lower() not in file_types:
                    del db[each][each1[0]]
    delete = []
    for each in db:
        if db[each] == []:
            delete.append(each)
    for each in delete:
        del db[each]
    return db

def __mount__(device, path_dir):
    """Mount device at path
    It would be much lighter weight to use ctypes to do this
    But, that keeps throwing an 'Invalid Argument' error.
    Calling Mount with check_call is the safer option.
    """
    pipe = subprocess.Popen(["sudo", "mount", device, path_dir],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out = pipe.stderr.read().decode()
    print(out)
    if "already mounted" in out:
        raise Exception
    if "does not exist" in out:
        raise OSError



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
        if image_override != 1:
            with open("/mnt/settings.json", "r") as file:
                self.settings = json.load(file)
        else:
            print("Cannot find drive...")
            with open("remote_data/settings.json", "r") as file:
                self.settings = json.load(file)
        self.settings["show_for"] *= 1000
        self.grab_error_files(errors)
        self.check_errors(image_override)
        self.pick_pic()
        GLib.timeout_add(self.settings["show_for"], self.pick_pic)

    def grab_error_files(self, errors):
        """Grab error files and pull them into memory"""
        for each in errors["errors"]:
            self.errors.append(GdkPixbuf.Pixbuf.new_from_file("errors/" + each))

    def check_errors(self, image_override):
        """Window for PyPicFrame"""
        if image_override is not None:
            image = Gtk.Image.new_from_pixbuf(self.errors[image_override])
            self.grid.attach(image, 1, 1, 1, 1)
            self.show_all()

    def pick_pic(self):
        """Pick a random picture from the index. Replace displayed image with new image."""
        if self.settings["honor_rating"]:
            num = rand.randint(1, 151)
            num = round(num, -1) / 10
            if num > 10:
                num = 5
            elif 6 < num <= 10:
                num = 4
            elif 3 < num <= 6:
                num = 3
            elif 1 < num <= 3:
                num = 2
            else:
                num = 1
        else:
            num = rand.randint(1, 6)
        string = "x" * num
        try:
            opts = self.image_index[string]
        except KeyError:
            return self.pick_pic()
        image = opts[rand.randint(0, len(opts) - 1)]
        path = "/mnt/" + string + "/" + image
        print(f"Chose: {path}")
        # we know what image we want now. Now, remove the old one and use the new one
        try:
            image = GdkPixbuf.Pixbuf.new_from_file(path)
        except gi.repository.GLib.GError:
            self.image_index = index_folder("/mnt")
            return self.pick_pic()
        image = scale(image)
        image = Gtk.Image.new_from_pixbuf(image)
        self.grid.remove_row(1)
        self.grid.attach(image, 1, 1, 1, 1)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.fullscreen()
        self.show_all()
        return True

    def exit(self, button):
        """Exit"""
        Gtk.main_quit("delete-event")
        self.destroy()


def scale(image):
    """Scale an image up or down depending on what's needed"""
    screen_res = get_screen_res()
    image_res = (image.get_width(), image.get_height())
    # we have horizontal realestate to spare. If vertical realestate matches, and
    # horizontal realestate is equal to or greater than used realestate, return
    # the image without modification
    if (((image_res[1] - 10) <= screen_res[1] <= (image_res[1] + 10)) and (image_res[0] <= screen_res[0])):
        return image
    # either the vertical realestate doesn't match, or the horizontal usage is
    # greater than what we have, or both
    # scale down situations first
    if image_res[1] > screen_res[1]:
        return scale_up(image, screen_res, image_res)
    if image_res[0] > screen_res[0]:
        return scale_down(image, screen_res, image_res)
    if image_res[1] < screen_res[1]:
        return scale_up(image, screen_res, image_res)


def scale_down(image, screen_res, image_res):
    """Scale images down"""
    arh = image_res[0] / image_res[1]
    arw = image_res[1] / image_res[0]
    nw = screen_res[1] * arw
    nh = screen_res[0] * arh
    screen_area = screen_res[0] * screen_res[1]
    nha = screen_res[0] * nh
    nwa = screen_res[1] * nw
    nhw = abs(nha - screen_area)
    nww = abs(nwa - screen_area)
    if nww <= nhw:
        res = (nw, screen_res[1])
    else:
        res = (screen_res[0], nh)
    return image.scale_simple(res[0], res[1], GdkPixbuf.InterpType.BILINEAR)


def scale_up(image, screen_res, image_res):
    """Scale images up"""
    aspect_ratio = image_res[0] / image_res[1]
    new_width = screen_res[1] * aspect_ratio
    return image.scale_simple(new_width, screen_res[1],
                              GdkPixbuf.InterpType.BILINEAR)


def get_screen_res():
    """Get screen resolution"""
    results = subprocess.check_output(['xrandr']).decode().split("current")[1].split(",")[0]
    width = results.split("x")[0].strip()
    height = results.split("x")[1].strip()
    width = int(width)
    height = int(height)
    return (width, height)

def show_window(errors, index, override):
    """Show Main UI"""
    window = PyPicFrame(errors, index, image_override=override)
    window.set_decorated(False)
    window.set_resizable(False)
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

try:
    __mount__(part, "/mnt")
    index_main = index_folder("/mnt")
except OSError:
    # pass
    index_main = {}
    override = 1
    print("Drive not mountable.")
except Exception:
    index_main = index_folder("/mnt")
    print("Drive already mounted.")

index_errors = {"errors": ["json_error.svg", "no_drive.svg", "no_pics.svg", "new_drive.svg"]}
if ((index_main == {}) and (override is None)):
    # check if folders exist
    ls = os.listdir("/mnt")
    total = 0
    string = "x"
    for each in range(1, 6):
        if (string * each) not in ls:
            total += 1
    if not os.path.exists("/mnt/settings.json"):
        total += 1
    if total >= 5:
        override = 3
    else:
        for each in range(1, 6):
            if (string * each) not in ls:
                os.mkdir("/mnt/" + (string * each))
        if not os.path.exists("/mnt/settings.json"):
            shutil.copyfile("remote_data/settings.json", "/mnt/settings.json")
if override == 1:
    print("FORKED!")
    pid = os.fork()
    """ from here, the CHILD needs to be the UI. The parent should watch for the drive,
    and once present, kill the child, recurse, then exit."""
    if pid != 0:
        while True:
            try:
                __mount__(part, "/mnt")
            except OSError:
                time.sleep(1)
                continue
            os.kill(pid, 9)
            subprocess.Popen([sys.argv[0]])
            exit()
if override == 3:
    print("FORKED!")
    pid = os.fork()
    """ from here, the CHILD needs to be the UI. The parent should set up the drive,
    and once done, kill the child, recurse, then exit."""
    if pid != 0:
        time.sleep(10)
        # set up the drive
        if not os.path.exists("/mnt/README.txt"):
            shutil.copyfile("remote_data/README.txt", "/mnt/README.txt")
        if not os.path.exists("/mnt/settings.json"):
            shutil.copyfile("remote_data/settings.json", "/mnt/settings.json")
        string = "x"
        for each in range(1, 6):
            os.mkdir("/mnt/" + (string * each))
        os.kill(pid, 9)
        subprocess.Popen([sys.argv[0]])
        exit()
if override == 2:
    print("FORKED!")
    pid = os.fork()
    """ from here, the CHILD needs to be the UI. The parent should watch for images.
    Once images are found, it should kill the child, recurse, then exit."""
    if pid != 0:
        while True:
            index_main = index_folder("/mnt")
            if index_main != {}:
                break
            time.sleep(3)
        os.kill(pid, 9)
        subprocess.Popen([sys.argv[0]])
        exit()
show_window(index_errors, index_main, override)
