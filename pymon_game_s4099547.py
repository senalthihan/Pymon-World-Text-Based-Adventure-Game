
"""



@author: dipto
@student_id : s4099547 (Senal Edirisinghe)
@highest_level_attempted: Stage 4

- Reflection:
  This program was developed iteratively from the given skeleton. I preserved the
  original class names and extended them to cover all features from Stage 1 to 4:
  — Stage 1: Map + movement + menu; load locations/creatures from CSV.
  — Stage 2: Items + inventory + challenge (race) + swap.
  — Stage 3: Energy system + item usage (Apple, Pogo stick, Binocular) + exceptions.
  — Stage 4: Save/Load (single CSV), race stats, admin features.

The program meets all Stage 1–4 requirements; however, a few minor limitations remain. T
he CSV import functions for locations.csv and items.csv require exact header names, while only creatures.csv 
supports flexible spacing and casing. Admin-created locations and creatures exist only in memory and are not 
written back to the base CSV files. Race statistics are saved separately in race_stats.txt and not embedded in the 
main save file. Loading a save mid-session may duplicate some entities, and the race loop pauses execution due to 
time.sleep. These issues do not affect normal gameplay or the core functionality required by the assignment.

References
OpenAI (2025) ChatGPT (GPT 5 version) [Large language model], accessed 1 November 2025.
"""

import sys
import os
import csv
import random
import time
from typing import Optional

#
# Utilities


# you may use, extend and modify the following random generator
def generate_random_number(max_number = 1):
    r = random.randint(0,max_number)
    return r


# Exceptions


class InvalidDirectionException(Exception): ...
class InvalidInputFileFormat(Exception): ...
class GameOver(Exception): ...


# Domain models


class Item:
    """Simple item template/instance."""
    def __init__(self, name: str, description: str, pickable: bool, consumable: bool):
        self.name = name
        self.description = description
        self.pickable = pickable
        self.consumable = consumable

    def __str__(self):
        flags = []
        if self.pickable: flags.append("pickable")
        if self.consumable: flags.append("consumable")
        return f"{self.name} ({', '.join(flags)}) — {self.description}"


class Creature:
    """Non-player creature. If adoptable=True, it can be captured (becomes a Pymon in team)."""
    def __init__(self, nickname: str, description: str, adoptable: bool, speed: float, location: Optional['Location']=None):
        self.nickname = nickname
        self.description = description
        self.adoptable = adoptable
        self.speed = float(speed) if speed is not None else 0.0
        self.location = location

    def __str__(self):
        loc = self.location.name if self.location else "Unknown"
        tag = "Pymon" if self.adoptable else "Animal"
        return f"{self.nickname} [{tag}] — {self.description} @ {loc}"


class Pymon:
    """Player-controlled Pymon with energy, speed, inventory and movement."""
    def __init__(self, name = "The player", description: str="player Pymon", speed: float=5.0):
        self.name = name
        self.description = description
        self.current_location: Optional['Location'] = None
        self.energy_max = 3
        self.energy = 3
        self.speed = float(speed)
        self.inventory: list[Item] = []
        self._pogo_armed = False  # doubles actual speed in the next race only

    def move(self, direction = None):
        direction = (direction or "").lower()
        if direction not in ("west","north","east","south"):
            raise InvalidDirectionException("Invalid direction keyword.")
        if self.current_location is not None:
            nxt = self.current_location.doors.get(direction)
            if nxt is not None:
                # move lists
                if self in self.current_location.creatures:
                    self.current_location.creatures.remove(self)
                nxt.add_creature(self)
                self.current_location = nxt
            else:
                print("no access to " + direction)

    def spawn(self, loc: 'Location'):
        if loc is not None:
            loc.add_creature(self)
            self.current_location = loc

    def get_location(self):
        return self.current_location

    #  items 
    def arm_pogo(self):
        self._pogo_armed = True

    def consume_apple(self):
        if self.energy < self.energy_max:
            self.energy += 1

    def use_binocular(self) -> str:
        here = self.current_location
        if not here:
            return "Unknown location."
        lines = []
        lines.append(f"[Here] {here.name}: {here.description}")
        if here.creatures:
            lines.append("  Creatures: " + ", ".join([getattr(c,'nickname', getattr(c,'name','?')) for c in here.creatures if c is not self]))
        if here.items:
            lines.append("  Items: " + ", ".join([i.name for i in here.items]))
        for d in ("west","north","east","south"):
            nxt = here.doors.get(d)
            if nxt:
                lines.append(f"[{d}] {nxt.name}: {nxt.description}")
                if nxt.creatures:
                    lines.append("  Creatures: " + ", ".join([getattr(c,'nickname', getattr(c,'name','?')) for c in nxt.creatures]))
                if nxt.items:
                    lines.append("  Items: " + ", ".join([i.name for i in nxt.items]))
        return "\n".join(lines)


class Location:
    """A map node with up to 4 connections, creatures and items."""
    def __init__(self, name = "New room", w = None, n = None , e = None, s = None, description: str=""):
        self.name = name
        self.description = description
        self.doors: dict[str, Optional['Location']] = {}
        self.doors["west"] = w
        self.doors["north"] = n
        self.doors["east"] = e
        self.doors["south"] = s
        self.creatures: list = []
        self.items: list[Item] = []

    def add_creature(self, creature):
        # append a creature to this room and set location
        self.creatures.append(creature)
        if isinstance(creature, (Pymon, Creature)):
            creature.location = self

    def add_item(self, item: Item):
        self.items.append(item)

    def connect_east(self, another_room):
        self.doors["east"] = another_room
        another_room.doors["west"]  = self

    def connect_west(self, another_room):
        self.doors["west"] = another_room
        another_room.doors["east"]  = self

    def connect_north(self, another_room):
        self.doors["north"] = another_room
        another_room.doors["south"]  = self

    def connect_south(self, another_room):
        self.doors["south"] = another_room
        another_room.doors["north"]  = self

    def get_name(self):
        return self.name


# Persistence / Game data


class Record:
    def __init__(self):
        # collections indexed by name
        self.locations_by_name: dict[str, Location] = {}
        self.creatures_by_name: dict[str, Creature] = {}
        self.items_catalog: dict[str, Item] = {}

    # CSV loaders 
    def import_location(self, filepath: Optional[str]=None):
        """
        Import data from locations.csv.
        Columns: name, description, west, north, east, south
        Two-pass: create nodes, then connect.
        """
        path = filepath or ("locations.csv" if os.path.exists("locations.csv") else "/mnt/data/locations.csv")
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected = {"name","description","west","north","east","south"}
            headers = set(reader.fieldnames or [])
            if headers != expected:
                raise InvalidInputFileFormat(f"locations.csv header must be {expected}")
            rows = [row for row in reader]

        for r in rows:
            name = r["name"].strip()
            desc = (r["description"] or "").strip()
            self.locations_by_name[name] = Location(name, description=desc)

        for r in rows:
            here = self.locations_by_name[r["name"].strip()]
            for d in ("west","north","east","south"):
                other_name = (r[d] or "").strip()
                if other_name and other_name != "None":
                    other = self.locations_by_name.get(other_name)
                    if not other:
                        raise InvalidInputFileFormat(f"Unknown location '{other_name}' referenced in {d}")
                    # connect both sides if not already
                    if here.doors[d] is None:
                        if d == "west":
                            here.connect_west(other)
                        elif d == "east":
                            here.connect_east(other)
                        elif d == "north":
                            here.connect_north(other)
                        elif d == "south":
                            here.connect_south(other)

    

    def import_creatures(self, filepath: Optional[str]=None):
        """
        creatures.csv cols (flexible): nickname|name, description, adoptable, speed
        Accepts extra spaces or case differences in headers.
        """
        path = filepath or ("creatures.csv" if os.path.exists("creatures.csv") else "/mnt/data/creatures.csv")

        with open(path, newline="", encoding="utf-8") as f:
            # Read and normalize header names
            raw_header = f.readline()
            if not raw_header:
                raise InvalidInputFileFormat("creatures.csv is empty.")
            headers = [h.strip().lower() for h in raw_header.strip().split(",")]

            # Map to header keys
            canon = []
            for h in headers:
                if h in ("nickname", "name"):
                    canon.append("nickname")
                elif h == "description":
                    canon.append("description")
                elif h == "adoptable":
                    canon.append("adoptable")
                elif h == "speed":
                    canon.append("speed")
                else:
                    canon.append(h)

            # Read the remaining rows
            rows = []
            for line in f:
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.rstrip("\n").split(",")]
                rec = {}
                for i, key in enumerate(canon):
                    if i < len(parts):
                        rec[key] = parts[i]
                rows.append(rec)

        # Validate required keys
        required = {"nickname", "description", "adoptable", "speed"}
        if not required.issubset(set(canon)):
            raise InvalidInputFileFormat(f"creatures.csv header mismatch. Got: {set(canon)} need at least {required}")

        # Build creatures
        for row in rows:
            nickname = (row.get("nickname") or "").strip()
            if not nickname:
                continue
            desc = (row.get("description") or "").strip()
            adoptable = (row.get("adoptable") or "").strip().lower() in ("yes", "true", "1", "y", "t")
            try:
                spd = float(row.get("speed") or 0.0)
            except ValueError:
                spd = 0.0
            c = Creature(nickname, desc, adoptable, spd)
            self.creatures_by_name[nickname] = c



    def import_items(self, filepath: Optional[str]=None):

        """
        items.csv cols: name, description, pickable, consumable
        """
        path = filepath or ("items.csv" if os.path.exists("items.csv") else "/mnt/data/items.csv")
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected = {"name","description","pickable","consumable"}
            if set(reader.fieldnames or []) != expected:
                raise InvalidInputFileFormat("items.csv header mismatch.")
            for row in reader:
                name = (row["name"] or "").strip()
                desc = (row["description"] or "").strip()
                pickable = (row["pickable"] or "").strip().lower() in ("yes","true","1","y","t")
                consumable = (row["consumable"] or "").strip().lower() in ("yes","true","1","y","t")
                self.items_catalog[name] = Item(name, desc, pickable, consumable)

    # Save/Load single-file
    def save_game(self, filepath: str, current_name: str, bench_names: list[str]):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["role","name","type","location","energy","inventory","is_current","is_benched"])
            for name, c in self.creatures_by_name.items():
                loc = c.location.name if getattr(c,"location",None) else ""
                typ = "Pymon" if isinstance(c, Pymon) or getattr(c,"adoptable",False) else "Animal"
                energy = ""
                inv = ""
                if isinstance(c, Pymon):
                    energy = str(c.energy)
                    inv = ";".join([i.name for i in c.inventory])
                w.writerow(["entity", name, typ, loc, energy, inv, "yes" if name==current_name else "no", "yes" if name in bench_names else "no"])

    def load_game(self, filepath: str):
        current_name = None
        bench = []
        with open(filepath, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            expected = {"role","name","type","location","energy","inventory","is_current","is_benched"}
            if set(r.fieldnames or []) != expected:
                raise InvalidInputFileFormat("Save file header mismatch.")
            rows = [row for row in r]

        # ensure entries exist
        for row in rows:
            nm = row["name"].strip()
            typ = row["type"].strip()
            if nm not in self.creatures_by_name:
                if typ == "Pymon":
                    self.creatures_by_name[nm] = Pymon(nm, "(custom)", 5.0)
                else:
                    self.creatures_by_name[nm] = Creature(nm, "(custom)", False, 0.0)

        # apply
        for row in rows:
            nm = row["name"].strip()
            locn = (row["location"] or "").strip()
            c = self.creatures_by_name[nm]
            loc = self.locations_by_name.get(locn) if locn else None
            if loc:
                loc.add_creature(c)
            if isinstance(c, Pymon):
                try:
                    c.energy = int(row["energy"] or "3")
                except:
                    c.energy = 3
                c.inventory = []
                inv = (row["inventory"] or "").strip()
                if inv:
                    for iname in inv.split(";"):
                        iname = iname.strip()
                        tpl = self.items_catalog.get(iname)
                        if tpl:
                            c.inventory.append(Item(tpl.name, tpl.description, tpl.pickable, tpl.consumable))
            if (row["is_current"] or "").lower().startswith("y"):
                current_name = nm
            if (row["is_benched"] or "").lower().startswith("y"):
                bench.append(nm)

        return current_name, bench


#UI


class Operation:
    def handle_menu(self):
        print("Please issue a command to your Pymon:")
        print("1) Inspect Pymon")
        print("2) Inspect current location")
        print("3) Move")
        print("4) Pick up item")
        print("5) View inventory / Use item")
        print("6) Challenge a creature (race)")
        print("7) Swap current Pymon")
        print("8) Save game")
        print("9) Load game")
        print("10) Show race stats")
        print("11) Admin features")
        print("0) Exit the program")

    def __init__(self, loc_file: Optional[str]=None, cre_file: Optional[str]=None, item_file: Optional[str]=None):
        self.locations: list[Location] = []
        self.current_pymon = Pymon("Toromon", "white and yellow Pymon with a square face", speed=5.0)
        self.bench: list[Pymon] = []
        self.record = Record()
        self._move_counter = 0
        self.stats_path = "race_stats.txt"
        self.stats = {}

        # detect files (CLI or defaults)
        self.loc_file = loc_file or (sys.argv[1] if len(sys.argv)>=2 else None)
        self.cre_file = cre_file or (sys.argv[2] if len(sys.argv)>=3 else None)
        self.item_file = item_file or (sys.argv[3] if len(sys.argv)>=4 else None)

    # Setup & placement
    def setup(self):
        self.record.import_location(self.loc_file)
        self.record.import_creatures(self.cre_file)
        self.record.import_items(self.item_file)

        # fill self.locations list
        for loc in self.record.locations_by_name.values():
            self.locations.append(loc)

        # Stage 1 spawn: Toromon @ School
        school = self.record.locations_by_name.get("School")
        if not school:
            raise InvalidInputFileFormat("Required location 'School' missing in locations.csv")
        self.current_pymon.spawn(school)
        self.record.creatures_by_name[self.current_pymon.name] = self.current_pymon

        # place creatures as per spec examples
        def place(cre_name, loc_name):
            c = self.record.creatures_by_name.get(cre_name)
            loc = self.record.locations_by_name.get(loc_name)
            if c and loc:
                loc.add_creature(c)
        place("Kitimon","Playground")
        place("Sheep","Beach")
        place("Marimon","School")

        # Stage 2: initial items on ground
        def drop(iname, lname):
            # case-insensitive lookup, supports partial match too
            key = next((k for k in self.record.items_catalog.keys()
                if k.lower() == iname.lower() or iname.lower() in k.lower()), None)
            tpl = self.record.items_catalog.get(key) if key else None
            loc = self.record.locations_by_name.get(lname)
            if tpl and loc:
                loc.add_item(Item(tpl.name, tpl.description, tpl.pickable, tpl.consumable))

        drop("Apple","Beach")
        drop("Pogo stick","Playground")
        drop("Binocular","School")

        self._load_stats()

    def display_setup(self):
        for location in self.locations:
            print(location.name + " has the following creatures:")
            for creature in location.creatures:
                nm = getattr(creature,'nickname', getattr(creature,'name','?'))
                print(nm)

    # loop helpers
    def _decrement_energy_if_due(self):
        if self._move_counter % 2 == 0 and self._move_counter > 0:
            self.current_pymon.energy -= 1
            print(f"Your Pymon feels tired. Energy now {self.current_pymon.energy}/{self.current_pymon.energy_max}.")
            if self.current_pymon.energy <= 0:
                # current escapes
                loc = self.current_pymon.current_location
                if loc and self.current_pymon in loc.creatures:
                    loc.creatures.remove(self.current_pymon)
                print(f"Oh no! {self.current_pymon.name} ran away due to exhaustion.")
                if self.bench:
                    self.current_pymon = self.bench.pop(0)
                    print(f"{self.current_pymon.name} steps in from the bench!")
                else:
                    raise GameOver()

    def _load_stats(self):
        self.stats = {}
        if not os.path.exists(self.stats_path):
            return
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                for line in f:
                    line=line.strip()
                    if not line: continue
                    parts = line.split(",")
                    if len(parts)==4:
                        n,w,l,d = parts
                        self.stats[n] = {"W":int(w),"L":int(l),"D":int(d)}
        except: pass

    def _save_stats(self):
        with open(self.stats_path, "w", encoding="utf-8") as f:
            for n, rec in sorted(self.stats.items()):
                f.write(f"{n},{rec.get('W',0)},{rec.get('L',0)},{rec.get('D',0)}\n")

    def _bump_stat(self, name: str, key: str):
        self.stats.setdefault(name, {"W":0,"L":0,"D":0})
        self.stats[name][key] = self.stats[name].get(key,0)+1

    # UI actions 
    def start_game(self):
        print("Welcome to Pymon World\n")
        print("It's just you and your loyal Pymon roaming around to find more Pymons to capture and adopt.\n")
        print("You started at ",self.current_pymon.get_location().get_name())

        while True:
            self.handle_menu()
            choice = input("Select an option: ").strip()
            try:
                if choice == "1": self.inspect_pymon()
                elif choice == "2": self.inspect_location()
                elif choice == "3": self.menu_move()
                elif choice == "4": self.menu_pickup()
                elif choice == "5": self.menu_inventory()
                elif choice == "6": self.menu_challenge()
                elif choice == "7": self.menu_swap()
                elif choice == "8": self.menu_save()
                elif choice == "9": self.menu_load()
                elif choice == "10": self.show_stats()
                elif choice == "11": self.menu_admin()
                elif choice == "0":
                    print("Bye!"); break
                else:
                    print("Invalid choice.")
            except GameOver:
                print("\n*** GAME OVER: You have no Pymon left. ***")
                break
            except InvalidDirectionException as e:
                print(f"Move error: {e}")
            except InvalidInputFileFormat as e:
                print(f"CSV error: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

    def inspect_pymon(self):
        p = self.current_pymon
        print("\n--- Current Pymon ---")
        print(f"Name: {p.name}")
        print(f"Description: {p.description}")
        print(f"Energy: {p.energy}/{p.energy_max}")
        print(f"Speed: {p.speed} m/s")
        print(f"Location: {p.get_location().name if p.get_location() else 'Unknown'}")
        if self.bench:
            print("Bench:", ", ".join([b.name for b in self.bench]))
        else:
            print("Bench: (empty)")
        if p.inventory:
            print("Inventory:", ", ".join([i.name for i in p.inventory]))
        else:
            print("Inventory: (empty)")

    def inspect_location(self):
        loc = self.current_pymon.get_location()
        print(f"\n--- Location: {loc.name} ---")
        print(getattr(loc,"description",""))
        if loc.creatures:
            print("Creatures here:", ", ".join([getattr(c,'nickname', getattr(c,'name','?')) for c in loc.creatures if c is not self.current_pymon]))
        else:
            print("Creatures here: (none)")
        if loc.items:
            print("Items here:", ", ".join([i.name for i in loc.items]))
        else:
            print("Items here: (none)")
        doors = [d for d,t in loc.doors.items() if t]
        print("Doors:", ", ".join(doors) if doors else "(none)")

    def menu_move(self):
        d = input("Enter a direction (west/north/east/south): ").strip().lower()
        if d not in ("west","north","east","south"):
            print("Invalid direction keyword."); return
        here = self.current_pymon.get_location()
        nxt = here.doors.get(d)
        if not nxt:
            print("There is no door that way."); return
        # perform move via Pymon API (handles list updates)
        self.current_pymon.move(d)
        self._move_counter += 1
        print(f"Moved {d} to {self.current_pymon.get_location().name}.")
        self._decrement_energy_if_due()

    def menu_pickup(self):
        loc = self.current_pymon.get_location()
        if not loc.items:
            print("No items to pick up here."); return
        print("\nItems on the ground:")
        for idx, it in enumerate(loc.items, start=1):
            print(f"{idx}. {it}")
        sel = input("Pick which item # (or Enter to cancel): ").strip()
        if not sel: return
        try:
            k = int(sel); assert 1 <= k <= len(loc.items)
        except: print("Invalid selection."); return
        it = loc.items[k-1]
        if not it.pickable:
            print("You can't pick up this item."); return
        self.current_pymon.inventory.append(it)
        loc.items.pop(k-1)
        print(f"Picked up: {it.name}")

    def menu_inventory(self):
        p = self.current_pymon
        if not p.inventory:
            print("Inventory is empty."); return
        print("\nInventory:")
        for idx, it in enumerate(p.inventory, start=1):
            print(f"{idx}. {it}")
        print("a) Use apple   b) Use pogo   c) Use binocular   (Enter to cancel)")
        sel = input("Choose (number for details, or a/b/c to use): ").strip().lower()
        if not sel: return
        if sel in ("a","b","c"):
            if sel == "a":
                idx = next((i for i,x in enumerate(p.inventory) if x.name.lower()=="apple"), -1)
                if idx == -1: print("You don't have an Apple."); return
                p.consume_apple()
                p.inventory.pop(idx)
                print("You ate an Apple. Energy +1 (max 3).")
            elif sel == "b":
                idx = next((i for i,x in enumerate(p.inventory) if x.name.lower().startswith("pogo")), -1)
                if idx == -1: print("You don't have a Pogo stick."); return
                p.arm_pogo()
                p.inventory.pop(idx)  # breaks after next race
                print("You equipped the Pogo stick. Your next race doubles your actual speed.")
            elif sel == "c":
                idx = next((i for i,x in enumerate(p.inventory) if x.name.lower().startswith("binocular")), -1)
                if idx == -1: print("You don't have Binocular."); return
                print("\n" + p.use_binocular())
            return
        # show detail
        try:
            k = int(sel); assert 1 <= k <= len(p.inventory)
        except: print("Invalid input."); return
        print(str(p.inventory[k-1]))

    def menu_swap(self):
        if not self.bench:
            print("Bench is empty."); return
        print("\nBenched Pymons:")
        for i, b in enumerate(self.bench, start=1):
            print(f"{i}. {b.name} (Energy {b.energy}/{b.energy_max}, Speed {b.speed})")
        sel = input("Choose which # to make current (Enter to cancel): ").strip()
        if not sel: return
        try: k = int(sel); assert 1 <= k <= len(self.bench)
        except: print("Invalid selection."); return
        new = self.bench.pop(k-1)
        self.bench.insert(0, self.current_pymon)
        self.current_pymon = new
        print(f"Current Pymon is now {self.current_pymon.name}.")

    def menu_challenge(self):
        here = self.current_pymon.get_location()
        opponents = [c for c in here.creatures if c is not self.current_pymon]
        if not opponents:
            print("No opponent here."); return
        print("\nOpponents present:")
        def spd(x): return getattr(x,"speed",0.0)
        for i, c in enumerate(opponents, start=1):
            tag = "Pymon" if getattr(c,"adoptable",False) else "Animal"
            name = getattr(c,'nickname', getattr(c,'name','?'))
            print(f"{i}. {name} [{tag}] (Speed {spd(c)})")
        sel = input("Choose opponent # (Enter to cancel): ").strip()
        if not sel: return
        try: k = int(sel); assert 1 <= k <= len(opponents)
        except: print("Invalid selection."); return
        opp = opponents[k-1]
        outcome = self._race_100m(self.current_pymon, opp)
        # apply outcome
        if outcome == "WIN":
            print("You WON!")
            if getattr(opp,"adoptable",False):
                self._adopt(opp)
                print(f"{getattr(opp,'nickname',getattr(opp,'name','?'))} has joined your team!")
        elif outcome == "LOSE":
            print("You LOST.")
            self.current_pymon.energy -= 1
            if self.current_pymon.energy <= 0:
                # remove current from room and promote bench or game over
                if self.current_pymon in here.creatures:
                    here.creatures.remove(self.current_pymon)
                if self.bench:
                    self.current_pymon = self.bench.pop(0)
                    print(f"{self.current_pymon.name} steps in from the bench!")
                else:
                    raise GameOver()
        else:
            print("It's a DRAW.")
        # update stats
        self._load_stats()
        me_name = self.current_pymon.name
        opp_name = getattr(opp,'nickname', getattr(opp,'name','?'))
        if outcome == "WIN":
            self._bump_stat(me_name, "W")
            if getattr(opp,"adoptable",False): self._bump_stat(opp_name, "L")
        elif outcome == "LOSE":
            self._bump_stat(me_name, "L")
            if getattr(opp,"adoptable",False): self._bump_stat(opp_name, "W")
        else:
            self._bump_stat(me_name, "D")
            if getattr(opp,"adoptable",False): self._bump_stat(opp_name, "D")
        self._save_stats()

    def _adopt(self, creature: Creature):
        # Convert animal to Pymon or keep Pymon as-is and add to bench
        if not getattr(creature,"adoptable",False):
            return False
        name = getattr(creature,'nickname', getattr(creature,'name','?'))
        # replace creature entry with a Pymon objec
        desc = getattr(creature,'description',"adopted")
        spd = getattr(creature,'speed', 5.0)
        p = Pymon(name, desc, spd)
        # place at current location
        p.spawn(self.current_pymon.get_location())
        self.bench.append(p)
        self.record.creatures_by_name[name] = p
        return True

    def _race_100m(self, me: Pymon, opp) -> str:
        print("\n--- Race Start (100m) ---")
        my_pos, opp_pos = 0.0, 0.0
        second = 0
        pogo_used = False
        opp_speed = getattr(opp,'speed',0.0)
        opp_name = getattr(opp,'nickname', getattr(opp,'name','Opponent'))
        while my_pos < 100.0 and opp_pos < 100.0:
            second += 1
            # player's speed with luck
            my_speed = me.speed
            my_luck = random.uniform(0.2, 0.5)
            my_sign = -1 if random.random() < 0.5 else 1
            my_actual = my_speed * (1 + my_sign * my_luck)
            if me._pogo_armed and not pogo_used:
                my_actual *= 2.0
                pogo_used = True
                me._pogo_armed = False
            # opponent
            o_luck = random.uniform(0.2, 0.5)
            o_sign = -1 if random.random() < 0.5 else 1
            opp_actual = opp_speed * (1 + o_sign * o_luck)

            my_pos += max(0.0, my_actual)
            opp_pos += max(0.0, opp_actual)
            print(f"[{second:2d}s] You {my_pos:6.1f}m | {opp_name} {opp_pos:6.1f}m")
            time.sleep(1)

        if my_pos >= 100.0 and opp_pos >= 100.0: return "DRAW"
        if my_pos >= 100.0: return "WIN"
        if opp_pos >= 100.0: return "LOSE"
        return "DRAW"

    def menu_save(self):
        path = input("Enter save filename (e.g., save1.csv): ").strip()
        if not path: print("Cancelled."); return
        bench_names = [b.name for b in self.bench]
        # Register all entities into record map before save
        for loc in self.locations:
            for c in loc.creatures:
                nm = getattr(c,'nickname', getattr(c,'name','?'))
                self.record.creatures_by_name[nm] = c
        self.record.save_game(path, self.current_pymon.name, bench_names)
        print(f"Saved to {path}")

    def menu_load(self):
        path = input("Enter save filename to load: ").strip()
        if not path or not os.path.exists(path):
            print("File not found."); return
        cur_name, bench_names = self.record.load_game(path)
        # Rebuild state
        self.bench = [self.record.creatures_by_name[n] for n in bench_names if isinstance(self.record.creatures_by_name.get(n), Pymon)]
        if cur_name and isinstance(self.record.creatures_by_name.get(cur_name), Pymon):
            self.current_pymon = self.record.creatures_by_name[cur_name]
        print("Game loaded.")

    def show_stats(self):
        self._load_stats()
        print("\n=== Race Stats (per Pymon) ===")
        if not self.stats:
            print("No races yet.")
            return
        for n, rec in sorted(self.stats.items()):
            print(f"{n}: {rec['W']}W/{rec['L']}L/{rec['D']}D")

    # - Admin 
    def menu_admin(self):
        print("\n[Admin] 1) Add location  2) Add creature  3) Randomise connections  4) Back")
        sel = input("Choose: ").strip()
        if sel == "1": self._admin_add_location()
        elif sel == "2": self._admin_add_creature()
        elif sel == "3": self._admin_randomise_connections()
        else: return

    def _admin_add_location(self):
        name = input("New location name: ").strip()
        if not name or name in self.record.locations_by_name:
            print("Invalid or duplicate name."); return
        desc = input("Description: ").strip()
        loc = Location(name, description=desc)
        self.record.locations_by_name[name] = loc
        print(f"Location '{name}' added. (Persist to CSV manually if required.)")

    def _admin_add_creature(self):
        nickname = input("Creature nickname: ").strip()
        if not nickname:
            print("Invalid nickname."); return
        desc = input("Description: ").strip()
        adopt = input("Adoptable (yes/no): ").strip().lower().startswith("y")
        try:
            speed = float(input("Speed (m/s): ").strip())
        except:
            print("Invalid speed."); return
        c = Creature(nickname, desc, adopt, speed)
        self.record.creatures_by_name[nickname] = c
        print(f"Creature '{nickname}' added to catalog.")

    def _admin_randomise_connections(self):
        locs = list(self.record.locations_by_name.values())
        # disconnect all
        for L in locs:
            for d in ("west","north","east","south"):
                if L.doors[d] is not None:
                    opposite = {"west":"east","east":"west","north":"south","south":"north"}[d]
                    L.doors[d].doors[opposite] = None
                    L.doors[d] = None
        # random connect
        for L in locs:
            for d in ("west","north","east","south"):
                if L.doors[d] is None and random.random() < 0.6:
                    target = random.choice(locs)
                    if target is not L:
                        if d == "west":
                            L.connect_west(target)
                        elif d == "east":
                            L.connect_east(target)
                        elif d == "north":
                            L.connect_north(target)
                        elif d == "south":
                            L.connect_south(target)
        print("Connections randomised (bi-directional).")


# Main


if __name__ == '__main__':
    ops = Operation()
    ops.setup()
    # ops.display_setup()
    ops.start_game()
