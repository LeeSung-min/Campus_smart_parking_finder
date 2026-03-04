import socket
import json
import threading
import parking_data
import queue

# worker loops waiting for a task
def worker(car_queue, parking):
    while True:
        conn, addr = car_queue.get()
        try:
            handle_client(conn, addr, parking)
        finally:
            car_queue.task_done()

def start_pool(pool, queue_limit, parking):
    #create the worker queue
    car_queue = queue.Queue(maxsize= queue_limit)

    for i in range(pool):
        car = threading.Thread(target= worker, args= (car_queue, parking), daemon= True)
        car.start()

    return car_queue

def start_server(host, port, backlog, car_queue):
    #create socket to listen for clients

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(backlog)

    print(f"Server Connected - host: {host}, port: {port}")

    # accept connections until queue is filled out
    while True:
        conn, addr = server.accept()

        try:
            car_queue.put_nowait((conn,addr))
        except queue.Full:
            try:
                conn.sendall(b"Queue is FULL\n")
            except Exception:
                pass
            conn.close()


def handle_client(conn, addr, parking):
    
    #store partial messages in a buffer till seeing \n
    msg_buffer = ""

    with conn:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            msg_buffer += data.decode("utf-8")

            #split full message once seeing \n
            while "\n" in msg_buffer:
                line, msg_buffer = msg_buffer.split("\n", 1)
                line = line.strip()
                #handle empty line
                if line == "":
                    continue
                
                response = cmd_protocol(line, parking)
                conn.sendall((response + "\n").encode("utf-8"))
    
    try: 
        conn.close()
    except Exception:
        pass

def cmd_protocol(line, parking):
    parts = line.split()

    if len(parts) == 0:
        return "Invalid Request"
    
    cmd = parts[0]

    if cmd == "LOTS" and len(parts) == 1:
        lots = parking.getLots()
        return json.dumps(lots)

    if cmd == "AVAIL" and len(parts) == 2:
        lotId = parts[1]
        
        try: 
            free = parking.getAvailability(lotId)
            return str(free)
        except KeyError:
            return "Invalid lot"
       
    if cmd == "RESERVE" and len(parts) == 3:
        lotId = parts[1]
        plate = parts[2]

        try:
            return parking.reserve(lotId,plate)
        except KeyError:
            return "Invalid lot"

    if cmd == "CANCEL" and len(parts) == 3:
        lotId = parts[1]
        plate = parts[2]

        try:
            return parking.cancel(lotId, plate)
        except KeyError:
            return "Invalid lot"

    if cmd == "PING" and len(parts) == 1:
        return "PONG"
            
    # if none of these messages matched return error as well
    return "Invalid request"

def main():
    #load config 
    with open("config.json", "r") as f:
        config = json.load(f)

    host = config.get("host")
    port = int(config.get("server_port"))
    parking = parking_data.Parking(config["lots"], config["ttl"])
    
    #chose pool size of 4 since the tests given in the assignment were small amount of parallel client workers 1/4/8/16, so having a smaller
    #pool size, we could check for the back pressure
    backlog = int(config.get("backlog"))
    pool = int(config.get("pool_size"))
    queue_limit = int(config.get("queue_limit"))

    car_queue = start_pool(pool, queue_limit, parking)
    start_server(host, port, backlog, car_queue)

    # use thread pool to handle large amount of clients instead of thread per connection, where too many threads will cause performance issues

if __name__ == "__main__":
    main()
