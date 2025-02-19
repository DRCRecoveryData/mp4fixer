import os
import random

block = 2000000  # size of block
block_count = 35  # how many pieces you want

# change file paths
input_file = 'some_good_pron.mp4'
output_file = 'montage2.bad'

with open(input_file, 'rb') as dd, open(output_file, 'wb') as oo:
    size = os.path.getsize(input_file)
    
    for _ in range(block_count):
        dd.seek(random.randint(0, size - block))
        file_data = dd.read(block)
        oo.write(file_data)
