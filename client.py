from rpc_framework import ParkingClientStub

# This part doesn't care ABOUT sockets or JSON. It just calls functions.
stub = ParkingClientStub()

print("Checking availability...")
spots = stub.getAvailability("Lot_A")
print(f"Spots available: {spots}")

print("Attempting reservation...")
success = stub.reserve("Lot_A", "BEAU-2026")
if success:
    print("Success! Parking secured.")
else:
    print("Lot is full!")
