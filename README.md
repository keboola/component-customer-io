# Customer.io Extractor

Fetch customers, campaigns, segments and activites from your Customer.io account.


**Table of contents:**  
  
[TOC]

# Configuration

## Authorization

- **API key**, **Site ID** - Provide your Customer.io credentials.

## Load type

If set to Incremental update, the result tables will be updated based on primary key consisting of all selected dimensions. Full load overwrites the destination table each time, with no primary keys.

**Note**: When set to incremental updates the primary key is set automatically based on the dimensions selected. 
If the dimension list is changed in an existing configuration, the existing result table might need to be dropped or the primary key changed before the load, since it structure 
will be different. If set to full load, **no primary key** is set.

## Download Campaigns

Downloads campaigns dataset. Note that columns `actions` and `tags` contain JSON and Array object in textual form.

## Download Segments

### Date

Report date range boundaries. The maximum date range accessible through API is 397 days (13 months) from today.

### Client IDS

Optional list of client IDs to retrieve. If left empty, data for all available clients will be retrieved.

## Dimensions

List of report dimensions. For full list of dimensions and its' description [refer here](docs/available_dimensions.md)

## Metrics

List of report metrics. Max 10. Note that some combinations of metrics and/or dimensions are not supported.

Each metric definition consists of a **metric name** and additional filtering possibilities (`Specs Metadata`) for individual metric. 
If no value is specified in the `Specs Metadata` the default metric is used.

For a full list of available metrics and specs [see here](https://bitbucket.org/kds_consulting_team/kds-team.ex-adform-reports/raw/a5e14ac3450e4e1ab5b3cdb061493e2d5078108f/docs/available_metrics.md)

 
## Development
 
This example contains runnable container with simple unittest. For local testing it is useful to include `data` folder in the root
and use docker-compose commands to run the container or execute tests. 

If required, change local data folder (the `CUSTOM_FOLDER` placeholder) path to your custom path:
```yaml
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
```

Clone this repository, init the workspace and run the component with following command:

```
git clone https://bitbucket.org:kds_consulting_team/kbc-python-template.git my-new-component
cd my-new-component
docker-compose build
docker-compose run --rm dev
```

Run the test suite and lint check using this command:

```
docker-compose run --rm test
```

# Integration

For information about deployment and integration with KBC, please refer to the [deployment section of developers documentation](https://developers.keboola.com/extend/component/deployment/) 