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


class ExcessOutsideAir(object):
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
        self.oad_values = []
        self.timestamp = []
        self.econ_timestamp = []
        self.fan_spd_values = []
        self.economizing = []
        self.analysis_name = ""
        self.results_publish = None

        # Application thresholds (Configurable)
        self.cfm = None
        self.eer = None
        self.max_dx_time = None
        self.data_window = None
        self.no_required_data = None
        self.excess_oaf_threshold = None
        self.min_damper_sp = None
        self.desired_oaf = None
        self.excess_damper_threshold = None
        self.economizing_dict = None
        self.invalid_oaf_dict = None
        self.inconsistent_date = None
        self.nsufficient_data = None

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, min_damper_sp, desired_oaf, cfm, eer):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        min_damper_sp: float
        desired_oaf: float
        cfm: float
        eer: float

        No return
        """
        self.results_publish = results_publish
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.data_window = data_window
        self.analysis_name = analysis_name
        self.no_required_data = no_required_data
        self.excess_oaf_threshold = {
            "low": min_damper_sp*2.0 + 10.0,
            "normal": min_damper_sp + 10.0,
            "high": min_damper_sp*0.5 + 10.0
        }
        self.min_damper_sp = min_damper_sp
        self.desired_oaf = desired_oaf
        self.excess_damper_threshold = {
            "low": min_damper_sp*2.0,
            "normal": min_damper_sp,
            "high":  min_damper_sp*0.5
        }
        self.economizing_dict = {key: 36.0 for key in self.excess_damper_threshold}
        self.invalid_oaf_dict = {key: 31.2 for key in self.excess_damper_threshold}
        self.insufficient_data = {key: 32.2 for key in self.excess_damper_threshold}
        self.inconsistent_date = {key: 35.2 for key in self.excess_damper_threshold}

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
                                                                           (constants.ECON4 + constants.DX),
                                                                           self.inconsistent_date))
                self.clear_data()
                return
            self.excess_oa()
        else:
            self.results_publish.append(constants.table_publish_format(self.analysis_name, current_time,
                                                                       (constants.ECON4 + constants.DX),
                                                                       self.insufficient_data))
            self.clear_data()

    def excess_ouside_air_algorithm(self, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """Perform the excess outside air class algorithm
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

        self.oad_values.append(oad)
        self.oat_values.append(oat)
        self.rat_values.append(rat)
        self.mat_values.append(mat)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

    def economizer_conditions(self, current_time):
        if len(self.economizing) >= len(self.econ_timestamp) * 0.5:
            _log.info(constants.table_log_format(self.analysis_name, current_time,
                                                 (constants.ECON4 + constants.DX + ":" + str(self.economizing_dict))))
            self.results_publish.append(
                constants.table_publish_format(self.analysis_name,
                                               current_time,
                                               (constants.ECON4 + constants.DX),
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

    def excess_oa(self):
        """If the detected problems(s) are consistent then generate a fault message(s).
        No return
        """
        energy = 0.0
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = mean(oaf) * 100.0
        avg_damper = mean(self.oad_values)
        desired_oaf = self.desired_oaf / 100.0
        diagnostic_msg = {}
        energy_impact = {}

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ("{}: Inconclusive result, unexpected OAF value: {}".format(constants.ECON4, avg_oaf))
            _log.info(msg)
            _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                        constants.ECON4 + constants.DX + ":" + str(self.invalid_oaf_dict))))
            self.results_publish.append(
                constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.DX), self.invalid_oaf_dict))
            self.clear_data()
            return

        avg_oaf = max(0.0, min(100.0, avg_oaf))
        thresholds = zip(self.excess_damper_threshold.items(), self.excess_oaf_threshold.items())
        for (key, damper_thr), (key2, oaf_thr) in thresholds:
            if avg_damper > damper_thr:
                msg = "{}: The OAD should be at the minimum but is significantly higher.".format(constants.ECON4)
                # color_code = "RED"
                result = 32.1
                if avg_oaf - self.desired_oaf > oaf_thr:
                    msg = ("{}: The OAD should be at the minimum for ventilation "
                           "but is significantly above that value. Excess outdoor air is "
                           "being provided; This could significantly increase "
                           "heating and cooling costs".format(constants.ECON4))
                    energy = self.energy_impact_calculation(desired_oaf)
                    result = 34.1
            elif avg_oaf - self.desired_oaf > oaf_thr:
                msg = ("{}: Excess outdoor air is being provided, this could "
                       "increase heating and cooling energy consumption.".format(constants.ECON4))
                # color_code = "RED"
                energy = self.energy_impact_calculation(desired_oaf)
                result = 33.1
            else:
                # color_code = "GREEN"
                msg = ("{}: The calculated OAF is within configured limits.".format(constants.ECON4))
                result = 30.0
                energy = 0.0

            _log.info(msg)
            energy_impact.update({key: energy})
            diagnostic_msg.update({key: result})
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                    constants.ECON4 + constants.DX + ":" + str(diagnostic_msg))))
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                    constants.ECON4 + constants.EI + ":" + str(energy_impact))))
        self.results_publish.append(
            constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.DX), diagnostic_msg))
        self.results_publish.append(
            constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.EI), energy_impact))
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
