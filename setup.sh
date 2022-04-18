#!/bin/bash
# -*- coding: utf-8 -*-
#
#  setup.sh
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
sudo groupadd mount
sudo usermod -aG mount $(whoami)
sudo mkdir /etc/pypicframe
sudo ln -s "$PWD/internal_settings.json" /ets/pypicframe/internal_settings.json
sudo ln -s "$PWD/system_config/sudoers" /etc/sudoers.d/pypicframe
sudo ln -s "$PWD/pypicframe.py" /usr/local/bin/pypicframe
sudo ln -s "$PWD/system_config/xsession.desktop" /usr/share/xsessions/pypicframe.desktop
