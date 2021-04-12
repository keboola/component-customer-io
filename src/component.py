'''
Template Component main class.

'''

import ast
import logging
import os
import sys
from pathlib import Path

from kbc.env_handler import KBCEnvHandler
from kbc.result import KBCTableDef, ResultWriter

from customer_io import api_service
from customer_io.api_service import CustomerIoClient

# configuration variables
KEY_ATTRIBUTES = 'attributes'
CAMPAIGNS_COLS = ["id", "deduplicate_id", "name",
                  "type", "created", "updated", "active", "state", "actions", "first_started",
                  "created_by", "tags", "frequency", "date_attribute", "timezone",
                  "use_customer_timezone",
                  "start_hour", "start_minutes", "customer_id"]
SINGLE_ACTIVITY_TBL_HEADER = ["id", "customer_id", "type", "timestamp", "data", "delivery_id",
                              "delivery_type"]
KEY_API_SECRET = '#api_secret'
KEY_SITE_ID = 'site_id'

KEY_INCREMENTAL = 'incremental_output'
KEY_CAMPAIGNS = 'campaigns'
KEY_SEGMENTS = 'segments'
KEY_CUSTOMERS = 'customers'
KEY_FILTERS = 'filters'

KEY_ACTIVITIES = 'activities'
KEY_MESSAGES = 'messages'
KEY_ACT_TYPES = 'types'
KEY_ACT_MODE = 'mode'
KEY_ACT_DELETED = 'deleted'

# #### Keep for debug
KEY_DEBUG = 'debug'
MANDATORY_PARS = [KEY_API_SECRET]
MANDATORY_IMAGE_PARS = []


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        # for easier local project setup
        default_data_dir = Path(__file__).resolve().parent.parent.joinpath('data').as_posix() \
            if not os.environ.get('KBC_DATADIR') else None
        KBCEnvHandler.__init__(self, MANDATORY_PARS, data_path=default_data_dir)
        # override debug from config
        if self.cfg_params.get(KEY_DEBUG):
            debug = True

        log_level = logging.DEBUG if debug else logging.INFO
        # setup GELF if available
        if os.getenv('KBC_LOGGER_ADDR', None):
            self.set_gelf_logger(log_level)
        else:
            self.set_default_logger(log_level)
        logging.info('Loading configuration...')

        try:
            self.validate_config()
            if self.cfg_params.get(KEY_ACTIVITIES):
                self.validate_parameters(self.cfg_params[KEY_ACTIVITIES][0],
                                         [KEY_ACT_TYPES, KEY_ACT_MODE], KEY_ACTIVITIES)

                # validate types
                err = []
                for t in self.cfg_params[KEY_ACTIVITIES][0][KEY_ACT_TYPES]:
                    if t not in api_service.SUPPORTED_ACTIVITY_TYPES:
                        err.append(t)
                if err:
                    raise ValueError(f'These activity types are not supported: {err}')

        except ValueError as e:
            logging.exception(e)
            exit(1)

        # intialize instance parameteres
        self.client = CustomerIoClient(self.cfg_params[KEY_API_SECRET])
        self.writers = {}

        # headers from state
        self.state = self.get_state_file()
        self.activity_headers = {}
        if not self.state:
            self.state = {}

        self.activity_headers = self.state.get("activity_headers", {})
        self.message_headers = self.state.get("message_headers", [])

    def run(self):
        '''
        Main execution code
        '''
        params = self.cfg_params  # noqa
        if params.get(KEY_CUSTOMERS):
            logging.info('Downloading customers export.')
            self.download_customers(params[KEY_CUSTOMERS][0])
            logging.info("Customers downloaded successfully.")

        if params.get(KEY_ACTIVITIES):
            logging.info('Downloading activites.')
            self.download_activities(params[KEY_ACTIVITIES][0])

        last_token = None
        if params.get(KEY_MESSAGES):
            logging.info('Downloading messages.')
            last_token = self.download_messages(params[KEY_MESSAGES][0])

        if params.get(KEY_CAMPAIGNS):
            logging.info('Downloading campaigns.')
            self.download_campaigns()

        if params.get(KEY_SEGMENTS):
            logging.info('Downloading segments..')
            self.download_segments()

        self.write_state_file({"activity_headers": self.activity_headers, "message_headers": self.message_headers,
                               "message_last_token": last_token})

        logging.info('Extraction finished successfully!')

    def download_customers(self, param):
        filters = None
        attributes = None
        if param.get(KEY_FILTERS):
            filters = ast.literal_eval(param.get(KEY_FILTERS))
        if param.get(KEY_ATTRIBUTES):
            attributes = self._parse_comma_separated_values(param[KEY_ATTRIBUTES])

        exp = self.client.submit_export(filters, 'customers', attributes=attributes)
        logging.info(f"Export {exp['description']} submitted.")
        logging.info("Downloading result...")

        customers_out = os.path.join(self.tables_out_path, 'customers.csv')
        self.client.get_export_result(exp['id'], customers_out)
        self.configuration.write_table_manifest(customers_out, primary_key=['id'])

    def download_activities(self, params):
        types = params[KEY_ACT_TYPES]
        mode = params[KEY_ACT_MODE]
        results = []
        logging.info(f'Running in {mode} mode.')
        for t in types:
            logging.info(f'Getting results for activity type: {t}')
            res = self._collect_activities_for_type(t, params.get(KEY_ACT_DELETED, False), mode)
            results.extend(res)

        # close global writer if single table
        if mode == 'SINGLE_TABLE':
            self.writers['SINGLE_TABLE'].close()

        logging.info('Writing activity manifests..')
        self.create_manifests(results, incremental=self.cfg_params[KEY_INCREMENTAL])

    def download_messages(self, params):
        types = params[KEY_ACT_TYPES]
        results = []
        last_tokens = {}
        for t in types:
            logging.info(f'Getting results for message type: {t}')
            res, return_par = self._collect_messages_for_type(t, incremental=params.get(KEY_INCREMENTAL))
            last_tokens[t] = return_par
            results.extend(res)

        logging.info('Writing message manifests..')
        self.create_manifests(results, incremental=self.cfg_params[KEY_INCREMENTAL])
        return last_tokens

    def _collect_activities_for_type(self, activity_type, fetch_deleted, parse_mode):
        wr = None
        for res in self.client.get_activities(activity_type, fetch_deleted):
            if not res:
                continue
            wr = self._get_activity_writer(activity_type, parse_mode, res)
            wr.write_all(res)
        if wr and parse_mode != 'SINGLE_TABLE':
            wr.close()
        return wr.collect_results() if wr else []

    def _collect_messages_for_type(self, message_type, incremental=False):
        wr = None
        last_token = None
        if incremental:
            last_token = self.state.get('message_last_token', {}).get(message_type)
        results = []
        for res, return_par in self.client.get_messages(_type=message_type, last_token=last_token):
            if not res:
                continue
            if return_par:
                last_token = return_par

            wr = self._get_message_writer(res)
            wr.write_all(res)
        if wr:
            wr.close()
            results = wr.collect_results()
        return results, last_token

    def _get_activity_writer(self, activity_type, mode, response) -> ResultWriter:
        if mode == 'SINGLE_TABLE':
            activity_type = 'SINGLE_TABLE'
            if not self.writers.get('SINGLE_TABLE'):
                table_def = KBCTableDef(['id'], SINGLE_ACTIVITY_TBL_HEADER, 'activities_all', '')

                wr = ResultWriter(self.tables_out_path, table_def, fix_headers=True, flatten_objects=False)
                self.writers['SINGLE_TABLE'] = wr

        elif mode == 'PARSED_DATA':
            if not self.writers.get(activity_type):
                header = self._get_activity_table_header(activity_type, response)
                table_def = KBCTableDef(['id'], header, 'activity_' + activity_type, '')

                wr = ResultWriter(self.tables_out_path, table_def, fix_headers=True)
                self.writers[activity_type] = wr
        else:
            raise ValueError(f'Unsupported activity parser mode {mode}')

        return self.writers[activity_type]

    def _get_message_writer(self, response):
        if not self.writers.get('messages_writer'):
            header = self._get_message_table_header(response)
            table_def = KBCTableDef(['deduplicate_id'], header, 'messages', '')

            wr = ResultWriter(self.tables_out_path, table_def, fix_headers=True)
            self.writers['messages_writer'] = wr
        return self.writers['messages_writer']

    def download_campaigns(self):
        campaigns_data = self.client.get_campaigns()
        table_def = KBCTableDef(['id'], CAMPAIGNS_COLS, 'campaigns', '')
        with ResultWriter(self.tables_out_path, table_def, fix_headers=True) as wr:
            wr.write_all(campaigns_data, object_from_arrays=False)
            self.create_manifests(wr.collect_results(), incremental=self.cfg_params[KEY_INCREMENTAL])

    def download_segments(self):
        campaigns_data = self.client.get_segments()
        table_def = KBCTableDef(['id'], [], 'segments', '')
        with ResultWriter(self.tables_out_path, table_def, fix_headers=False) as wr:
            wr.write_all(campaigns_data, object_from_arrays=False)
            self.create_manifests(wr.collect_results(), incremental=self.cfg_params[KEY_INCREMENTAL])

    def _get_activity_table_header(self, activity_type, response):
        wr = ResultWriter(self.tables_out_path, KBCTableDef(['id'], [], 'activity_' + activity_type, ''),
                          fix_headers=True)
        last_header = self.activity_headers.get(activity_type, [])
        curr_header = set(wr.flatten_json(response[0]).keys())
        curr_header.update(last_header)
        self.activity_headers[activity_type] = list(curr_header)
        return list(curr_header)

    def _get_message_table_header(self, response):
        wr = ResultWriter(self.tables_out_path, KBCTableDef(['id'], [], 'messages', ''),
                          fix_headers=True)
        last_header = self.message_headers
        curr_header = set(wr.flatten_json(response[0]).keys())
        curr_header.update(last_header)
        self.message_headers = list(curr_header)
        return list(curr_header)

    def _parse_comma_separated_values(self, param):
        cols = []
        if param:
            cols = [p.strip() for p in param.split(",")]
        return cols


"""
    Main entrypoint
"""

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug = sys.argv[1]
    else:
        debug = False
    try:
        comp = Component(debug)
        comp.run()
    except Exception as e:
        logging.exception(e)
        exit(1)
