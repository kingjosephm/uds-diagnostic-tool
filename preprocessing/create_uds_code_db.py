import pandas as pd
import sqlite3

pd.set_option('display.max_rows', 100)


if __name__ == '__main__':
    
    # UDS Service codes
    service_codes = pd.read_excel('lookup/uds_codes.xlsx', sheet_name='services').dropna().reset_index(drop=True)
    service_codes[service_codes.select_dtypes(['object']).columns] = service_codes.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Standardizing column names
    service_codes.rename(columns={'SID': 'Code', 'Description': 'Description_Long', 'Service': 'Description'}, inplace=True)
    service_codes['Type'] = 'Service' + ' ' + service_codes['Type']
    
    
    # UDS Negative Response Codes
    negative_response_codes = pd.read_excel('lookup/uds_codes.xlsx', sheet_name='nrc').dropna().reset_index(drop=True)
    negative_response_codes[negative_response_codes.select_dtypes(['object']).columns] = negative_response_codes.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Standardizing column names
    negative_response_codes.rename(columns={'NRC': 'Code', 'Description': 'Description_Long', 'Response': 'Description'}, inplace=True)
    negative_response_codes['Type'] = 'Negative Response Code'
    
    # Create unified DataFrame
    df = pd.concat([service_codes, negative_response_codes], ignore_index=True).sort_values(by=['Code', 'Type'], ascending=[True, False]).reset_index(drop=True)
    
    # Create a connection to the SQLite database (this will create it if it doesn’t exist)
    conn = sqlite3.connect('lookup/uds_codes.db')
    cursor = conn.cursor()
    
    # Write df to new table in SQLite, or overwrite existing table
    df.to_sql(name='uds_codes', con=conn, if_exists='replace', index=False)
    
    
    # Query the database for sanity check
    pd.read_sql_query(f"SELECT * FROM uds_codes LIMIT 5;", conn)

    