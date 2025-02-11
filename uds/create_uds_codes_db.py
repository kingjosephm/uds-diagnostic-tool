import sqlite3
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

pd.set_option('display.max_rows', 20)
pd.set_option('display.max_columns', 100)

# pylint: disable=C0303
# pylint: disable=C0301

if __name__ == '__main__':

    # Create a connection to the SQLite database (this will create it if it doesn’t exist)
    conn = sqlite3.connect('uds/uds_codes.db')
    cursor = conn.cursor()

    ###################################################################################
    ####################        Short UDS Descriptions      ###########################
    ###################################################################################
    
    # NRC Codes
    nrc = pd.read_excel('uds/uds_codes.xlsx', sheet_name='nrc').dropna().reset_index(drop=True)
    nrc[nrc.select_dtypes(['object']).columns] = nrc.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings

    nrc = nrc[~nrc['Description'].str.contains('ISO Reserved')]  # Drop any "ISO Reserved" codes
    nrc = nrc[~nrc['Response'].str.contains('Vehicle Manufacturer Specific')]
    nrc = nrc[~nrc['Response'].str.contains('Reserved For Specific Conditions Not Correct')]
    nrc = nrc[~nrc['NRC'].str.contains('0x00')]  # Drop code "0x00" since it is not a negative response code
    nrc = nrc.reset_index(drop=True)
    assert nrc['NRC'].duplicated().sum() == 0, "Duplicate NRC codes found!"
    
    nrc.rename(columns={'NRC': 'Code'}, inplace=True)
        
    # NRC Long-form descriptions for vector DB (below)
    nrc['Type'] = 'NRC'
    nrc_long = nrc[['Code', 'Type', 'Description']]
    nrc.drop(columns=['Type', 'Description'], inplace=True)  # drop long-form descriptions
    
    nrc = nrc.rename(columns={'Response': 'Description'})  # Use short-form description for SQLite DB
    
    # Write df to new table in SQLite, or overwrite existing table
    nrc.to_sql(name='nrc', con=conn, if_exists='replace', index=False)
    
    # Query the database for sanity check
    pd.read_sql_query("SELECT * FROM nrc LIMIT 5;", conn)
    
    # SID Codes
    sid = pd.read_excel('uds/uds_codes.xlsx', sheet_name='services').dropna().reset_index(drop=True)
    sid[sid.select_dtypes(['object']).columns] = sid.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Drop service codes that are "Supplier Specific" or "Reserved"
    sid = sid[~sid['Service'].str.contains('Supplier Specific')].reset_index(drop=True)
    sid = sid[~sid['Description'].str.contains('Reserved')].reset_index(drop=True)
    sid = sid[~sid['Description'].str.contains('ISO')].reset_index(drop=True)
    
    sid.rename(columns={'SID': 'Code'}, inplace=True)
    assert sid['Code'].duplicated().sum() == 0, "Duplicate SID codes found!"
    
    # SID Long-form descriptions for vector DB (below)
    sid_long = sid[['Code', 'Type', 'Description']].copy()
    sid_long['Type'] = 'SID'
    del sid['Description']  # Drop long-form descriptions

    # Combined description
    sid['Description'] = np.where((sid['Type']=='Request') & (sid['Code'] != '0x7F'), sid['Service'] + ' Request', np.NaN)
    sid['Description'] = np.where(sid['Code'] == '0x7F', sid['Service'], sid['Description'])
    sid['Description'] = np.where((sid['Type']=='Response') & (sid['Code'] != '0x7F'), 'Positive Response to ' 
                                  + sid['Service'], sid['Description'])
    
    # Write df to new table in SQLite, or overwrite existing table
    sid[['Code', 'Description']].to_sql(name='sid', con=conn, if_exists='replace', index=False)

    # Query the database for sanity check
    pd.read_sql_query("SELECT * FROM sid LIMIT 5;", conn)

    ###################################################################################
    ####################      Long UDS Descriptions         ###########################
    ###################################################################################

    # Combine 
    long = pd.concat([sid_long, nrc_long], axis=0).reset_index(drop=True)
    
    long.to_sql(name='descriptions', con=conn, if_exists='replace', index=False)
    
    # Query the database for sanity check
    pd.read_sql_query("SELECT * FROM descriptions LIMIT 5;", conn)