# Customer.io Extractor

Fetch customers, campaigns, segments and activites from your Customer.io account.


**Table of contents:**  
  
[TOC]

# Configuration

## Authorization

- **API key** - You can generate a bearer token, known as an App API Key, with a defined scope in [your account settings](https://fly.customer.io/settings/api_credentials?keyType=app)
. [Learn more about bearer authorization in Customer.io.](https://customer.io/docs/managing-credentials)



## Load type

If set to Incremental update, the result tables will be updated based on primary key consisting of all selected dimensions. Full load overwrites the destination table each time, with no primary keys.

**Note**: When set to incremental updates the primary key is set automatically based on the dimensions selected. 
If the dimension list is changed in an existing configuration, the existing result table might need to be dropped or the primary key changed before the load, since it structure 
will be different. If set to full load, **no primary key** is set.

## Campaigns

Downloads campaigns dataset. Note that columns `actions` and `tags` contain JSON and Array object in textual form.

## Segments

Downloads segments

## Messages

List metadata about messages. You may choose which types of messages you wish.  
Allowable values are `email`, `webhook`, `twilio`, `urban_airship`, `slack`, `push`.

[More info here](https://customer.io/docs/api/#apibeta-apimessagesmessages_list) 

### Incremental loading

When `Continue since last run` is checked, only the new messages that had appeared since last run are downloaded. 
To backfill without changing this attribute, click the `Reset State` button.

## Customers

### Filter

An additional filter condition in JSON format. The filter language is defined [here](https://customer.io/docs/documentation/api-triggered-data-format.html#general-syntax)

**Example Values**: 

- `Find the first 2 customers in segment 7 and segment 5` =>: `{"and":[{"segment":{"id":7}},{"segment":{"id":5}}]}`
- `Find the first 10 unsubscribed customers` =>: `{"attribute":{"field":"unsubscribed","operator":"eq","value":"true"}}}`


## Activities 
 
 
 
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