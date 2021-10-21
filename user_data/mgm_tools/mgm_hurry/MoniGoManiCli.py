# -*- coding: utf-8 -*-
# -* vim: syntax=python -*-

# --- ↑↓ Do not remove these libs ↑↓ -----------------------------------------------------------------------------------

"""MoniGoManiCli is the responsible module to communicate with the mgm strategy."""

# ___  ___               _  _____        ___  ___               _  _____  _  _
# |  \/  |              (_)|  __ \       |  \/  |              (_)/  __ \| |(_)
# | .  . |  ___   _ __   _ | |  \/  ___  | .  . |  __ _  _ __   _ | /  \/| | _
# | |\/| | / _ \ | '_ \ | || | __  / _ \ | |\/| | / _` || '_ \ | || |    | || |
# | |  | || (_) || | | || || |_\ \| (_) || |  | || (_| || | | || || \__/\| || |
# \_|  |_/ \___/ |_| |_||_| \____/ \___/ \_|  |_/ \__,_||_| |_||_| \____/|_||_|

import glob
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from math import ceil
from shutil import copy2, copytree

import logger
import pygit2
from pygit2 import Repository, clone_repository
from yaspin import yaspin

from user_data.mgm_tools.mgm_hurry.CliColor import Color
from user_data.mgm_tools.mgm_hurry.MoniGoManiConfig import MoniGoManiConfig
from user_data.mgm_tools.mgm_hurry.MoniGoManiLogger import MoniGoManiLogger, MGMLogger

# ---- ↑ Do not remove these libs ↑ ------------------------------------------------------------------------------------

GIT_URL_MONIGOMANI: str = 'https://github.com/Rikj000/MoniGoMani.git'


class MoniGoManiCli(object):
    """
    Use this module to communicate with the MoniGoMani HyperStrategy.

    Attributes:
        logger              The logger function of the MoniGoManiCli module.
        monigomani_config   The MoniGoManiConfig object.
    """
    logger: MoniGoManiLogger
    monigomani_config: MoniGoManiConfig

    def __init__(self, basedir):
        """
        Let's talk command-line-ish.

        :param basedir (str): The base directory of your Freqtrade & MoniGoMani installation
        """
        self.basedir = basedir
        self.logger = MoniGoManiLogger(self.basedir).get_logger()
        self.monigomani_config = MoniGoManiConfig(self.basedir)

    def installation_exists(self, silent: bool = False) -> bool:
        """
        Check if the MGM Hyper Strategy installation exists.

        :param silent: (bool, Optional) Silently run method (without command line output)
        :return success (bool): Whether or not the config and strategy files are found.
        """
        with yaspin(text='', color='cyan') as sp:

            if self._mgm_config_json_exists() is False:
                mgm_config_name = self.monigomani_config.config['mgm_config_names']['mgm-config']
                if silent is False:
                    sp.yellow.write(f'🤷 No "{mgm_config_name}" file found.')
                    self.logger.warning(Color.yellow(f'🤷 No "{mgm_config_name}" file found.'))
                return False

            if self._mgm_hyperstrategy_file_exists() is False:
                if silent is False:
                    sp.yellow.write('🤷 No "MoniGoManiHyperStrategy.py" file found.')
                    self.logger.warning(Color.yellow('🤷 No "MoniGoManiHyperStrategy.py" file found.'))
                return False

            if silent is False:
                sp.green.ok('✔ MoniGoManiHyperStrategy and configuration found')

        if silent is False:
            self.logger.debug(Color.green('MoniGoManiHyperStrategy and configuration found √'))

        return True

    def _mgm_config_json_exists(self) -> bool:
        """
        Checks if `mgm-config` exists

        :return bool: Returns true if `mgm-config` exists, returns false if not.
        """
        mgm_config_name = self.monigomani_config.config['mgm_config_names']['mgm-config']
        return os.path.exists(f'{self.basedir}/user_data/{mgm_config_name}')

    def _mgm_hyperstrategy_file_exists(self) -> bool:
        """
        Checks if `MoniGoManiHyperStrategy.py` exists

        :return bool: Returns true if `MoniGoManiHyperStrategy.py` exists, returns false if not.
        """
        return os.path.exists(f'{self.basedir}/user_data/strategies/MoniGoManiHyperStrategy.py')

    def download_setup_mgm(self, target_dir: str = None, branch: str = 'develop', commit: str = None):
        """
        Install MoniGoMani using a git clone to target_dir.

        :param target_dir: (str) Specify a target_dir to install MoniGoMani. Defaults to 'os.getcwd()'.
        :param branch: (str) Checkout a specific branch. Defaults to 'develop'.
        :param commit: (str) Checkout a specific commit. Defaults to None aka 'latest'.
        """
        with tempfile.TemporaryDirectory() as temp_dirname:
            if target_dir is None:
                target_dir = os.getcwd()

            text = '👉  Clone MoniGoMani repository'
            if (commit == 'latest') or (commit is None):
                text = f'{text} on the latest commit'
            else:
                text = f'{text} and resetting to commit {commit}'
            with yaspin(text=text, color='cyan') as sp:
                repo = clone_repository(GIT_URL_MONIGOMANI, temp_dirname, checkout_branch=branch)
                if (commit is not None) and (commit != 'latest'):
                    repo.reset(commit, pygit2.GIT_RESET_HARD)

                if not isinstance(repo, Repository):
                    sp.red.write('Failed to download MoniGoMani repo. I quit!')
                    self.logger.critical(Color.red('Failed to clone MoniGoMani repo. I quit!'))
                    sys.exit(1)

                sp.green.ok('✔')

            with yaspin(text='👉  Copy MoniGoMani to the monigomani folder in the target directory and '
                             'symbolic linking files', color='cyan') as sp:
                try:
                    if self.copy_and_link_installation_files(temp_dirname, target_dir):
                        sp.green.ok('✔ Copy & linking MoniGoMani installation files completed!')
                    else:
                        sp.red.write('😕 MoniGoMani installation failed')
                        sys.exit(1)
                except Exception as e:
                    sp.red.write(str(e))
                    sp.red.write('😕 MoniGoMani installation failed')
                    sys.exit(1)

            self.logger.info('👉  Installing/Updating MoniGoMani Python dependency packages')
            self.run_command('pip3 install -r ./monigomani/requirements-mgm.txt')
            self.logger.info(Color.green('✔ Downloading & Installing MoniGoMani completed!'))

    def copy_and_link_installation_files(self, temp_dirname: str, target_dir: str) -> bool:
        """
        Copy the installation files to the target directory and symbolic link them.

        :param temp_dirname: (str) The source directory where installation files exist.
        :param target_dir: (str) The target directory where the installation files should be copied to.
        :return bool: True if copying and symbolic linking was executed successfully, False if failed.
        """
        try:
            mgm_folder = '/monigomani'
            make_directories = [target_dir + mgm_folder, f'{target_dir}/user_data/importance_results',
                                f'{target_dir}/user_data/csv_results']

            for make_dir in make_directories:
                if not os.path.exists(make_dir):
                    os.makedirs(make_dir, exist_ok=True)

            if os.path.isfile(f'{target_dir + mgm_folder}/setup.exp'):
                os.remove(f'{target_dir + mgm_folder}/setup.exp')

            os.chmod(f'{temp_dirname}/setup.exp', 0o444)
            copytree(temp_dirname, target_dir + mgm_folder, dirs_exist_ok=True)

            for delete_file in ['docker-compose.yml', 'user_data/logs/freqtrade.log']:
                if os.path.isfile(f'{target_dir}/{delete_file}'):
                    os.remove(f'{target_dir}/{delete_file}')

            # Symlink separate files and whole directories
            symlink_objects = {
                'Documentation',
                'Some Test Results',
                # 'docker/Dockerfile.MoniGoMani',
                'user_data/logs/freqtrade.log',
                'user_data/mgm_pair_lists',
                'user_data/mgm_tools',
                'user_data/__init__.py',
                # 'docker-compose.yml',
                'mgm-hurry',
                'requirements-mgm.txt'
            }

            for symlink_object in symlink_objects:
                if os.path.islink(f'{target_dir}/{symlink_object}') is False:
                    os.symlink(f'{target_dir + mgm_folder}/{symlink_object}', f'{target_dir}/{symlink_object}')
            if os.path.islink(f'{target_dir}/README-MGM.md') is False:
                os.symlink(f'{target_dir + mgm_folder}/README.md', f'{target_dir}/README-MGM.md')

            # Symlink all files inside the given directories separately
            symlink_directory_contents = {
                'tests',
                'user_data/hyperopts',
                'user_data/strategies'
            }

            for directory in symlink_directory_contents:
                for symlink_object in glob.glob(f'{target_dir + mgm_folder}/{directory}/*'):
                    target_location = symlink_object.replace(mgm_folder, '')
                    if os.path.islink(target_location) is False:
                        os.symlink(symlink_object, target_location)

            return True
        except Exception as e:
            self.logger.critical(str(e))
            return False

    def apply_mgm_results(self, strategy: str = 'MoniGoManiHyperStrategy') -> bool:
        """
        Apply MoniGoMani HyperOpt results to the `mgm-config-hyperopt` file.

        :param strategy: (str) The name of the strategy. Is used to determine ho-results file.
        :return bool: True if ho-results file was successfully applied. False otherwise.
        """
        strategy_ho_json_name = f'{strategy}.json'
        strategy_ho_json_path = f'{self.basedir}/user_data/strategies/{strategy_ho_json_name}'

        if os.path.isfile(strategy_ho_json_path) is False:
            self.logger.error(Color.red(f'🤷 Failed applying best results because the HyperOpt results file '
                                        f'"{strategy_ho_json_name}" does not exist.'))
            return False

        # Apply best results from `MoniGoManiHyperStrategy.json` to `mgm-config-hyperopt`
        if strategy == 'MoniGoManiHyperStrategy':
            mgm_ho_json_name = self.monigomani_config.config['mgm_config_names']['mgm-config-hyperopt']
            mgm_ho_json_path = f'{self.basedir}/user_data/{mgm_ho_json_name}'

            copy2(strategy_ho_json_path, mgm_ho_json_path)
            # Cleanup leftover file `MoniGoManiHyperStrategy.json`
            os.remove(strategy_ho_json_path)
        else:
            self.logger.debug(f'Freqtrade already automatically applied the results '
                              f'for {strategy} at {strategy_ho_json_path}, all good!')

        return True

    def run_command(self, command: str, output_file_name: str = None,
                    hyperopt: bool = False, backtest: bool = False) -> any:
        """
        Execute shell command and log output to mgm logfile if a path + filename is provided.

        :param command: (str) Shell command to execute, sir!
        :param output_file_name: (str, Optional) Name of the absolute path to the '.log' file.
        :param hyperopt: (bool, Optional): Must be True if HyperOpt command provided, defaults to false.
        :param backtest: (bool, Optional): Must be True if BackTest command provided, defaults to false.
        :return returncode: (Any) The returncode of the subprocess, HyperOpt results table or BackTest sell reasons
        """

        if command is None or command == '':
            self.logger.error(Color.red('🤷 Please pass a command through. Without command no objective, sir!'))
            sys.exit(1)
        return_code = 1

        if output_file_name is not None:
            output_file = open(output_file_name, 'w')
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, encoding='utf-8')

        hyperopt_results = []
        backtest_sell_reasons = []
        mgm_logger = MGMLogger(logger.logger)
        monigomani_logger = MoniGoManiLogger(self.basedir)
        elapsed_time = 'Elapsed Time:'
        eta = '| [ETA:'
        break_output = False
        storing_sell_reasons = False

        for line in process.stdout:
            final_line = mgm_logger.clean_line(line)

            if (hyperopt is True) and (final_line.count('# Buy hyperspace params:') > 0):
                break_output = True

            if backtest is True:
                if final_line.count('= SELL REASON STATS =') > 0:
                    storing_sell_reasons = True
                elif final_line.count('= LEFT OPEN TRADES REPORT =') > 0:
                    storing_sell_reasons = False
                if storing_sell_reasons is True:
                    backtest_sell_reasons.append(final_line)

            if break_output is False:
                # Save the output to a '.log' file if enabled
                if (mgm_logger.filter_line(final_line) is False) and (output_file_name
                                                                      is not None) and (eta not in final_line):
                    output_file.write(final_line)

                # Check if a new HyperOpt Results line is found,
                # store it in RAM and re-print the whole HyperOpt Table if so
                response = monigomani_logger.store_hyperopt_results(hyperopt_results, final_line)
                if (hyperopt is True) and ((response['results_updated'] is True) or
                                           (eta not in final_line) and (elapsed_time in final_line)):
                    hyperopt_results = response['hyperopt_results']
                    # Skip the initial header
                    if len(hyperopt_results) > 3:
                        for hyperopt_results_line in hyperopt_results:
                            sys.stdout.write(Color.green(hyperopt_results_line))
                    if (eta not in final_line) and (elapsed_time in final_line):
                        sys.stdout.write(final_line)
                else:
                    if final_line.count('ERROR') > 0:
                        sys.stdout.write(Color.red(final_line))
                    elif final_line.count('WARNING') > 0:
                        sys.stdout.write(Color.yellow(final_line))
                    else:
                        sys.stdout.write(final_line)

        process.wait()

        for log_file in glob.glob(f'{self.basedir}/user_data/logs/MGM-Hurry-Command-*.log'):
            if os.stat(log_file).st_size == 0:
                os.remove(log_file)

        if hyperopt is True:
            last_ho_results_path = f'{self.basedir}/user_data/hyperopt_results/.last_ho_results_table.log'
            if os.path.isfile(last_ho_results_path):
                os.remove(last_ho_results_path)
            last_ho_results_file = open(last_ho_results_path, 'w')
            if len(hyperopt_results) > 3:
                for ho_result in hyperopt_results:
                    last_ho_results_file.write(ho_result)
            last_ho_results_file.close()

        elif backtest is True:
            last_sell_reasons_path = f'{self.basedir}/user_data/backtest_results/.last_backtest_sell_reasons.log'
            if os.path.isfile(last_sell_reasons_path):
                os.remove(last_sell_reasons_path)
            last_sell_reasons_file = open(last_sell_reasons_path, 'w')
            if len(backtest_sell_reasons) > 1:
                for backtest_sell_reason in backtest_sell_reasons:
                    last_sell_reasons_file.write(backtest_sell_reason)
            last_sell_reasons_file.close()

        return return_code

    def calculate_timerange_start_minus_startup_candle_count(self, timerange: int = None) -> dict:
        """
        Calculate the amount of days to add to the timerange based on the startup candle count
        & timeframes (candle sizes) used

        Subtracts the startup_candle_count from the provided timerange, defaults to timerange defined in '.hurry'

        :param timerange: (str, Optional) Timerange for which to subtract candle data timerange, defaults to
        :return dict: Dictionary object containing the new timerange and the new start date:
            eg: {'new_timerange': str, 'new_start_date': datetime}
        """

        # Load the config files & timeframes used
        mgm_config_files = self.monigomani_config.load_config_files()
        timeframe_list = self.get_timeframe_list()

        # Calculate the largest timeframe size in minutes_to_timeframe
        largest_timeframe_minutes = 0
        for timeframe in timeframe_list:
            timeframe_minutes = self.timeframe_to_minutes(timeframe)
            if timeframe_minutes > largest_timeframe_minutes:
                largest_timeframe_minutes = timeframe_minutes

        # Calculate the amount of extra_days of candle data to download
        startup_candle_count = mgm_config_files['mgm-config']['monigomani_settings']['startup_candle_count']
        extra_days = ceil((largest_timeframe_minutes * startup_candle_count) / (60 * 24))

        # Load the timerange from '.hurry' if none was provided
        if timerange is not None:
            split_timerange = timerange.split('-')
        else:
            split_timerange = self.monigomani_config.config['timerange'].split('-')

        # Calculate the new start date
        new_start_date = datetime.strptime(split_timerange[0], '%Y%m%d') - timedelta(extra_days)

        # Parse the new timerange & return
        if len(split_timerange) > 1:
            timerange = f'{new_start_date.strftime("%Y%m%d")}-{split_timerange[1]}'
        else:
            timerange = f'{new_start_date.strftime("%Y%m%d")}-'

        self.logger.info(f'👉 Added {extra_days} extra days to the timerange for the "startup_candle_count"')
        return {'new_timerange': timerange, 'new_start_date': new_start_date}

    @staticmethod
    def timeframe_to_minutes(timeframe):
        amount = int(timeframe[0:-1])
        unit = timeframe[-1]
        if 'y' == unit:
            scale = 60 * 60 * 24 * 365
        elif 'M' == unit:
            scale = 60 * 60 * 24 * 30
        elif 'w' == unit:
            scale = 60 * 60 * 24 * 7
        elif 'd' == unit:
            scale = 60 * 60 * 24
        elif 'h' == unit:
            scale = 60 * 60
        elif 'm' == unit:
            scale = 60
        elif 's' == unit:
            scale = 1
        else:
            raise TypeError(f'MoniGoManiCli - ERROR - timeframe unit {unit} is not supported')
        return (amount * scale) // 60

    @staticmethod
    def minutes_to_timeframe(minutes: int) -> str:
        """
        Calculates the corresponding timeframe for the amount of minutes provided

        :param minutes: (int) Amount of minutes to parse to the closest candle size
        :return: (str) The parsed timeframe / candle size
        """

        if minutes < 1:
            timeframe_number = 60 * minutes
            timeframe_size = 's'  # Return seconds
        elif minutes < 60:
            timeframe_number = minutes
            timeframe_size = 'm'  # Return minutes
        elif minutes < 1440:
            timeframe_number = minutes / 60
            timeframe_size = 'h'  # Return hours
        elif minutes < 10080:
            timeframe_number = minutes / 1440
            timeframe_size = 'd'  # Return days
        elif minutes < 40320:
            timeframe_number = minutes / 10080
            timeframe_size = 'w'  # Return weeks
        else:
            timeframe_number = minutes / 40320
            timeframe_size = 'M'  # Return months

        if (timeframe_number - int(timeframe_number) == 0) is False:
            sys.exit(f'MoniGoManiCli - ERROR - MoniGoMani could not correctly parse the provided minutes '
                     f'({minutes}m) to a usable timeframe format ({str(round(timeframe_number, 2))}{timeframe_size})!'
                     f'\nPlease adjust the "timeframes" section of your "mgm-config"!')

        return f'{str(int(timeframe_number))}{timeframe_size}'

    def get_timeframe_list(self) -> list[str]:
        """
        Fetches a list of all the timeframes used by MoniGoMani as it's configured in 'mgm-config'
        :return: (list) List of string containing all the timeframes used by MoniGoMani
        """

        # ToDo: Remove doubles from list, perhaps also from framework?

        # Load the MoniGoMani timeframes settings section
        mgm_config_files = self.monigomani_config.load_config_files()
        timeframes_section = mgm_config_files['mgm-config']['monigomani_settings']['timeframes']

        # Build the list of all timeframes used
        timeframe_list = [timeframes_section['base_timeframe'], timeframes_section['roi_timeframe']]
        for weighted_signal_timeframe in timeframes_section['weighted_signal_timeframes']:
            timeframe_list.append(weighted_signal_timeframe)

            # Calculate the core_trend_timeframes used
            core_trend_timeframe = self.minutes_to_timeframe(
                minutes=(self.timeframe_to_minutes(weighted_signal_timeframe)
                         * timeframes_section['core_trend_timeframe_multiplier']))
            timeframe_list.append(core_trend_timeframe)

        return timeframe_list

    def get_default_timeframe_options(self) -> list[dict]:
        """
        Returns a list of dictionaries with selectable timeframe data.
        It will automatically toggle on the timeframes used by MoniGoMani.

        :return: (list[dict]) Returns a list with timeframe prompt options
        """
        timeframe_list = self.get_timeframe_list()
        timeframe_options = [
            {'name': '1m', 'value': '1m', 'enabled': False},
            {'name': '3m', 'value': '3m', 'enabled': False},
            {'name': '5m', 'value': '5m', 'enabled': False},
            {'name': '15m', 'value': '15m', 'enabled': False},
            {'name': '30m', 'value': '30m', 'enabled': False},
            {'name': '1h', 'value': '1h', 'enabled': False},
            {'name': '2h', 'value': '2h', 'enabled': False},
            {'name': '4h', 'value': '4h', 'enabled': False},
            {'name': '6h', 'value': '6h', 'enabled': False},
            {'name': '8h', 'value': '8h', 'enabled': False},
            {'name': '12h', 'value': '12h', 'enabled': False},
            {'name': '1d', 'value': '1d', 'enabled': False},
            {'name': '3d', 'value': '3d', 'enabled': False},
            {'name': '1w', 'value': '1w', 'enabled': False},
            {'name': '2w', 'value': '2w', 'enabled': False},
            {'name': '1M', 'value': '1M', 'enabled': False},
            {'name': '1y', 'value': '1y', 'enabled': False}
        ]

        for timeframe in timeframe_list:
            timeframe_usable = False
            timeframe_option_index = 0

            for timeframe_option in timeframe_options[:]:
                if timeframe == timeframe_option['value']:
                    timeframe_options[timeframe_option_index]['enabled'] = True
                    timeframe_usable = True
                    break
                timeframe_option_index += 1

            if timeframe_usable is False:
                self.logger.warning(Color.yellow(f'🤷 The configured timeframe ({timeframe}) is not usable by Freqtrade!'
                                                 f'\nPlease adjust the "timeframes" section of your "mgm-config"!'))

        return timeframe_options
