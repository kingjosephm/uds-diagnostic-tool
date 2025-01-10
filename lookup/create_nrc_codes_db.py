import pandas as pd
import sqlite3

pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', 100)


if __name__ == '__main__':
    
    # UDS Negative Response Codes
    negative_response_codes = pd.read_excel('lookup/uds_codes.xlsx', sheet_name='nrc').dropna().reset_index(drop=True)
    negative_response_codes[negative_response_codes.select_dtypes(['object']).columns] = negative_response_codes.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Drop any "ISO Reserved" codes
    negative_response_codes = negative_response_codes[~negative_response_codes['Description'].str.contains('ISO Reserved')]
    
    # Drop code "0x00" since it is not a negative response code
    negative_response_codes = negative_response_codes[~negative_response_codes['NRC'].str.contains('0x00')]
    
    negative_response_codes.drop(columns=['Description'], inplace=True)
    
    # Standardizing column names
    negative_response_codes.rename(columns={'NRC': 'Code', 'Response': 'Description'}, inplace=True)
    
    # Create a connection to the SQLite database (this will create it if it doesn’t exist)
    conn = sqlite3.connect('lookup/nrc_codes.db')
    cursor = conn.cursor()
    
    # Write df to new table in SQLite, or overwrite existing table
    negative_response_codes.to_sql(name='nrc_codes', con=conn, if_exists='replace', index=False)
    
    # Query the database for sanity check
    pd.read_sql_query(f"SELECT * FROM nrc_codes LIMIT 5;", conn)