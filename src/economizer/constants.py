# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Installable Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2022 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

from volttron.utils.jsonapi import dumps

ECON1 = "Temperature Sensor Dx"
ECON2 = "Not Economizing When Unit Should Dx"
ECON3 = "Economizing When Unit Should Not Dx"
ECON4 = "Excess Outdoor-air Intake Dx"
ECON5 = "Insufficient Outdoor-air Intake Dx"
DX = "/diagnostic message"
EI = "/energy impact"

DX_LIST = [ECON1, ECON2, ECON3, ECON4, ECON5]

FAN_OFF = -99.3
OAF = -89.2
OAT_LIMIT = -79.2
RAT_LIMIT = -69.2
MAT_LIMIT = -59.2
TEMP_SENSOR = -49.2


def table_log_format(name, timestamp, data):
    """ Return a formatted string for use in the log"""
    return str(str(name) + "&" + str(timestamp) + "->[" + str(data) + "]")


def table_publish_format(name, timestamp, table, data):
    """ Return a dictionary for use in the results publish"""
    table_key = str(str(name) + "&" + str(timestamp))
    data = dumps(data)
    return [table_key, [table, data]]
