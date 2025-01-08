import os
import pyshark
import pandas as pd



if __name__ == '__main__':
    
    dir_contents = [i for i in os.listdir("./data") if ".pcap" in i]
    
    for file in dir_contents:
    
        capture = pyshark.FileCapture(f"./data/{file}", include_raw=True, use_json=True)
        
        uds_packets = {}
        
        # Iterate through each packet
        for packet in capture:
            
            if packet.highest_layer.split('_')[0] in ['UDS']:
                
                packet_info = {
                    'number': packet.number,  # Packet number
                    'timestamp': packet.sniff_time.strftime("%Y-%m-%d %H:%M:%S"),  # Time of packet capture
                    'protocol': packet.highest_layer.split('_')[0],  # overall protocol
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
            
        df = pd.DataFrame(uds_packets).T
        df.to_excel(f"./data/{file.split('.')[0]}.xlsx", index=False)
        
            
        # Close the capture once done
        capture.close()