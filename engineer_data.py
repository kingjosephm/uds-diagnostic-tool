import pandas as pd
from pandas import json_normalize
import os
import json

pd.set_option('display.max_columns', 200)
pd.set_option('display.max_rows', 100) 

if __name__ == '__main__':
    
    dir_contents = [i for i in os.listdir("./data") if ".json" in i]
    
    for file in dir_contents:
        
        with open(f"./data/{file}") as f:
            data = json.load(f)
        
        assert isinstance(data, list), f"{file} is not a list!"
        
        df = pd.DataFrame()
        for elem in data:
            row = json_normalize(elem['_source']['layers'])
            df = pd.concat([df, row], ignore_index=True)
        
        df.to_csv(f"./data/{file.split('.')[0]}.csv", index=False)