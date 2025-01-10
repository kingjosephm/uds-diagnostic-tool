import pandas as pd
import pyshark


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
                'timestamp': packet.sniff_time.strftime("%Y-%m-%d %H:%M:%S"),  # Time of packet capture
                'source': packet.doip.source_address if hasattr(packet.doip, 'source_address') else 'N/A',
                'target': packet.doip.target_address if hasattr(packet.doip, 'target_address') else 'N/A',
                'request': True if packet.uds.reply == '0x00' else False,  # misnomer, this is request code if '0x00'. Reply codes are '0x01'
                'sid': 'N/A',  # Service ID, fill in below
                'error': 'N/A',  # alter below, if present
            }
            
            if packet_info['request']:
                packet_info['sid'] = packet.uds.sid
            else:  # reply code
                packet_info['sid'] = hex(int(packet.uds.sid, 16) + 0x40)  # must add '0x40' to get correct reply code for both positive and negative replies
                if hasattr(packet.uds, 'err'):
                    packet_info['error'] = packet.uds.err.code  # negative reply error code. This is second byte of the negative reply shown in CloudShark. Ignore first byte of negative reply code for now since this not standardized
            
            # Capitalize the letters in the SID and Reply fields
            for key in ['sid', 'error']:  # assumes only one byte
                if packet_info[key] != 'N/A':
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
            - request_sid: Service ID of the request
            - reply_sid: Service ID of the reply
            - error: Error code (if present)
    """
    requests = df[df['request'] == True].copy()
    replies = df[df['request'] == False].copy()

    combined = []

    for _, request in requests.iterrows():

        reply = replies[(replies['source'] == request['target']) &
                        (request['number'] < replies['number'])].head(1)\
                            [['source', 'sid', 'error']]  # presorted on packet number so the first reply is the one we want
        
        if reply.empty:  # no corresponding reply found
            continue
        else:
            # Drop reply from the replies dataframe
            replies = replies.drop(reply.index)
            
            combined.append([reply['source'].values[0], request['sid'], reply['sid'].values[0], reply['error'].values[0]])
    
    return pd.DataFrame(combined, columns=['ecu_address', 'request_sid', 'reply_sid', 'error'])