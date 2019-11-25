# Import dependencies
import json
import pandas as pd
import numpy as np
import re
from sqlalchemy import create_engine
import psycopg2
from config import db_password
import time

# Clean movie function 
def clean_movie(movie):
    movie = dict(movie)
    alt_titles = {}
    for key in ['Also known as','Arabic','Cantonese','Chinese','French','Hangul','Hebrew','Hepburn','Japanese','Literally','Mandarin','McCune–Reischauer','Original title','Polish','Revised Romanization','Romanized','Russian', 
            'Simplified','Traditional','Yiddish']:
        if key in movie:
            alt_titles[key] = movie[key]
            movie.pop(key)
    if len(alt_titles) > 0:
        movie['alt_titles'] = alt_titles

    # merge column names 
    def change_column_name(old_name, new_name): 
        if old_name in movie: 
            movie[new_name] = movie.pop(old_name) 
    change_column_name('Adaptation by', 'Writer(s)') 
    change_column_name('Country of origin', 'Country') 
    change_column_name('Directed by', 'Director') 
    change_column_name('Distributed by', 'Distributor') 
    change_column_name('Edited by', 'Editor(s)') 
    change_column_name('Length', 'Running time') 
    change_column_name('Original release', 'Release date') 
    change_column_name('Music by', 'Composer(s)') 
    change_column_name('Produced by', 'Producer(s)') 
    change_column_name('Producer', 'Producer(s)') 
    change_column_name('Productioncompanies ', 'Production company(s)') 
    change_column_name('Productioncompany ', 'Production company(s)') 
    change_column_name('Released', 'Release Date') 
    change_column_name('Release Date', 'Release date') 
    change_column_name('Screen story by', 'Writer(s)') 
    change_column_name('Screenplay by', 'Writer(s)') 
    change_column_name('Story by', 'Writer(s)') 
    change_column_name('Theme music composer', 'Composer(s)') 
    change_column_name('Written by', 'Writer(s)') 

    return movie  

# Parse dollar data to float 
def parse_dollars(s): 
    # if s is not a string, return NaN 
    if type(s) != str: 
        return np.nan 

    # if input is of the form $###.# million 
    if re.match(r'\\$\\s*\\d+\\.?\\d*\\s*milli?on', s, flags=re.IGNORECASE): 

        # remove dollar sign and \ million\ 
        s = re.sub('\\$|\\s|[a-zA-Z]','', s) 

        # convert to float and multiply by a million 
        value = float(s) * 10**6 

        # return value 
        return value 

    # if input is of the form $###.# billion 
    elif re.match(r'\\$\\s*\\d+\\.?\\d*\\s*billi?on', s, flags=re.IGNORECASE): 

        # remove dollar sign and \ billion\ 
        s = re.sub('\\$|\\s|[a-zA-Z]','', s) 

        # convert to float and multiply by a billion 
        value = float(s) * 10**9 

        # return value 
        return value 

    # if input is of the form $###,###,### 
    elif re.match(r'\\$\\s*\\d{1,3}(?:[,\\.]\\d{3})+(?!\\s[mb]illion)', s, flags=re.IGNORECASE): 

        # remove dollar sign and commas 
        s = re.sub('\\$|,','', s) 

        # convert to float 
        value = float(s) 

        # return value 
        return value 

    # otherwise, return NaN 
    else: 
        return np.nan


# CHALLENGE: ETL function
def movies_ETL(wiki_data_str, metadata_str, rating_str):
    # Load data assuming data remain the same format
    file_dir = 'C:/Users/Thi/desktop/class/Thi_Nguyen_Movies-ETL'
    try:
        with open(f'{file_dir}/{wiki_data_str}.json', mode='r') as file:
            wiki_data = json.load(file)
    except FileNotFoundError:
        print('Error loading wikipedia file')
    try:
        metadata = pd.read_csv(f'{file_dir}/{metadata_str}.csv', low_memory=False)
    except FileNotFoundError:
        print('Error loading kaggle movies metadata file')
    try:
        rating_data = pd.read_csv(f'{file_dir}/{rating_str}.csv', low_memory=False)
        print('Files sucessfully extracted')
    except FileNotFoundError:
        print('Error loading kaggle ratings file')

    # Clean wiki_data assuming columns remain the same
    wiki_movies = [movie for movie in wiki_data if ('Director' in movie or 'Directed by' in movie) and 'imdb_link' in movie and 'No. of episodes' not in movie]  
    clean_movies = [clean_movie(movie) for movie in wiki_movies]
    wiki_movies_df = pd.DataFrame(clean_movies)
    # Assuming that imdb id remains the same format
    wiki_movies_df['imdb_id'] = wiki_movies_df['imdb_link'].str.extract(r'(tt\d{7})')
    wiki_movies_df.drop_duplicates(subset='imdb_id', inplace=True)
    # Asumption: drop column that has 90% of null values
    wiki_movies_df = wiki_movies_df[[column for column in wiki_movies_df.columns if wiki_movies_df[column].isnull().sum() < len(wiki_movies_df) * 0.9]]

    # Clean box office data assuming data type is object
    form_one = r'\\$\\s*\\d+\\.?\\d*\\s*[mb]illi?on'
    form_two = r'\\$\\s*\\d{1,3}(?:[,\\.]\\d{3})+(?!\\s[mb]illion)'
    box_office = wiki_movies_df['Box office'].dropna().apply(lambda x: ' '.join(x) if type(x) == list else x)
    wiki_movies_df['box_office'] = box_office.str.extract(f'({form_one}|{form_two})', flags=re.IGNORECASE)[0].apply(parse_dollars)
    wiki_movies_df.drop('Box office', axis=1, inplace=True)

    # Clean budget data
    budget = wiki_movies_df['Budget'].dropna().apply(lambda x: ' '.join(x) if type(x) == list else x)
    budget = budget.str.replace(r'\\$.*[-—–](?![a-z])', '$', regex=True)
    budget = budget.str.replace(r'\\[\\d+\\]\\s*', '')
    wiki_movies_df['budget'] = budget.str.extract(f'({form_one}|{form_two})', flags=re.IGNORECASE)[0].apply(parse_dollars)
    wiki_movies_df.drop('Budget', axis=1, inplace=True)

    # Clean release date data
    date_form_one = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s[123]\\d,\\s\\d{4}'
    date_form_two = r'\\d{4}.[01]\\d.[123]\\d'
    date_form_three = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s\\d{4}'
    date_form_four = r'\\d{4}'
    release_date = wiki_movies_df['Release date'].dropna().apply(lambda x: ' '.join(x) if type(x) == list else x)
    wiki_movies_df['release_date'] = pd.to_datetime(release_date.str.extract(f'({date_form_one}|{date_form_two}|{date_form_three}|{date_form_four})')[0], infer_datetime_format=True)
    wiki_movies_df.drop('Release date', axis=1, inplace=True)

    # Clean Running time
    running_time = wiki_movies_df['Running time'].dropna().apply(lambda x: ' '.join(x) if type(x) == list else x)
    running_time_extract = running_time.str.extract(r'(\\d+)\\s*ho?u?r?s?\\s*(\\d*)|(\\d+)\\s*m')
    running_time_extract = running_time_extract.apply(lambda col: pd.to_numeric(col, errors='coerce')).fillna(0)
    wiki_movies_df['running_time'] = running_time_extract.apply(lambda row: row[0]*60 + row[1] if row[2] == 0 else row[2], axis=1)
    wiki_movies_df.drop('Running time', axis=1, inplace=True)

    print('Finish Cleaning wikpedia data')


    ## CLEAN metadata
    # keep rows where adult is false and drop the column
    metadata = metadata[metadata['adult'] == 'False'].drop('adult',axis='columns')
    # Convert data type
    metadata['video'] = metadata['video'] == 'True'
    metadata['budget'] = metadata['budget'].astype(int)
    metadata['id'] = pd.to_numeric(metadata['id'], errors='raise')
    metadata['popularity'] = pd.to_numeric(metadata['popularity'], errors='raise')
    metadata['release_date'] = pd.to_datetime(metadata['release_date'])
    print('Finish Cleaning kaggle movies metadata data')

    ## Clean ratings data
    rating_data['timestamp'] = pd.to_datetime(rating_data['timestamp'], unit='s')

    # Merge wikipedia and kaggle metadata
    try:
        movies_df = pd.merge(wiki_movies_df, metadata, on='imdb_id', suffixes=['_wiki','_kaggle'])
    except:
        print('error')
    # Drop wrongly merged row
    movies_df = movies_df.drop(movies_df[(movies_df['release_date_wiki'] > '1996-01-01') & (movies_df['release_date_kaggle'] < '1965-01-01')].index)

    # Drop the  title_wiki, release_date_wiki, Language, and Production company(s) columns assuming keeping the data from kaggle
    try:
        movies_df.drop(columns=['title_wiki','release_date_wiki','Language','Production company(s)'], inplace=True)
    except:
        print('Error dropping wikipedia columns')
    # Create function to fill in missing data for a column pair and drops the redundant column   
    def fill_missing_kaggle_data(df, kaggle_column, wiki_column):
        df[kaggle_column] = df.apply(lambda row: row[wiki_column] if row[kaggle_column] == 0 else row[kaggle_column], axis=1)
        df.drop(columns=wiki_column, inplace=True)
    # Call fill funtion on runtime, budget and box office data
    try:
        fill_missing_kaggle_data(movies_df, 'runtime', 'running_time')
        fill_missing_kaggle_data(movies_df, 'budget_kaggle', 'budget_wiki')
        fill_missing_kaggle_data(movies_df, 'revenue', 'box_office')
    except:
        print('Error filling in missing kaggle data from wikipedia data')

    # Rearrange columns assuming the same columns
    try:
        movies_df = movies_df[['imdb_id','id','title_kaggle','original_title','tagline','belongs_to_collection','url','imdb_link',
                       'runtime','budget_kaggle','revenue','release_date_kaggle','popularity','vote_average','vote_count',
                       'genres','original_language','overview','spoken_languages','Country',
                       'production_companies','production_countries','Distributor',
                       'Producer(s)','Director','Starring','Cinematography','Editor(s)','Writer(s)','Composer(s)','Based on'
                      ]]
    except:
        print('Column(s) not found')
    movies_df.rename({'id':'kaggle_id',
                  'title_kaggle':'title',
                  'url':'wikipedia_url',
                  'budget_kaggle':'budget',
                  'release_date_kaggle':'release_date',
                  'Country':'country',
                  'Distributor':'distributor',
                  'Producer(s)':'producers',
                  'Director':'director',
                  'Starring':'starring',
                  'Cinematography':'cinematography',
                  'Editor(s)':'editors',
                  'Writer(s)':'writers',
                  'Composer(s)':'composers',
                  'Based on':'based_on'
                 }, axis='columns', inplace=True)
    print('Finish combining wikipedia data and kaggle meta data')

    # Count ratings for each movie and remane userID to count and create pivot table
    rating_counts = rating_data.groupby(['movieId','rating'], as_index=False).count().rename({'userId':'count'}, axis=1).pivot(index='movieId',columns='rating', values='count')
    movies_with_ratings_df = pd.merge(movies_df, rating_counts, left_on='kaggle_id', right_index=True, how='left')
    movies_with_ratings_df[rating_counts.columns] = movies_with_ratings_df[rating_counts.columns].fillna(0)

    # Save to SQL
    # Connection string
    try:
        db_string = f'postgres://postgres:{db_password}@127.0.0.1:5432/movie_data'
    except:
        print('Error creating connection string')
    # Create database engine
    engine = create_engine(db_string)
    # replace the movie records in movies table
    engine.execute('DELETE FROM movies')
    movies_df.to_sql(name='movies', con=engine, if_exists='append')

    # replace the rating records in ratings table
    engine.execute('DELETE FROM ratings')
    rows_imported = 0
    # get the start_time from time.time()
    try:
        start_time = time.time()
        for data in pd.read_csv(f'{file_dir}/{rating_str}.csv', chunksize=1000000):
            print(f'importing rows {rows_imported} to {rows_imported + len(data)}...', end='')
            data.to_sql(name='ratings', con=engine, if_exists='append')
            rows_imported += len(data)

            # add elapsed time to final print out
            print(f'Done. {time.time() - start_time} total seconds elapsed')
    except:
        print('Error loading ratings file to SQL')

    print('Finish loading data to SQL')

    return movies_df

# Run ETL function
movies_ETL('wikipedia-movies', 'movies_metadata', 'ratings')


