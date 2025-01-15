import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', 100)

# pylint: disable=C0303
# pylint: disable=C0301

if __name__ == '__main__':

    # Create a connection to the SQLite database (this will create it if it doesn’t exist)
    conn = sqlite3.connect('uds/uds_codes.db')
    cursor = conn.cursor()

    ###################################################################################
    ####################    SQLite DB for Tabular Lookup    ###########################
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
    
    # NRC Long-form descriptions for vector DB (below)
    nrc_long = 'NRC ' + nrc['NRC'] + ": " + nrc['Description']
    del nrc['Description']  # Drop long-form descriptions
    
    nrc = nrc.rename(columns={'NRC': 'Code', 'Response': 'Description'})  # Standardizing column names
    
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
    
    # SID Long-form descriptions for vector DB (below)
    sid_long = 'SID ' + sid['SID'] + ": " + sid['Description']
    del sid['Description']  # Drop long-form descriptions
    
    sid.rename(columns={'SID': 'Code'}, inplace=True)
    assert sid['Code'].duplicated().sum() == 0, "Duplicate SID codes found!"

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
    #####################     Vector DB for SID & NRC Codes     #######################
    ###################################################################################

    # Combine 
    comb = pd.concat([sid_long, nrc_long], axis=0).reset_index(drop=True)
    
    