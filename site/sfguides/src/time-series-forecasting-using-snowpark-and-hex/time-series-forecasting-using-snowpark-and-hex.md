author: Hex Staff
id: time-series-forecasting-using-snowpark-and-hex
summary: This solution architecture shows how to use Snowpark User-Defined Table Functions to forecast the foot traffic of a restaurant chain by locations.
categories: snowflake-site:taxonomy/solution-center/certification/partner-solution
environments: web
language: en
status: Published
feedback link: https://github.com/Snowflake-Labs/sfguides/issues
fork repo link: https://github.com/Snowflake-Labs/sfquickstarts/tree/master/site/sfguides/src/time-series-forecasting-using-snowpark-and-hex

# Parallelized Time Series Analysis of Restaurant Foot Traffic
<!-- ------------------------ -->
## Overview

This solution architecture shows how to use Snowpark User-Defined Table Functions to forecast the foot traffic of a restaurant chain by locations. 

* Run pre-processing and feature engineering using Snowpark
* Use Snowpark UDTF to train several forecasting models in parallel for different store locations

<!-- ------------------------ -->
## Solution Architecture: Time series forecasting with Snowpark UDTF and Hex

![Architecture Diagram](assets/time-series-forecasting-using-snowpark-and-hex.png)

* In this use-case, you learn how to use Snowpark to analyze the store locations and customer traffic data.
* The solution shows how to use Snowpark UDTFs to train several ML models in parallel.
