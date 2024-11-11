import pandas as pd
import sqlite3
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
openai_api_key = os.getenv('OPENAI_API_KEY')  # Get the OPENAI_API_KEY from environment variables

pd.set_option('display.max_rows', 100)
pd.set_option('display.max_colwidth', None)  # No truncation of column content


def summarize_code(df: pd.DataFrame) -> pd.Series:
    """Summarize UDS codes."""
    
    template = """ You are a helpful assistant that summarizes metadata.

    Here is the metadata:

    Metadata: {metadata}

    Provide a concise (max. 15 word) summary using only the information given.

    """
    
    prompt = PromptTemplate(
    input_variables=["metadata"],
    template=template,
    )

    llm = ChatOpenAI(api_key=openai_api_key, temperature=0, model="gpt-4o-mini")
    chain = prompt | llm
    
    
    summaries = []
    for i in df.index:
        metadata = str(df.loc[i, ['Description', 'Description_Long']].to_dict())
        summary = chain.invoke(metadata).content
        summaries.append(df.loc[i, 'Type'] + ": " + summary)
    
    return pd.Series(summaries)



if __name__ == '__main__':
    
    # UDS Service codes
    service_codes = pd.read_excel('lookup/uds_codes.xlsx', sheet_name='services').dropna().reset_index(drop=True)
    service_codes[service_codes.select_dtypes(['object']).columns] = service_codes.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Standardizing column names
    service_codes.rename(columns={'SID': 'Code', 'Description': 'Description_Long', 'Service': 'Description'}, inplace=True)
    service_codes['Type'] = 'Service' + ' ' + service_codes['Type']
    
    # Create a summary of the service codes using ChatGPT
    service_codes['Summary'] = summarize_code(service_codes)
    
    # UDS Negative Response Codes
    negative_response_codes = pd.read_excel('lookup/uds_codes.xlsx', sheet_name='nrc').dropna().reset_index(drop=True)
    negative_response_codes[negative_response_codes.select_dtypes(['object']).columns] = negative_response_codes.select_dtypes(['object']).apply(lambda x: x.str.strip())  # stipping whitespace from strings
    
    # Standardizing column names
    negative_response_codes.rename(columns={'NRC': 'Code', 'Description': 'Description_Long', 'Response': 'Description'}, inplace=True)
    negative_response_codes['Type'] = 'Negative Response Code'
    
    # Create a summary of the service codes using ChatGPT
    negative_response_codes['Summary'] = summarize_code(negative_response_codes)
    
    # Create unified DataFrame
    cols = ['Code', 'Type', 'Summary']
    df = pd.concat([service_codes[cols], negative_response_codes[cols]], ignore_index=True).sort_values(by=['Code', 'Type'], ascending=[True, False]).reset_index(drop=True)
    assert df.duplicated(subset=['Code', 'Type']).sum() == 0  # ensure no duplicates
    
    # Create a connection to the SQLite database (this will create it if it doesn’t exist)
    conn = sqlite3.connect('lookup/uds_codes.db')
    cursor = conn.cursor()
    
    # Write df to new table in SQLite, or overwrite existing table
    df.to_sql(name='uds_codes', con=conn, if_exists='replace', index=False)
    
    
    # Query the database for sanity check
    pd.read_sql_query(f"SELECT * FROM uds_codes LIMIT 5;", conn)

    