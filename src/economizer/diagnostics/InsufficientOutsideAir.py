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

import logging

from datetime import timedelta as td

from volttron.utils import setup_logging
from volttron.utils.math_utils import mean

from economizer import constants

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s   %(levelname)-8s %(message)s",
                    datefmt="%m-%d-%y %H:%M:%S")


class InsufficientOutsideAir(object):
    """
    Air-side HVAC ventilation diagnostic.
    ExcessOutside Air uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing excess outdoor air.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        self.max_dx_time = None
        self.analysis_name = ""
        self.results_publish = None

        # Application thresholds (Configurable)
        self.data_window = None
        self.no_required_data = None
        self.ventilation_oaf_threshold = None
        self.desired_oaf = None
        self.invalid_oaf_dict = None
        self.inconsistent_date = None
        self.insufficient_data = None

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, desired_oaf):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        desired_oaf: float

        No return
        """
        self.results_publish = results_publish
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2

        # Application thresholds (Configurable)
        self.data_window = data_window
        self.analysis_name = analysis_name
        self.no_required_data = no_required_data
        self.ventilation_oaf_threshold = {
            "low": desired_oaf*0.75,
            "normal": desired_oaf*0.5,
            "high": desired_oaf*0.25
        }
        self.desired_oaf = desired_oaf
        self.invalid_oaf_dict = {key: 41.2 for key in self.ventilation_oaf_threshold}
        self.inconsistent_date = {key: 44.2 for key in self.ventilation_oaf_threshold}
        self.insufficient_data = {key: 42.2 for key in self.ventilation_oaf_threshold}

    def run_diagnostic(self, current_time):
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)

        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                        constants.ECON5 + constants.DX + ":" + str(self.inconsistent_date))))
                self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1],
                                                                           (constants.ECON5 + constants.DX),
                                                                           self.inconsistent_date))
                self.clear_data()
                return
            self.insufficient_oa()
        else:
            self.results_publish.append(constants.table_publish_format(self.analysis_name, current_time,
                                                                       (constants.ECON5 + constants.DX),
                                                                       self.insufficient_data))
            self.clear_data()

    def insufficient_outside_air_algorithm(self, oatemp, ratemp, matemp, cur_time):
        """Perform the insufficient outside air class algorithm
        oatemp: float
        ratemp: float
        matemp: float
        cur_time: datetime time delta

        No return
        """
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.timestamp.append(cur_time)

    def insufficient_oa(self):
        """If the detected problems(s) are consistent then generate a fault message(s).
        No return
        """
        oaf = [(mat - rat) / (oat - rat) for oat, rat, mat in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = mean(oaf) * 100.0
        diagnostic_msg = {}

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ("{}: Inconclusive result, the OAF calculation led to an "
                   "unexpected value: {}".format(constants.ECON5, avg_oaf))
            _log.info(msg)
            _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                        constants.ECON5 + constants.DX + ":" + str(self.invalid_oaf_dict))))
            self.results_publish.append(
                constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON5 + constants.DX), self.invalid_oaf_dict))
            self.clear_data()
            return

        avg_oaf = max(0.0, min(100.0, avg_oaf))
        for sensitivity, threshold in self.ventilation_oaf_threshold.items():
            if self.desired_oaf - avg_oaf > threshold:
                msg = "{}: Insufficient OA is being provided for ventilation - sensitivity: {}".format(constants.ECON5, sensitivity)
                result = 43.1
            else:
                msg = "{}: The calculated OAF was within acceptable limits - sensitivity: {}".format(constants.ECON5, sensitivity)
                result = 40.0
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                    constants.ECON5 + constants.DX + ":" + str(diagnostic_msg))))
        self.results_publish.append(
            constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON5 + constants.DX), diagnostic_msg))

        self.clear_data()

    def clear_data(self):
        """
        Reinitialize data arrays.

        No return
        """
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return
