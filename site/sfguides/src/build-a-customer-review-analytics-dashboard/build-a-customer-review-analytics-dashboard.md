author: Chanin Nantasenemat
id: build-a-customer-review-analytics-dashboard
summary: Process and analyze customer review data using an LLM-powered data processing workflow with Snowflake Cortex.
categories: snowflake-site:taxonomy/solution-center/certification/certified-solution
environments: web
language: en
status: Published
feedback link: https://github.com/Snowflake-Labs/sfguides/issues
fork repo link: https://github.com/Snowflake-Labs/sfquickstarts/tree/master/site/sfguides/src/build-a-customer-review-analytics-dashboard

# Build a Customer Review Analytics Dashboard
<!-- ------------------------ -->
## Overview

Process and analyze customer review data using an LLM-powered data processing workflow with Snowflake Cortex.

Build a  customer review analytics dashboard that processes unstructured text data and visualizes sentiment trends across products and time periods.

<!-- ------------------------ -->
## Code Example

```sql
SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;

SELECT 
  filename,
  SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
    @avalanche_db.avalanche_schema.customer_reviews,
    filename,
    {'mode': 'layout'}
  ):content AS layout
FROM files;
```
