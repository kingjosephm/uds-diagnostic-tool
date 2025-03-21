import os
import asyncio
import pandas as pd
import pyshark
import sqlite3
import numpy as np
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# pylint: disable=C0303
# pylint: disable=C0301
# pylint: disable=e1133


async def read_pcap_file(file_path: str) -> pd.DataFrame:
    """Reads a pcap file and returns a Pandas DataFrame with UDS packets.

    Args:
        file_path (str): string path to the pcap file

    Returns:
        pd.DataFrame: DataFrame with UDS packets, with columns:
            - number: Packet number
            - timestamp: Time of packet capture
            - source: Source address
            - target: Target address
            - request: True if request, False if reply
            - sid: Service ID
            - error: Error code (if present)
    """
    capture = pyshark.FileCapture(file_path, include_raw=True, use_json=True)
        
    uds_packets = {}
    
    # Iterate through each packet, collecting as dictionary
    for packet in capture:
        
        if hasattr(packet, "uds"):  # note - only keeps UDS packets
            
            packet_info = {
                'number': packet.number,  # Packet number
                'timestamp': packet.sniff_time.strftime("%Y-%m-%d %H:%M:%S.%f"),  # timestamp of when packet captured by the network sniffer
                'source': packet.doip.source_address if hasattr(packet.doip, 'source_address') else None,
                'target': packet.doip.target_address if hasattr(packet.doip, 'target_address') else None,
                'request': True if packet.uds.reply == '0x00' else False,  # misnomer, this is request code if '0x00'. Reply codes are '0x01'
                'sid': None,  # Service ID, fill in below
                'error': None,  # alter below, if present
            }
            
            if packet_info['request']:
                packet_info['sid'] = packet.uds.sid
            else:  # reply code
                packet_info['sid'] = hex(int(packet.uds.sid, 16) + 0x40)  # must add '0x40' to get correct reply code for both positive and negative replies
                if hasattr(packet.uds, 'err'):
                    packet_info['error'] = packet.uds.err.code  # negative reply error code. This is second byte of the negative reply shown in CloudShark. Ignore first byte of negative reply code for now since this not standardized
            
            # Capitalize the letters in the SID and Reply fields
            for key in ['sid', 'error']:  # assumes only one byte
                if packet_info[key] is not None:
                    packet_info[key] = ''.join([char.upper() if char.isalpha() and char != 'x' else char for char in packet_info[key]])                
                
            # Store the packet info in the dictionary, using packet number as the key
            uds_packets[packet.number] = packet_info
    
    capture.close()  # Close the capture
    
    return pd.DataFrame(uds_packets).T.sort_values(by='number').reset_index(drop=True)


def combine_request_reply(df: pd.DataFrame) -> pd.DataFrame:
    """Combines request SIDs, reply SIDs, and errors (if present) into single row in a DataFrame. Replies are matched 
    to requests based on the source and target addresses, conditional on the reply having a higher packet number than 
    the request.

    Args:
        df (pd.DataFrame): DataFrame of PCAP file, with replies and requests in separate rows

    Returns:
        pd.DataFrame: DataFrame with combined requests and replies, with columns:
            - ecu_address: ECU address
            - request_sid: Service ID of the request
            - reply_sid: Service ID of the reply
            - error: Description of the error code (if present, else 'No error')
            - request_description: Description of the request SID
            - reply_description: Description of the reply SID
            - error_description: Description of the error code (if present, else None)
    """
    requests = df[df['request'] == True].drop(columns=['source', 'request', 'error'])
    replies = df[df['request'] == False].drop(columns=['target', 'request'])

    combined = []

    for _, request in requests.iterrows():

        # Match the request with the corresponding reply
        request_sid = request['sid']
        expected_reply_sid = f"0x{(int(request_sid, 16) + 0x40):X}"  # positive reply code
        expected_error_sid = "0x7F"  # negative reply code

        reply = replies[(replies['source'] == request['target']) &
                        (request['number'] < replies['number']) & 
                        (replies['sid'].isin([expected_reply_sid, expected_error_sid]))].head(1)\
                            [['source', 'sid', 'error', 'timestamp']] # presorted on packet number so the first reply is the one we want
        
        if reply.empty:  # no corresponding reply found, so engineer a response too long error
            
            reply = pd.DataFrame({'source': [request['target']], 
                                  'sid': None,  # p6 timing response too long
                                  'error': 'p6 parameter timout',  # p6 timing response too long 
                                  'timestamp': pd.NaT})
        
        else:
            # Drop reply from the replies dataframe, if there was a normal match
            replies = replies.drop(reply.index)
            
        combined.append([reply['source'].values[0], request['sid'], reply['sid'].values[0], reply['error'].values[0]])
    
    reply_request = pd.DataFrame(combined, columns=['ecu_address', 'request_sid', 'reply_sid', 'error'])
    
    # Merge SID descriptions
    reply_request = merge_sid_description(reply_request)
    
    # Merge NRC descriptions (if present)
    if reply_request['error'].notnull().mean() > 0:
    
        reply_request = merge_nrc_description(reply_request)
    
    else:
        reply_request['error'] = 'No error'
    
    return reply_request

def merge_sid_description(df: pd.DataFrame) -> pd.DataFrame:
    """Merges the service ID descriptions from the UDS database table. Rows with no SID codes are filled with 
    'Unknown Request/Reply'.

    Args:
        df (pd.DataFrame): DataFrame with service IDs

    Returns:
        pd.DataFrame: DataFrame with descriptions of the service IDs, in addition to the codes themselves
    """
    # Load the service IDs from the SQLite database
    conn = sqlite3.connect('uds/uds_codes.db')
    sid_codes = pd.read_sql_query("SELECT * FROM sid;", conn)
    
    # Merge the service description with request_sid
    df = df.merge(sid_codes, left_on='request_sid', right_on='Code', how='left')\
        .rename(columns={'Description': 'request_description'}).drop(columns='Code')
    df['request_description'] = df['request_description'].fillna('Unknown Request')
    
    # Merge the service description with reply_sid
    df = df.merge(sid_codes, left_on='reply_sid', right_on='Code', how='left')\
        .rename(columns={'Description': 'reply_description'}).drop(columns='Code')
    df['reply_description'] = df['reply_description'].fillna('Unknown Reply')
    
    # If reply_sid is None, this means an ECU timeout, so fill in 'Timeout: No Reply'
    df['reply_description'] = np.where(df['reply_sid'].isnull(), 'Timeout: No Reply', df['reply_description'])

    return df
    

def merge_nrc_description(df: pd.DataFrame) -> pd.DataFrame:
    """Merges the negative response description from the lookup table. Any missing NRC codes are filled
    with 'Unknown error'. Rows with no NRC codes are filled with 'No error'.

    Args:
        df (pd.DataFrame): DataFrame with error codes

    Returns:
        pd.DataFrame: DataFrame with descriptions of the error codes rather than the codes themselves
    """
    # Load the negative response codes from the SQLite database
    conn = sqlite3.connect('uds/uds_codes.db')
    nrc_codes = pd.read_sql_query("SELECT * FROM nrc;", conn)
    
    # Merge the error codes with the negative response codes
    df = df.merge(nrc_codes, left_on='error', right_on='Code', how='left')
    
    # Error codes with no match in db, fill with 'unknown error'
    # Also replaces info from 'Description' column in 'error' column
    df['error'] = np.where((df['reply_sid']=='0x7F') & (df['Description'].isnull()), 'Unknown error', df['error'])
    
    # Fill in missing error descriptions
    df['error'] = df['error'].fillna('No error')
    
    return df.drop(columns=['Code', 'Description'])


def convert_session_log_to_str(df: pd.DataFrame) -> str:
    """ Converts session log from pd.DataFrame to string format.

    Args:
        df (pd.DataFrame): Dataframe where each row represents a single request-reply pair, ecu address and error code.

    Returns:
        str: string representation of the session log
    """
    session_log = ""

    for _, row in df.iterrows():

        ecu = row['ecu_address']
        request_sid = row['request_sid']
        request_description = row['request_description']
        reply_sid = row['reply_sid']
        reply_description = row['reply_description']
        error = row['error']
        
        session_log += f"ECU '{ecu}': SID {request_sid} ({request_description}) -> SID {reply_sid} ({reply_description}) // {error}\n"
    
    return session_log

def pcap_transformation_wrapper(file_path: str) -> pd.DataFrame:
    """Wrapper function to transform a pcap file into a Pandas DataFrame

    Args:
        file_path (str): string path to the pcap file

    Returns:
        df: DataFrame representation of the pcap session log
    """
    df = asyncio.run(read_pcap_file(file_path))
    df = combine_request_reply(df)

    return df

def instantiate_llm(model: str = "gpt-4o") -> ChatOpenAI:
    """Instantiates the Langchain AzureChatOpenAI model.
    
    Args: 
        model (str): The model to use. Defaults to "gpt-4o".

    Returns:
        AzureChatOpenAI: Langchain OpenAI model
    """
    # Load environment variables from .env file
    load_dotenv()
    
    return ChatOpenAI(
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"), 
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        deployment_name=model,
        api_version="2024-02-01"
    )