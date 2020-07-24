'''
Template Component main class.

'''

import ast
import logging
import os
import sys

from kbc.env_handler import KBCEnvHandler
from kbc.result import KBCTableDef, ResultWriter

from customer_io import api_service
from customer_io.api_service import CustomerIoClient

# configuration variables
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
KEY_ACT_TYPES = 'types'
KEY_ACT_MODE = 'mode'
KEY_ACT_DELETED = 'deleted'

# #### Keep for debug
KEY_DEBUG = 'debug'
MANDATORY_PARS = [KEY_API_SECRET, KEY_SITE_ID]
MANDATORY_IMAGE_PARS = []


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        KBCEnvHandler.__init__(self, MANDATORY_PARS, )
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
        self.client = CustomerIoClient(self.cfg_params[KEY_SITE_ID], self.cfg_params[KEY_API_SECRET])
        self.writers = {}

        # headers from state
        state = self.get_state_file()
        self.activity_headers = {}
        if state:
            self.activity_headers = state.get("activity_headers", {})

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

        if params.get(KEY_CAMPAIGNS):
            logging.info('Downloading campaigns.')
            self.download_campaigns()

        if params.get(KEY_SEGMENTS):
            logging.info('Downloading segments..')
            self.download_segments()

        self.write_state_file({"activity_headers": self.activity_headers})
        logging.info('Extraction finished successfully!')

    def download_customers(self, param):
        filters = None
        if param.get(KEY_FILTERS):
            filters = ast.literal_eval(param.get(KEY_FILTERS))

        exp = self.client.submit_export(filters, 'customers')
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
