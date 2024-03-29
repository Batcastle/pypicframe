#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  pypicframe.py
#
#  Copyright 2023 Thomas Castleman <batcastle@draugeros.org>
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
from Xlib.display import Display
from ctypes import cdll, byref, create_string_buffer
import psutil
import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GdkPixbuf, GLib


def __eprint__(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=sys.stderr, **kwargs)


if sys.version_info[0] == 2:
    __eprint__("Please run with Python 3 as Python 2 is End-of-Life.")
    sys.exit(2)


try:
    try:
        with open("/etc/pypicframe/internal_settings.json", "r") as file:
            settings = json.load(file)
    except FileNotFoundError:
        try:
            with open("internal_settings.json", "r") as file:
                settings = json.load(file)
        except FileNotFoundError:
            print("Cannot Find Internal Settings File. Defaulting internal backups...")
            settings = {
                            "part": "/dev/sde1",
                            "logfile": "./pypicframe.log"
                        }
    part = settings["part"]
    logfile = settings["logfile"]
except json.decoder.JSONDecodeError:
    print("Error Reading Internal Settings File. Defaulting internal backups...")
    settings = {
                            "part": "/dev/sde1",
                            "logfile": "./pypicframe.log"
                        }
    part = settings["part"]
    logfile = settings["logfile"]
    override = 0


def log(output):
    """Print log data to STDOUT and log file"""
    try:
        global logfile
    except NameError:
        try:
            with open("/etc/pypicframe/internal_settings.json", "r") as file:
                settings = json.load(file)
        except FileNotFoundError:
            try:
                with open("internal_settings.json", "r") as file:
                    settings = json.load(file)
            except FileNotFoundError:
                settings = {
                                "part": "/dev/sde1",
                                "logfile": "./pypicframe.log"
                            }
        logfile = settings["logfile"]
    try:
        with open(logfile, "a+") as file:
            file.write(output)
            file.write("\n")
    except PermissionError:
        with open("./pypicframe.log", "a+") as file:
            file.write(output)
            file.write("\n")
    print(output)


# supported file types
file_types = ("jpg", "jpeg", "jpe", "png", "svg", "gif", "tif", "tiff")

# check to make sure we are running in a good place
ls = os.listdir()
if "errors" not in ls:
    try:
        os.chdir("/etc/pypicframe")
    except FileNotFoundError:
        log("Data not available in current directory.", end=" ")
        log("Either install PyPicFrame to your system or run from", end=" ")
        log("within the local git repo.")
        sys.exit(2)


def set_procname(newname):
    """set procname for current process"""
    libc = cdll.LoadLibrary('libc.so.6')    #Loading a 3rd party library C
    buff = create_string_buffer(len(newname) + 1) #Note: One larger than the name (man prctl says that)
    buff.value = bytes(newname, 'utf-8')               #Null terminated string as it should be
    libc.prctl(15, byref(buff), 0, 0, 0) #Refer to "#define" of "/usr/include/linux/prctl.h" for the misterious value 16 & arg[3..5] are zero as the man page says.


def index_folder(folder):
    """Get contents of all necessary files in remote settings folder"""
    database = {}
    top_level = os.listdir(folder)
    folders = ["x", "xx", "xxx", "xxxx", "xxxxx"]
    for each in folders:
        if each in top_level:
            new = os.listdir(folder + "/" + each)
            if new == []:
                continue
            database[each] = new
            for each1 in enumerate(database[each]):
                if os.path.isdir(folder + "/" + each + "/" + each1[1]):
                    del database[each][each1[0]]
                if each1[1].split(".")[-1].lower() not in file_types:
                    del database[each][each1[0]]
    delete = []
    for each in database:
        if database[each] == []:
            delete.append(each)
    for each in delete:
        del database[each]
    size = 0
    for each in database:
        size += len(database[each])
    return {"index": database, "size": size}


def __mount__(device, path_dir):
    """Mount device at path
    It would be much lighter weight to use ctypes to do this
    But, that keeps throwing an 'Invalid Argument' error.
    Calling Mount with check_call is the safer option.
    """
    with subprocess.Popen(["sudo", "mount", device, path_dir],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE) as pipe:
        out = pipe.stderr.read().decode()
    if "already mounted" in out:
        raise Exception
    if "does not exist" in out:
        raise OSError


def __umount__(path_dir):
    return subprocess.check_call(["sudo", "umount", path_dir])


# This code handles auto-mounting and adaptive handling of that situation for PyPicFrame
if "--no-fork" not in sys.argv:
    # GUI_pid = os.fork()
    GUI_pid = -1
    log(f"Background process: {GUI_pid}")
    if GUI_pid != 0:
        # status indicator:
        #   0: device not attached
        #   1: device attached but not mounted
        #   2: device attached and mounted
        #
        # These are only to be set AFTER handling the above status, but checked for
        # before handling.
        set_procname("ppf-mounter")


        def restart_child(pid, options=[]):
            if pid is not None:
                try:
                    os.kill(pid, 15)
                    os.kill(pid, 9)
                except ProcessLookupError:
                    log(f"Process { pid } not found.")
            command = [sys.argv[0], "--no-fork"]
            if isinstance(options, list):
                command = command + options
            elif isinstance(options, str):
                command.append(options)
            log(command)
            new_pid = subprocess.Popen(command).pid
            return new_pid


        status = 0
        while True:
            status_kernel = subprocess.check_output(["lsblk", "--json",
                                                     "--output",
                                                     "path,mountpoint"]).decode()
            status_kernel = json.loads(status_kernel)["blockdevices"]
            index = -1
            for each in status_kernel:
                if each["path"] == part:
                    index = each
                    break
            if index == -1:
                # device not attached. Handle.
                if status == 2:
                    __umount__("/mnt")
                if status != 0:
                    GUI_pid = restart_child(GUI_pid, "--no-device")
                elif GUI_pid == -1:
                    # Initialize with no device flag
                    GUI_pid = restart_child(None, "--no-device")
                status = 0
                time.sleep(3)
                continue
            if "/mnt" != index["mountpoint"]:
                # device attached but not mounted. Handle.
                try:
                    __mount__(part, "/mnt")
                except OSError:
                    # pass
                    log("Drive not mountable.")
                    time.sleep(3)
                except Exception:
                    log("Drive already mounted.")
                if os.listdir("/mnt") == []:
                    GUI_pid = restart_child(GUI_pid, "--setup")
                    time.sleep(1)
                status = 1
                continue
            if GUI_pid == -1:
                # Initialize
                GUI_pid = subprocess.Popen(sys.argv + ["--no-fork"]).pid
                status = 2
                continue
            if status != 2:
                # device NEWLY attached AND mounted. Handle.
                GUI_pid = restart_child(GUI_pid)
                status = 2
                continue
            time.sleep(2)


def get_screen_res():
    """Get screen resolution"""
    screen = Display(':0').screen()
    return (int(screen.width_in_pixels), int(screen.height_in_pixels))


class PyPicFrame(Gtk.Window):
    """Main UI Window"""
    def __init__(self, errors, image_index, image_override=None):
        """Initialize the Window"""
        Gtk.Window.__init__(self, title="PyPicFrame")
        self.grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.grid)
        self.errors = []
        self.image_index = image_index
        self.displayed_image = None
        if ((image_index["size"] == 0) and (image_override is None)):
            image_override = 2
        if image_override not in (1, 3):
            with open("/mnt/settings.json", "r") as file:
                self.settings = json.load(file)
        else:
            log("Cannot find drive...")
            with open("remote_data/settings.json", "r") as file:
                self.settings = json.load(file)
        self.settings["show_for"] *= 1000
        self.grab_error_files(errors)
        overridden = self.check_errors(image_override)
        if overridden:
            return
        self.pick_pic()
        GLib.timeout_add(self.settings["show_for"], self.pick_pic)

    def grab_error_files(self, errors):
        """Grab error files and pull them into memory"""
        for each in errors["errors"]:
            log(f"Grabbing errors/{each}")
            image = GdkPixbuf.Pixbuf.new_from_file("errors/" + each)
            image = scale(image)[0]
            self.errors.append(image)

    def check_errors(self, image_override):
        """Window for PyPicFrame"""
        if image_override is not None:
            image = Gtk.Image.new_from_pixbuf(self.errors[image_override])
            self.grid.remove_row(1)
            self.grid.attach(image, 1, 1, 1, 1)
            self.display()
            return True
        return False

    def pick_pic(self):
        """Pick a random picture from the index. Replace displayed image with new image."""
        # we only have, at most, one image to show. So don't change anything.
        if self.image_index["size"] < 2:
            return True
        if self.settings["honor_rating"]:
            num = rand.randint(1, 150)
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
            opts = self.image_index["index"][string]
        except KeyError:
            test = index_folder("/mnt")
            if test["size"] == 0:
                # the drive has likely been removed and has not been reinserted yet
                # since we don't cache all the images into RAM, we can't do anything other
                # than throw up an error since those are stored internally AND cached
                self.restart()
            # this MIGHT happen, but shouldn't. Essentially what is happening if we get here is that
            # files changed on the drive while we weren't looking
            self.image_index = test
            return self.pick_pic()
        if len(opts) > 1:
            image = opts[rand.randint(0, len(opts) - 1)]
        else:
            image = opts[0]
        path = "/mnt/" + string + "/" + image
        # make sure we don't just reset the image. Pick a new one each time.
        if self.displayed_image == path:
            return self.pick_pic()
        self.displayed_image = path
        log(f"Chose: {path}")
        # we know what image we want now. Now, remove the old one and use the new one
        try:
            image = GdkPixbuf.Pixbuf.new_from_file(path)
        except gi.repository.GLib.GError:
            self.image_index = index_folder("/mnt")
            return self.pick_pic()
        image = scale(image)
        image[0] = Gtk.Image.new_from_pixbuf(image[0])
        self.grid.remove_row(1)
        self.grid.attach(image[0], 1, 1, 1, 1)
        self.display(resolution=image[1])
        return True

    def display(self, resolution=get_screen_res()):
        """handle show_all() calls"""
        res = get_screen_res()
        if (res[0] - 10) > resolution[0]:
            self.unfullscreen()
        else:
            self.fullscreen()
        self.set_position(Gtk.WindowPosition.CENTER)
        self.show_all()

    def restart(self):
        """Exit"""
        Gtk.main_quit("delete-event")
        self.destroy()
        subprocess.Popen([sys.argv[0]])
        sys.exit()



def scale(image):
    """Scale an image up or down depending on what's needed"""
    screen_res = get_screen_res()
    image_res = (image.get_width(), image.get_height())
    # we have horizontal realestate to spare. If vertical realestate matches,
    # and horizontal realestate is equal to or greater than usable realestate,
    # return the image without modification
    image = image.apply_embedded_orientation() # make sure the image is oriented correctly
    if (image_res[1] - 10) <= screen_res[1] <= (image_res[1] + 10):
        if image_res[0] <= screen_res[0]:
            return [image, image_res]
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
    aspect_ratio_to_height = image_res[0] / image_res[1]
    aspect_ratio_to_width = image_res[1] / image_res[0]
    new_width = screen_res[1] * aspect_ratio_to_width
    new_height = screen_res[0] * aspect_ratio_to_height
    screen_area = screen_res[0] * screen_res[1]
    new_height_area = screen_res[0] * new_height
    new_width_area = screen_res[1] * new_width
    new_height_wasted = abs(new_height_area - screen_area)
    new_width_wasted = abs(new_width_area - screen_area)
    if new_width_wasted <= new_height_wasted:
        res = (new_width, screen_res[1])
    else:
        res = (screen_res[0], new_height)
    return [image.scale_simple(res[0], res[1],
                               GdkPixbuf.InterpType.BILINEAR), res]


def scale_up(image, screen_res, image_res):
    """Scale images up"""
    aspect_ratio = image_res[0] / image_res[1]
    new_width = screen_res[1] * aspect_ratio
    return [image.scale_simple(new_width, screen_res[1],
                              GdkPixbuf.InterpType.BILINEAR),
            (new_width, screen_res[1])]


def show_window(errors, index, override):
    """Show Main UI"""
    window = PyPicFrame(errors, index, image_override=override)
    window.set_decorated(False)
    window.set_resizable(False)
    window.show_all()
    Gtk.main()


override=None
if "--setup" in sys.argv:
    override = 3
elif "--no-device" in sys.argv:
    override = 1

try:
    index_main = index_folder("/mnt")
except OSError:
    index_main = {}
    override = 1
index_errors = {"errors": ["json_error.svg", "no_drive.svg", "no_pics.svg", "new_drive.svg"]}
if ((index_main["size"] == 0) and (override is None)):
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

log(str(override))
log(str(sys.argv))
if override == 3: # need to set up drive
    log("FORKED!")
    pid = os.fork()
    """ from here, the CHILD needs to be the UI. The parent should set up the drive,
    and once done, kill the child, recurse, then exit."""
    if pid != 0:
        set_procname("ppf-setup")
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
        sys.exit()
if override == 2: # drive is set up but nothing in Index
    log("FORKED!")
    pid = os.fork()
    """ from here, the CHILD needs to be the UI. The parent should watch for images.
    Once images are found, it should kill the child, recurse, then exit."""
    if pid != 0:
        while True:
            index_main = index_folder("/mnt")
            if index_main["size"] != 0:
                break
            time.sleep(3)
        os.kill(pid, 9)
        subprocess.Popen([sys.argv[0]])
        sys.exit()
# hide the cursor so it doesn't show over the images
if "--testing" not in sys.argv:
    try:
        subprocess.Popen(["xbanish", "-a"])
    except subprocess.CalledProcessError:
        log("xbanish has encountered an error and could not be run.")
    except FileNotFoundError:
        log("xbanish not installed. Please install it to hide the cursor when images are displayed.")

# add a short delay so that the parent process can get the drive mounted
time.sleep(3)
for each in psutil.process_iter():
    if each.name() == "ppf-main":
        log("Process found!")
        sys.exit()
set_procname("ppf-main")
show_window(index_errors, index_main, override)
