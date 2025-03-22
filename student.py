# Authors: 
# João Roldão - 113920
# Martim Santos - 114614
# Gonçalo Sousa - 108133

import asyncio
import json
import os
import websockets
from map_knowledge import MapKnowledge
from state_manager import StateManager
from movement import Movement
from consts import Tiles

async def agent_loop(server_address="localhost:8000", agent_name="Roldão"):
    async with websockets.connect(f"ws://{server_address}/player") as websocket:
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        initial_state = json.loads(await websocket.recv())

        map_size = tuple(initial_state.get("size", (48, 24)))
        map_data = initial_state.get("map", [[Tiles.PASSAGE.value] * map_size[1] for _ in range(map_size[0])])
        map_knowledge = MapKnowledge(map_size=map_size, map_data=map_data)
        state_manager = StateManager(map_knowledge)
        movement = Movement(state_manager, map_knowledge)

        while True:
            try:
                state = json.loads(await websocket.recv())

                snake_info = {
                    "name": state.get("name", agent_name),
                    "body": state.get("body", []),
                    "range": state.get("range", 0),
                    "sight": state.get("sight", {}),
                    "step": state.get("step", 0),
                    "score": state.get("score", 0),
                    "traverse": state.get("traverse", True)
                }

                # Decide move with opponent info
                next_move = movement.decide_move(snake_info)

                map_knowledge.update_map(snake_info, snake_info["step"])
                state_manager.evaluate_state(snake_info)
                next_move = movement.decide_move(snake_info)

                await websocket.send(json.dumps({"cmd": "key", "key": next_move}))

            except websockets.exceptions.ConnectionClosedOK:
                print("Server has cleanly disconnected.")
                break
            except websockets.exceptions.ConnectionClosedError as e:
                print(f"Connection error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break

if __name__ == "__main__":
    SERVER = os.environ.get("SERVER", "localhost")
    PORT = os.environ.get("PORT", "8000")
    NAME = os.environ.get("NAME", "student_agent")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(agent_loop(f"{SERVER}:{PORT}", NAME))
