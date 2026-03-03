import socket
import json
import threading
import parking_data
import queue

def worker():
    while True:
        conn, addr = 


def main():
    #load config 
    with open("config.json", "r") as f:
        config = json.load(f)

    port = config["server_port"]
    parking = parking_data.Parking(config["lots"], config["ttl"])

    # use thread pool to handle large amount of clients instead of thread per connection
    pool
