#!/bin/bash
# -*- coding: utf-8 -*-
#
#  uninstall.sh
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
sudo rm -rfv /etc/pypicframe
sudo rm -rfv /usr/local/bin/pypicframe
sudo rm -rfv /etc/xdg/autostart/pypicframe.desktop
g=$(groups | sed 's/mount //g')
sudo usermod -G $g $(whoami)
sudo groupdel mount
