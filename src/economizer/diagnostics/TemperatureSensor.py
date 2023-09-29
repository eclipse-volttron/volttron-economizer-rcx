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


class TemperatureSensor(object):
    """
    Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.
    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []

        self.temp_sensor_problem = None
        self.max_dx_time = None
        self.analysis_name = ""
        self.results_publish = None

        # Application thresholds (Configurable)
        self.data_window = None
        self.no_required_data = None
        self.temp_diff_thr = None
        self.inconsistent_date = None
        self.insufficient_data = None
        self.sensor_damper_dx = DamperSensorInconsistency()

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, temp_diff_thr, open_damper_time, temp_damper_threshold):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        temp_diff_thr: float
        open_damper_time: float
        open_damper_threshold: float

        No return
        """
        self.results_publish = results_publish
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.data_window = data_window
        self.analysis_name = analysis_name
        self.no_required_data = no_required_data
        oat_mat_check = {
            "low": max(temp_diff_thr * 1.5, 6.0),
            "normal": max(temp_diff_thr * 1.25, 5.0),
            "high": max(temp_diff_thr, 4.0)
        }
        self.temp_diff_thr = {
            "low": temp_diff_thr + 2.0,
            "normal": temp_diff_thr,
            "high": max(1.0, temp_diff_thr - 2.0)
        }
        self.inconsistent_date = {key: 3.2 for key in self.temp_diff_thr}
        self.insufficient_data = {key: 2.2 for key in self.temp_diff_thr}
        self.sensor_damper_dx.set_class_values(analysis_name, results_publish, data_window, no_required_data, open_damper_time, oat_mat_check, temp_damper_threshold)

    def run_diagnostic(self, current_time):
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)
        _log.info("Elapsed time: {} -- required time: {}".format(elapsed_time, self.data_window))
        result = self.sensor_damper_dx.run_diagnostic()

        if len(self.timestamp) >= self.no_required_data and not result:
            _log.debug("Temperature Run -- no data: {} -- damper: {}".format(len(self.timestamp), result))
            if elapsed_time > self.max_dx_time:
                _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                        constants.ECON1 + constants.DX + ":" + str(self.inconsistent_date))))
                self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1],
                                                                           (constants.ECON1 + constants.DX),
                                                                           self.inconsistent_date))
                self.clear_data()
                return
            self.temperature_sensor_dx()
        elif len(self.timestamp) < self.no_required_data:
            self.results_publish.append(constants.table_publish_format(self.analysis_name, current_time,
                                                                       (constants.ECON1 + constants.DX),
                                                                       self.insufficient_data))
            self.clear_data()
        else:
            _log.debug("Temperature sensor else!")
            self.clear_data()

    def temperature_algorithm(self, oat, rat, mat, oad, cur_time):
        """Perform the temperature sensor class algorithm
        oat: float
        rat: float
        mat: float
        oad: float
        cur_time: datetime time delta

        return bool
        """
        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.timestamp.append(cur_time)

        if self.temp_sensor_problem:
            return self.temp_sensor_problem
        else:
            self.sensor_damper_dx.damper_algorithm(oat, mat, oad, cur_time)
            return self.temp_sensor_problem

    def temperature_sensor_dx(self):
        """Temperature sensor diagnostic.
        No return
        """
        avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra = self.aggregate_data()
        diagnostic_msg = {}
        for sensitivity, threshold in self.temp_diff_thr.items():
            if avg_oa_ma > threshold and avg_ra_ma > threshold:
                msg = ("{}: MAT is less than OAT and RAT - Sensitivity: {}".format(constants.ECON1, sensitivity))
                result = 1.1
            elif avg_ma_oa > threshold and avg_ma_ra > threshold:
                msg = ("{}: MAT is greater than OAT and RAT - Sensitivity: {}".format(constants.ECON1, sensitivity))
                result = 2.1
            else:
                msg = "{}: No problems were detected - Sensitivity: {}".format(constants.ECON1, sensitivity)
                result = 0.0
                self.temp_sensor_problem = False
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})

        if diagnostic_msg["normal"] > 0.0:
            self.temp_sensor_problem = True
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                    constants.ECON1 + constants.DX + ":" + str(diagnostic_msg))))
        self.results_publish.append(
            constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON1 + constants.DX), diagnostic_msg))
        self.clear_data()

    def aggregate_data(self):
        """ Calculate averages used for calculations within the class.  Needs oat, mat,rat values set in class
        return
        avg_oa_ma: float
        avg_ra_ma: float
        avg_ma_oa: float
        avg_ma_ra: float
        """
        oa_ma = [(x - y) for x, y in zip(self.oat_values, self.mat_values)]
        ra_ma = [(x - y) for x, y in zip(self.rat_values, self.mat_values)]
        ma_oa = [(y - x) for x, y in zip(self.oat_values, self.mat_values)]
        ma_ra = [(y - x) for x, y in zip(self.rat_values, self.mat_values)]
        avg_oa_ma = mean(oa_ma)
        avg_ra_ma = mean(ra_ma)
        avg_ma_oa = mean(ma_oa)
        avg_ma_ra = mean(ma_ra)
        return avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra

    def clear_data(self):
        """
        Reinitialize data arrays.

        No return
        """
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        if self.temp_sensor_problem:
            self.temp_sensor_problem = None


class DamperSensorInconsistency(object):
    """
    Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.
    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.mat_values = []
        self.timestamp = []
        self.steady_state = None
        self.econ_time_check = None
        self.data_window = None
        self.no_required_data = None
        self.oad_temperature_threshold = None
        self.oat_mat_check = None
        self.analysis_name = ""
        self.results_publish = None

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, open_damper_time, oat_mat_check, temp_damper_threshold):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        open_damper_time: float
        oat_mat_check: dictionary with "low": float, "normal": float, "high": float
        temp_damper_threshold: float

        No return
        """
        self.results_publish = results_publish
        self.econ_time_check = open_damper_time
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.oad_temperature_threshold = temp_damper_threshold
        self.oat_mat_check = oat_mat_check
        self.analysis_name = analysis_name

    def run_diagnostic(self):
        msg = ""
        if len(self.oat_values) > self.no_required_data:
            mat_oat_diff_list = [abs(x - y) for x, y in zip(self.oat_values, self.mat_values)]
            open_damper_check = mean(mat_oat_diff_list)
            diagnostic_msg = {}
            for sensitivity, threshold in self.oat_mat_check.items():
                if open_damper_check > threshold:
                    msg = "{} - {}: OAT and MAT are inconsistent when OAD is near 100%".format(constants.ECON1,
                                                                                               str(sensitivity))
                    result = 0.1
                else:
                    msg = "{} - {}: OAT and MAT are consistent when OAD is near 100%".format(constants.ECON1,
                                                                                             str(sensitivity))
                    result = 0.0
                diagnostic_msg.update({sensitivity: result})

            _log.info(msg)
            _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1],
                                                 (constants.ECON1 + constants.DX + ":" + str(diagnostic_msg))))
            self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1],
                                                                       (constants.ECON1 + constants.DX),
                                                                       diagnostic_msg))
            self.clear_data()
            return True
        else:
            self.clear_data()
            return False

    def damper_algorithm(self, oat, mat, oad, cur_time):
        """Perform the damper class algorithm
        oat: float
        mat: float
        oad: float
        cur_time: datetime time delta

        No return
        """
        if oad > self.oad_temperature_threshold:
            if self.steady_state is None:
                self.steady_state = cur_time
            elif cur_time - self.steady_state >= self.econ_time_check:
                self.oat_values.append(oat)
                self.mat_values.append(mat)
                self.timestamp.append(cur_time)
        else:
            self.steady_state = None

    def clear_data(self):
        """
        Reinitialize data arrays.

        No return
        """
        self.oat_values = []
        self.mat_values = []
        self.steady_state = None
        self.timestamp = []
