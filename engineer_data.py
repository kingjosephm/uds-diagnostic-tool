import os
import json
import pyshark


if __name__ == '__main__':
    
    dir_contents = [i for i in os.listdir("./data") if ".pcap" in i]
    
    for file in dir_contents:
    
        capture = pyshark.FileCapture(f"./data/{file}", include_raw=True, use_json=True)
        
        uds_packets = {}
        
        # Iterate through each packet
        for packet in capture:
            # Check if the packet has the ISO-TP or UDS layer
            if hasattr(packet, 'isotp') or hasattr(packet, 'uds'):
                packet_info = {
                    'timestamp': packet.sniff_time.strftime("%Y-%m-%d %H:%M:%S"),  # Time of packet capture
                    'source': packet.ip.src if hasattr(packet, 'ip') else 'N/A',  # Source IP if present
                    'destination': packet.ip.dst if hasattr(packet, 'ip') else 'N/A',  # Destination IP if present
                    # Extract data from the appropriate layer
                    #'data': packet.isotp_raw if hasattr(packet, 'isotp') else (packet.uds_raw if hasattr(packet, 'uds') else 'N/A')
                    'data': packet.uds_raw.value
                }
                
                # Store the packet info in the dictionary, using packet number as the key
                uds_packets[packet.number] = packet_info
    
        with open(f"./data/{file.strip('.pcap')}.json", 'w') as f:
            json.dump(uds_packets, f)
            
        # Close the capture once done
        capture.close()