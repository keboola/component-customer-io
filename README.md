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

## Incremental loading

Some of the datasets allow `Continue since last run` option. When checked, only the new messages that had appeared since last run are downloaded. 

To backfill without changing this attribute, click the `Reset State` button.

## Campaigns

Downloads campaigns dataset. Note that columns `actions` and `tags` contain JSON and Array object in textual form.

**Example output**:

| actions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | active | created    | created_by | customer_id | date_attribute | deduplicate_id | first_started | frequency | id | name                | start_hour | start_minutes | state   | tags       | timezone |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------|------------|------------|-------------|----------------|----------------|---------------|-----------|----|---------------------|------------|---------------|---------|------------|----------|
| [{'id': 3, 'type': 'email'}, {'id': 7, 'type': 'email'}]                                                                                                                                                                                                                                                                                                                                                                                                                                         |  FALSE | 1591294006 |            |             |                |   123123:29:00 |             0 |           |  1 | Onboarding Campaign |            |               | draft   | ['Sample'] |          |
| [{'id': 63, 'type': 'split_randomized'}, {'id': 78, 'type': 'email'}] |  FALSE | 1593102328 |            |             |                |    33223:29:00 |    1594045951 |           | 10 | Trial Onboarding    |            |               | stopped |            |          |

## Segments

Segments are groups of people, subsets of your audience. You get get information about segments and the customers contained by a segment. 

**Example output**

| deduplicate_id | description                                                                                                                                                               | id | name             | progress | state    | tags |    type |
|----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----|------------------|----------|----------|------|--------:|
| 26521567:45:00 | Includes all people|  1 | Signed up        |          | finished |      | dynamic |
| 26582936:15:00 | Anyone associated with active customer account.                                                                                                                           | 13 | Active Customers |          | finished |      | dynamic |


## Messages

List metadata about messages. You may choose which types of messages you wish.  
Allowable values are `email`, `webhook`, `twilio`, `urban_airship`, `slack`, `push`.

[More info here](https://customer.io/docs/api/#apibeta-apimessagesmessages_list) 



## Customers

### Attributes

Comma separated list of required customer attributes. 
Each customer may have different set of columns, this is to limit only to attributes you need. All attributes are downloaded if left empty.

**NOTE** It is possible that there are some custom attributes with the same name. E.g. `Name` and `name` 
or `Last name` and `last_name` are considered the same after conversion to supported Storage format. 
You may use appropriate [processors](https://developers.keboola.com/extend/component/processors/) to deal with this situation.

### Filter

An additional filter condition in JSON format. The filter language is defined [here](https://customer.io/docs/documentation/api-triggered-data-format.html#general-syntax)

**Example Values**: 

- `Find the first 2 customers in segment 7 and segment 5` =>: `{"and":[{"segment":{"id":7}},{"segment":{"id":5}}]}`
- `Find the first 10 unsubscribed customers` =>: `{"attribute":{"field":"unsubscribed","operator":"eq","value":"true"}}}`


## Activities 
 
 Return information about activities. Activities are cards in campaigns, broadcasts, etc. They might be messages, webhooks, attribute changes, etc.


### Mode of result parsing

Each activity type may have different columns and table structure, for this reason the extractor allows fetching data in two modes:

**`PARSED_DATA`**
 
 Will generate structured table for each activity type. e.g. `event` type will generate table `activity_event`:
 
 | customer_id | data_description | data_project | data_start           | id      | name             | timestamp  |  type |
|-------------|------------------|--------------|----------------------|---------|------------------|------------|------:|
| David       |                  | test         |                      | 1234d   | inactive project | 1609808524 | event |
| Tom         |                  | test2        | 2020-10-19T11:18:55Z | 3467g   | enroll           | 1603120800 | event |
| Carl        | desc             | TS_Test      |                      | 667676h | credit grant     | 1616382356 | event |
 
 
- `SINGLE_TABLE` 

Will populate single activities_all table with data unparsed as column. The data will be present in a `data` folder as a JSON string.
 
 Example:

| customer_id               | data                                                                                                                                                                | delivery_id | delivery_type | id                         | timestamp  |  type |
|---------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|---------------|----------------------------|------------|------:|
| David| {'daysofinactivity': 76, 'lastactivitydate': '2020-10-21', 'project': 'test', 'projecturl': 'example.com'} |             |               | 1234d | 1609808524 | event |
| morta.vilkaite@gmail.com  | {'project': 'https://connection.north-europe.azure.keboola.com/admin/projects/218', 'start': '2020-10-19T11:18:55Z'}                                                |             |               | 01EN0Q4 | 1603120800 | event |

 
 ``````
 
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