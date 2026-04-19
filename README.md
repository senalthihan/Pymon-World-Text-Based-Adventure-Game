# Pymon World — Text-Based Adventure Game

A Python command-line game where you explore locations, challenge 
creatures to races, capture Pymons, and manage your team's energy 
and inventory.

## Tools & Concepts
Python, OOP (Classes, Inheritance, Exceptions), CSV File I/O

## Features (Stage 1–4)
- **Map & Movement** — Navigate between locations loaded from CSV
- **Creature System** — Encounter animals and adoptable Pymons
- **Race Mechanic** — Challenge creatures to 100m races with 
  randomised speed and luck factors
- **Inventory System** — Pick up and use items (Apple, Pogo Stick, 
  Binocular) with real gameplay effects
- **Energy System** — Pymon energy decreases every 2 moves; 
  bench Pymons step in if current faints
- **Save/Load** — Full game state persistence via CSV
- **Race Stats** — Win/Loss/Draw tracking per Pymon
- **Admin Mode** — Add locations, creatures, and randomise map 
  connections at runtime

## How to Run
```bash
python pymon_game_s4099547.py locations.csv creatures.csv items.csv
```

## File Structure
- `pymon_game_s4099547.py` — Main game logic
- `locations.csv` — Map data
- `creatures.csv` — Creature definitions
- `items.csv` — Item definitions
