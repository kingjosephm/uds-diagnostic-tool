import pandas as pd
import numpy as np
import sqlite3

pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', 100)


if __name__ == '__main__':
    
    # Create a connection to the SQLite database (this will create it if it doesn’t exist)
    conn = sqlite3.connect('uds/uds_codes.db')
    cursor = conn.cursor()
    
    ###################################################################################
    ########################### UDS Negative Response Codes ###########################
    ###################################################################################
    df = pd.read_excel('uds/uds_codes.xlsx', sheet_name='nrc').dropna().reset_index(drop=True)
    df[df.select_dtypes(['object']).columns] = df.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Drop any "ISO Reserved" codes
    df = df[~df['Description'].str.contains('ISO Reserved')]
    
    # Drop code "0x00" since it is not a negative response code
    df = df[~df['NRC'].str.contains('0x00')]
    
    df.drop(columns=['Description'], inplace=True)
    
    # Standardizing column names
    df.rename(columns={'NRC': 'Code', 'Response': 'Description'}, inplace=True)
    
    # Write df to new table in SQLite, or overwrite existing table
    df.to_sql(name='nrc', con=conn, if_exists='replace', index=False)
    
    # Query the database for sanity check
    pd.read_sql_query(f"SELECT * FROM nrc LIMIT 5;", conn)
    
    
    ###################################################################################
    ###########################      UDS Service Codes      ###########################
    ###################################################################################
    df = pd.read_excel('uds/uds_codes.xlsx', sheet_name='services', usecols=['SID', 'Type', 'Service']).dropna().reset_index(drop=True)
    df[df.select_dtypes(['object']).columns] = df.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Drop supplier specific services
    df = df[~df['Service'].str.contains('Supplier Specific')].reset_index(drop=True)
    
    # Combined description
    df['Description'] = np.where((df['Type']=='Request') & (df['SID'] != '0x7F'), df['Service'] + ' Request', np.NaN)
    df['Description'] = np.where(df['SID'] == '0x7F', df['Service'], df['Description'])
    df['Description'] = np.where((df['Type']=='Response') & (df['SID'] != '0x7F'), 'Positive Response to ' + df['Service'], df['Description'])
    
    # Write df to new table in SQLite, or overwrite existing table
    df[['SID', 'Description']].to_sql(name='sid', con=conn, if_exists='replace', index=False)

    # Query the database for sanity check
    pd.read_sql_query(f"SELECT * FROM sid LIMIT 5;", conn)
    