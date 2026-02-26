# CSULB Smart Parking - RPC System

A concurrent parking management system utilizing a custom-built Remote Procedure Call (RPC) layer over TCP sockets. This system allows clients to query lot availability and manage reservations in a multithreaded environment.

## 1. Environment & Dependency Setup

### Create Virtual Environment
bash
''' python -m venv .venv 

### Activate Environment:
macOS/linux
''' bash
source .venv/bin/activate
Windows:
''' bash
.venv\scripts\activate

pip install -r requirements.txt

## 2. RPC Layer Specification
Framing and Marshalling
Framing: Every message is prefixed with a 4-byte unsigned integer (Big-Endian/Network Byte Order) representing the length of the payload in bytes. This prevents "message sticking" in the TCP stream.

Marshalling (Wire Format): Data is serialized into JSON format for platform independence.

Parameter Passing: Arguments are passed by value via JSON serialization.

Message Schemas
# Request Object:
{ 
  "rpcId": 12345,
  "method": "methodName",
  "args": ["arg1", "arg2"]
}
# Reply Object
{
  "rpcId": 12345,
  "result": "returnValue",
  "error": null
}
# RPC Path
The communication flow follows the standard RPC lifecycle:
Caller → Client Stub → TCP Socket → Server Skeleton → Internal Method → Return Value → Server Skeleton → TCP → Client Stub → Caller

## 3. Server Architecture
Threading Model
Model: Bounded Thread Pool.

Implementation: The server utilizes a ThreadPoolExecutor to handle concurrent client connections.

Reasoning: A thread pool limits the maximum number of active threads, preventing resource exhaustion while allowing multiple clients to process RPC requests simultaneously.

Concurrency and State
State Management: All parking lot data (occupancy, capacity, and reservation lists) is stored in-memory.

Synchronization: Shared data is protected by a threading.Lock() to ensure that operations like RESERVE remain atomic and prevent overbooking under high concurrent load.

Timeout Policy
The client-side stub enforces a 5.0 second timeout for all network operations. If the server does not respond within this window, a TimeoutError is raised.

## 4. Execution
Start the server: python server.py

Run the client: python client.py


### Next Step for you:
I've created an empty **requirements.txt** file below. You should save this in your project folder alongside the README to ensure you meet the "reproducible dependency specification" requirement.

**requirements.txt**
```text
# This project uses only the Python Standard Library.
# No external dependencies required.
