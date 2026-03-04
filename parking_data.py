import threading
import dataclasses
import time

# create a parking lot class
@dataclasses.dataclass
class Lot:
    id       : str
    capacity : int
    occupied : int = 0

    @property
    def free(self):
        return self.capacity - self.occupied
    
    # dict of reservations [id, time], new dict created for each instance of Lot
    reservations : dict[str, float] = dataclasses.field(default_factory=dict)

# implement methods for the lot: 
class Parking:
   
    def __init__(self, lots: list[dict], ttl: int):
        self.lots = {}

        for lot in lots:
            id = lot["id"]
            capacity = lot ["capacity"]

            new_lot  = Lot(id, capacity, 0)

            self.lots[id] = new_lot

        self.lock = threading.Lock()
        self.ttl = ttl


    def expire_res(self, lot: Lot):
        #remove reservations when res time hits 5 min for this assignment
        current_time = time.time()
        expired_plates = []

        for (plate, expire_time) in lot.reservations.items():
            if current_time >= expire_time:
                expired_plates.append(plate)
        
        for plate in expired_plates:
            del lot.reservations[plate]
            #check if occupancy goes below 0 
            lot.occupied -= 1

            if lot.occupied < 0:
                raise RuntimeError("expire res - occupancy below 0")

    def getLots(self):
        #return lots with format: {id, capacity, occupied, available}
        with self.lock:
            lot_data = []

            for lot in self.lots.values():
                #get rid of expired resy
                self.expire_res(lot)
                lot_data.append({
                    "id": lot.id,
                    "capacity": lot.capacity,
                    "occupied": lot.occupied,
                    "free": lot.free
                })

            return lot_data

    def getAvailability(self, lotId) -> int:
        #return the free spots in a give lot
        with self.lock:
            if lotId not in self.lots:
                raise KeyError("Invalid Lot id")
            
            lot = self.lots[lotId]
            #clear expired resy
            self.expire_res(lot)
            return lot.free

    def reserve(self, lotId, plate): # return OK|FULL|EXISTS
        with self.lock:
            if lotId not in self.lots:
                raise KeyError("Invalid lot id")
            
            lot = self.lots[lotId]

            #clear expired res and check if lot is full
            self.expire_res(lot)
            if lot.occupied >= lot.capacity:
                return "FULL"
            
            #check if plate already exists
            if plate in lot.reservations:
                return "EXISTS"
            
            #successful reservation, store timestamp
            lot.occupied += 1
            lot.reservations[plate] = time.time() + self.ttl

            return f"OK"

    def cancel(self, lotId, plate): #return OK | NOT_FOUND
        with self.lock:
            if lotId not in self.lots:
                raise KeyError("Invalid lot id")
            
            lot = self.lots[lotId]

            #remove exp and check for not found
            self.expire_res(lot)
            if plate not in lot.reservations:
                return "NOT_FOUND"
            
            del lot.reservations[plate]
            lot.occupied -= 1
            
            # check cancel edge case
            if lot.occupied < 0:
                raise RuntimeError("cancel - occupancy below 0")

            return "OK"
        
