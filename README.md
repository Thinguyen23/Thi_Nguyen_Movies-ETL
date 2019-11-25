# Thi_Nguyen_Movies-ETL
This analysis gather data from both Wikipedia and Kaggle, combine them and save in a SQL database using the ETL process: extract the data from files, transform the datasets by cleaning and joing, load the dataset into SQL database. These are the assumptions made throughout the process:
1. All updated data will stay in the same formats (wikipedia in json, kaggle data in csv)
2. All converted dataframe remain the same columns titles and data types to enable merge and functions
3. All box office, budget, release date, running time data remain in the similar formats to enable cleanning processes
4. Drop rows that are small in number (compared to the data size) but take extensive time to clean up
5. Drop columns that have 90% values as null
6. When merging wikipedia and kaggle metadata datasets, drop title, release date, language, and production company(s) from wikipedia dataset and keep the kaggle metadata as the more accurate data
7. When merging wikipedia and kaggle metadata datasets, keep the kaggle metadata runtime, budget and box office data and fill in zero values with wikipedia data
8. ProstgreSQL passcode is saved correctly in the config file.
