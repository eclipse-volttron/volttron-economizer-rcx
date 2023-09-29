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


class EconCorrectlyOff(object):
    """
    Air-side HVAC economizer diagnostic for AHU/RTU systems.
    EconCorrectlyOff uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should not.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.oad_values = []
        self.timestamp = []
        self.econ_timestamp = []
        self.analysis_name = ""

        # Initialize not_cooling and not_economizing flags
        self.economizing = []

        self.max_dx_time = None
        self.data_window = None
        self.no_required_data = None
        self.min_damper_sp = None
        self.excess_damper_threshold = None
        self.economizing_dict = None
        self.inconsistent_date = None
        self.desired_oaf = None
        self.analysis = None
        self.cfm = None
        self.eer = None
        self.results_publish = None
        self.insufficient_data = None

        # Application result messages
        self.alg_result_messages = [
            "The OAD should be at the minimum position but is significantly above this value.",
             "No problems detected.",
             "Inconclusive results, could not verify the status of the economizer."]

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, minimum_damper_setpoint, desired_oaf, cfm, eer):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        minimum_damper_setpoint: float
        desired_oaf: float
        cfm: float
        eer: float

        No return
        """
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.results_publish = results_publish
        self.data_window = data_window
        self.analysis_name = analysis_name
        self.no_required_data = no_required_data
        self.min_damper_sp = minimum_damper_setpoint
        self.excess_damper_threshold = {
            "low": minimum_damper_setpoint*2.0,
            "normal": minimum_damper_setpoint,
            "high":  minimum_damper_setpoint*0.5
        }
        self.economizing_dict = {key: 25.0 for key in self.excess_damper_threshold}
        self.inconsistent_date = {key: 23.2 for key in self.excess_damper_threshold}
        self.insufficient_data = {key: 22.2 for key in self.excess_damper_threshold}
        self.desired_oaf = desired_oaf
        self.cfm = cfm
        self.eer = eer

    def run_diagnostic(self, current_time):

        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)
        if self.economizer_conditions(current_time):
            return
        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                        constants.ECON3 + constants.DX + ":" + str(self.inconsistent_date))))
                self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1],
                                                                           (constants.ECON3 + constants.DX),
                                                                           self.inconsistent_date))
                self.clear_data()
                return
            self.economizing_when_not_needed()
        else:
            self.results_publish.append(constants.table_publish_format(self.analysis_name, current_time,
                                                                       (constants.ECON3 + constants.DX),
                                                                       self.insufficient_data))
            self.clear_data()

    def economizer_off_algorithm(self, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """Perform the Econ Correctly Off class algorithm
        oat: float
        rat: float
        mat: float
        oad: float
        econ_condition: float
        cur_time: datetime time delta
        fan_sp: float

        No return
        """

        economizing = self.economizing_check(econ_condition, cur_time)
        self.econ_timestamp.append(cur_time)
        if economizing:
            return

        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.oad_values.append(oad)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

    def economizer_conditions(self, current_time):
        if len(self.economizing) >= len(self.econ_timestamp)*0.5:
            _log.info(constants.table_log_format(self.analysis_name, current_time,
                                                 (constants.ECON3 + constants.DX + ":" + str(self.economizing_dict))))
            self.results_publish.append(
                constants.table_publish_format(self.analysis_name,
                                               current_time,
                                               (constants.ECON3 + constants.DX),
                                               self.economizing_dict))
            self.clear_data()
            return True
        return False

    def economizing_check(self, econ_condition, cur_time):
        """ Check conditions to see if should be economizing
        econ_conditions: float
        cur_time: datetime time delta
        returns boolean
        """
        if econ_condition:
            _log.info("{}: economizing, for data {} --{}.".format(constants.ECON3, econ_condition, cur_time))
            self.economizing.append(cur_time)
            return True
        return False

    def economizing_when_not_needed(self):
        """If the detected problems(s) are consistent then generate a fault message(s).
        No return
        """
        desired_oaf = self.desired_oaf / 100.0
        avg_damper = mean(self.oad_values)
        diagnostic_msg = {}
        energy_impact = {}
        for sensitivity, threshold in self.excess_damper_threshold.items():
            if avg_damper > threshold:
                msg = "{} - {}: {}".format(constants.ECON3, sensitivity, self.alg_result_messages[0])
                # color_code = "RED"
                result = 21.1
                energy = self.energy_impact_calculation(desired_oaf)
            else:
                msg = "{} - {}: {}".format(constants.ECON3, sensitivity, self.alg_result_messages[1])
                # color_code = "GREEN"
                result = 20.0
                energy = 0.0
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})
            energy_impact.update({sensitivity: energy})
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                    constants.ECON3 + constants.DX + ":" + str(diagnostic_msg))))
        self.results_publish.append(
            constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON3 + constants.DX), diagnostic_msg))
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                    constants.ECON3 + constants.EI + ":" + str(energy_impact))))
        self.results_publish.append(
            constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON3 + constants.EI), energy_impact))
        self.clear_data()

    def energy_impact_calculation(self, desired_oaf):
        """ Calculate the impact the temperature values have
        desired_oaf: float

        returns float
        """
        ei = 0.0
        energy_calc = [
            (1.08 * spd * self.cfm * (mat - (oat * desired_oaf + (rat * (1.0 - desired_oaf))))) / (1000.0 * self.eer)
            for mat, oat, rat, spd in zip(self.mat_values, self.oat_values, self.rat_values, self.fan_spd_values)
            if (mat - (oat * desired_oaf + (rat * (1.0 - desired_oaf)))) > 0
        ]
        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            ei = round(ei, 2)
        return ei

    def clear_data(self):
        """
        Reinitialize data arrays.

        No return
        """
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.econ_timestamp = []
        self.economizing = []


