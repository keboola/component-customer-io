import json
import time

import requests
from kbc.client_base import HttpClientBase

BASE_URL = 'https://beta-api.customer.io/v1/api/'

MAX_RETRIES = 10

# endpoints
END_EXPORTS = 'exports/'
END_BUYER_STATS_OPERATION = 'v1/buyer/stats/operations/'

DEFAULT_PAGING_LIMIT = 10000
# wait between polls (s)
DEFAULT_WAIT_INTERVAL = 2

SUPPORTED_ACTIVITY_TYPES = ["page", "event", "attribute_change", "failed_attribute_change", "stripe_event",
                            "drafted_email", "failed_email", "dropped_email", "sent_email", "spammed_email",
                            "bounced_email", "delivered_email", "triggered_email", "opened_email", "clicked_email",
                            "converted_email", "unsubscribed_email", "attempted_email", "undeliverable_email",
                            "device_change", "attempted_action", "drafted_action", "sent_action", "delivered_action",
                            "bounced_action", "failed_action", "converted_action", "undeliverable_action",
                            "opened_action", "secondary:dropped_email", "secondary:spammed_email",
                            "secondary:bounced_email", "secondary:delivered_email", "secondary:opened_email",
                            "secondary:clicked_email", "secondary:failed_email"]


class CustomerIoClientError(Exception):
    """

    """


class CustomerIoClient(HttpClientBase):
    """
    Basic HTTP client taking care of core HTTP communication with the API service.

    It exttends the kbc.client_base.HttpClientBase class, setting up the specifics for Adform service and adding
    methods for handling pagination.

    """

    def __init__(self, site_id, secret_key):
        HttpClientBase.__init__(self, base_url=BASE_URL, max_retries=MAX_RETRIES, backoff_factor=0.3,
                                status_forcelist=(429, 500, 502, 504),
                                auth=(site_id, secret_key))

    def _get_paged_result_pages(self, endpoint, parameters, res_obj_name, has_more_attr='next', offset=None,
                                limit=DEFAULT_PAGING_LIMIT):
        """
        Generic pagination getter method returning Iterable instance that can be used in for loops.

        :param endpoint:
        :param parameters:
        :param res_obj_name:
        :param has_more_attr:
        :param offset:
        :param limit:
        :return:
        """
        has_more = True
        while has_more:

            if offset:
                parameters['start'] = offset
            parameters['limit'] = limit

            url = self.base_url + endpoint
            req = self.get_raw(url, params=parameters)
            resp_text = str.encode(req.text, 'utf-8')
            req_response = json.loads(resp_text)

            self._validate_response(url, req_response)

            if req_response[has_more_attr]:
                has_more = True
            else:
                has_more = False
            offset = req_response[has_more_attr]

            yield req_response[res_obj_name]

    def submit_export(self, filters, type, **additional_params):
        """

        :param type: type of export [customers, deliveries]
        :param filters: dict
            {"filters":{"and":[{"segment":{"id":7}},{"segment":{"id":5}}]}}


        :return: export object (dict)
                {
                "id": 110,
                "deduplicate_id": "110:1530296738",
                "type": "customers",
                "failed": false,
                "description": "Filtered customer export (created via the api)",
                "downloads": 2,
                "created_at": 1530296738,
                "updated_at": 1530296738
              }
        """
        # get all if no filter specified
        if not filters:
            filters = {"attribute": {"field": "id", "operator": "exists"}}

        body = dict(filters=filters)
        body = {**body, **additional_params}

        response = self.post_raw(self.base_url + END_EXPORTS + type, json=body)
        if response.status_code > 299:
            raise CustomerIoClientError(
                f"Failed to submit export. Operation failed with code {response.status_code}. Reason: {response.text}")

        return response.json()['export']

    def get_export_result(self, export_id, result_path):

        res_url = self.get_wait_for_export_result_url(export_id)
        res = requests.get(res_url)

        with open(result_path, 'wb+') as out:
            for chunk in res.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive new chunks
                    out.write(chunk)
        return result_path

    def get_wait_for_export_result_url(self, export_id):
        url = self.base_url + END_EXPORTS + str(export_id) + '/download'

        continue_polling = True
        max_retries = 20
        retry = 0
        errors = ''
        res = {}
        while continue_polling:

            time.sleep(DEFAULT_WAIT_INTERVAL)
            res = self.get(url)
            errors = res.get('errors')
            if res.get('url') or retry >= max_retries:
                continue_polling = False
            retry += 1
        if retry >= max_retries:
            raise CustomerIoClientError(f'Report job ID "{export_id} failed to process with error {errors}"')

        return res['url']

    def get_activities(self, type=None, deleted=False, **additional_params):
        """

        :param type:   one of SUPPORTED_ACTIVITY_TYPES
        :param deleted:
        :param additional_params:
        :return:
        """
        parameters = {"type": type, "deleted": deleted}
        parameters = {**parameters, **additional_params}
        return self._get_paged_result_pages('activities', parameters, 'activities')

    def get_campaigns(self):
        url = self.base_url + 'campaigns'
        res = self.get(url=url)
        self._validate_response(url, res)
        return res['campaigns']

    def get_segments(self):
        url = self.base_url + 'segments'
        res = self.get(url=url)
        self._validate_response(url, res)
        return res['segments']

    def _validate_response(self, url, response):
        if response.get('errors'):
            raise CustomerIoClientError(f'Request to {url} failed with {response.get("errors")}')
