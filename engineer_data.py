import os
import pyshark
import pandas as pd



if __name__ == '__main__':
    
    restrict_uds_only = False
    
    dir_contents = [i for i in os.listdir("./data") if ".pcap" in i]
    
    for file in dir_contents:
    
        capture = pyshark.FileCapture(f"./data/{file}", include_raw=True, use_json=True)
        
        uds_packets = {}
        
        # Iterate through each packet
        for packet in capture:
            
            if packet.highest_layer.split('_')[0] in ['DOIP', 'UDS']:
                
                
                packet_info = {
                    'number': packet.number,  # Packet number
                    'timestamp': packet.sniff_time.strftime("%Y-%m-%d %H:%M:%S"),  # Time of packet capture
                    'protocol': packet.highest_layer.split('_')[0],  # overall protocol
                    'length': packet.length,
                    'source': packet.doip.source_address if hasattr(packet.doip, 'source_address') else 'N/A',
                    'target': packet.doip.target_address if hasattr(packet.doip, 'target_address') else 'N/A',
                    'doip': packet.doip_raw.value,
                    'uds': packet.uds_raw.value if hasattr(packet, 'uds_raw') else 'N/A'
                }
                
                # Separate the DOIP and UDS data into bytes
                for key in ['doip', 'uds']:
                    packet_info[key] = ':'.join([packet_info[key][i:i+2] for i in range(0, len(packet_info[key]), 2) if packet_info[key] != 'N/A'])
                
                
                # Store the packet info in the dictionary, using packet number as the key
                uds_packets[packet.number] = packet_info
            
        df = pd.DataFrame(uds_packets).T
        df['uds'] = df['uds'].replace('', 'N/A')
        df.to_excel(f"./data/{file.strip('.pcap')}.xlsx", index=False)
        
            
        # Close the capture once done
        capture.close()