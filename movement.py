# Authors: 
# João Roldão - 113920
# Martim Santos - 114614
# Gonçalo Sousa - 108133

import random
from state_manager import State
from consts import Direction, Tiles

DIRECTION_TO_KEY = {
    Direction.NORTH.value: "w",
    Direction.SOUTH.value: "s",
    Direction.EAST.value: "d",
    Direction.WEST.value: "a",
}

HISTORY_LEN = 50

class Movement:
    def __init__(self, state_manager, map_knowledge, history_len=HISTORY_LEN):
        """
        Initialize Movement attributes.
        """
        self.state_manager = state_manager
        self.map_knowledge = map_knowledge
        self.direction_history = []
        self.head_history = []
        self.history_len = history_len
        self.distance_grid = None


    ##########################################################
    #                      Decide Move                       #
    ##########################################################

    def decide_move(self, snake_info, opponent_info=None):
        """
        Decide the next move for the snake.
        """
        # 0) BFS layers for head once per turn
        head = tuple(snake_info["body"][0])
        traverse = snake_info["traverse"]
        self.distance_grid = self.map_knowledge.compute_bfs_layers(head, traverse)

        # 1) Check loops
        if self.detect_loop():
            direction = self.break_loop_strategy(snake_info)
            self._update_direction_history(direction, snake_info)
            return DIRECTION_TO_KEY.get(direction)

        # 2) Decide based on state
        try:
            if self.state_manager.current_state == State.DANGER:
                direction = self.avoid_danger(snake_info)

            elif self.state_manager.current_state == State.TARGETING:
                direction = self.navigate_to_food(snake_info)

            else:
                kill_dir = self.attempt_kill(snake_info)
                if kill_dir:
                    direction = kill_dir
                else:
                    direction = self.explore(snake_info)
                
        except Exception as e:
            direction = self.get_fallback_direction(snake_info)

        if direction is None:
            direction = self.get_fallback_direction(snake_info)

        self._update_direction_history(direction, snake_info)
        return DIRECTION_TO_KEY.get(direction)
    

    def _update_direction_history(self, direction, snake_info):
        """
        Update tracking history of snake's direction and head position.
        """
        if direction:
            self.direction_history.append(direction)
            if len(self.direction_history) > self.history_len:
                self.direction_history.pop(0)

        if snake_info["body"]:
            self.head_history.append(tuple(snake_info["body"][0]))
            if len(self.head_history) > self.history_len:
                self.head_history.pop(0)


    ##########################################################
    #                         Loops                          #
    ##########################################################

    def detect_loop(self):
        """
        Detect loops in the snake's head position history.
        """
        min_pattern_length = 10  # Minimum steps for a valid loop
        history_len = len(self.head_history)

        # Only check if we have enough history
        if history_len < min_pattern_length * 2:
            return False

        # Check for repeating patterns of increasing lengths
        for pattern_length in range(min_pattern_length, history_len // 2 + 1):
            pattern = self.head_history[-pattern_length:]  # Last 'pattern_length' steps
            previous_pattern = self.head_history[-2 * pattern_length:-pattern_length]

            if pattern == previous_pattern:
                return True

        return False


    def break_loop_strategy(self, snake_info):
        """
        Break a detected loop by avoiding recently visited positions.
        If no safe options exist, use fallback direction.
        """

        head = tuple(snake_info["body"][0])
        traverse = snake_info["traverse"]
        recent_positions = set(self.head_history[-10:])
        snake_len = len(snake_info["body"])

        # Find a direction that avoids recent positions and is safe
        best_moves = []
        for dx, dy, dir_val in self.get_directions():
            nxt = self.next_position(head, (dx, dy), traverse)
            if nxt and nxt not in recent_positions and not self.map_knowledge.is_collision(nxt, traverse):
                comp_size = self.map_knowledge.get_component_size(nxt)
                if comp_size >= snake_len:
                    exits = self.simulate_move(nxt, dir_val, traverse)
                    best_moves.append((comp_size, exits, dir_val))

        if best_moves:
            best_moves.sort(key=lambda x: (x[0], x[1]), reverse=True)
            chosen_dir = best_moves[0][2]
            return chosen_dir

        # No optimal move found, fallback to avoid infinite loops
        return self.get_fallback_direction(snake_info)


    ##########################################################
    #                       FallBack                         #
    ##########################################################

    def get_fallback_direction(self, snake_info):
        """
        Get a fallback direction.
        """
        last_move = self.direction_history[-1] if self.direction_history else None
        opposite_map = {
            Direction.NORTH.value: Direction.SOUTH.value,
            Direction.SOUTH.value: Direction.NORTH.value,
            Direction.EAST.value: Direction.WEST.value,
            Direction.WEST.value: Direction.EAST.value,
        }
        opposite_dir = opposite_map.get(last_move)

        head = tuple(snake_info["body"][0])
        traverse = snake_info["traverse"]
        snake_length = len(snake_info["body"])

        # Check immediate moves
        best_moves = []
        for dx, dy, dir_val in self.get_directions():
            if dir_val == opposite_dir:
                continue
            nxt = self.next_position(head, (dx, dy), traverse)
            if nxt is None:
                continue
            if not self.map_knowledge.is_collision(nxt, traverse):
                comp_size = self.map_knowledge.get_component_size(nxt)
                if comp_size >= snake_length:
                    # check how many exits we have from that tile
                    exits = self.simulate_move(nxt, dir_val, traverse)
                    best_moves.append((comp_size, exits, dir_val))

        # Choose the best immediate move
        if best_moves:
            best_moves.sort(key=lambda x: (x[0], x[1]), reverse=True)
            chosen_dir = best_moves[0][2]
            return chosen_dir

        # Evaluate all possible directions
        valid_moves = []
        for dx, dy, dir_val in self.get_directions():
            if dir_val == opposite_dir:
                continue  # Avoid immediately returning to the last move's opposite
            nxt = self.next_position(head, (dx, dy), traverse)
            if nxt and not self.map_knowledge.is_collision(nxt, traverse):
                valid_moves.append(dir_val)

        # If valid moves exist, choose one
        if valid_moves:
            return random.choice(valid_moves)

        # If no valid moves, attempt to use the opposite direction as a last resort
        if opposite_dir:
            return opposite_dir

        # Final fallback: choose any direction
        return random.choice([Direction.NORTH.value, Direction.SOUTH.value,
                            Direction.EAST.value, Direction.WEST.value])
    

    ##########################################################
    #                    Danger Avoidance                    #
    ##########################################################

    def avoid_danger(self, snake_info):
        """
        Avoid danger by moving to a safe location.
        """
        head = tuple(snake_info["body"][0])
        traverse = snake_info["traverse"]
        snake_len = len(snake_info["body"])
        safe_moves = []

        for dx, dy, direction_val in self.get_directions():
            nxt = self.next_position(head, (dx, dy), traverse)
            if nxt and self.distance_grid[nxt[0]][nxt[1]] != -1:
                csize = self.map_knowledge.get_component_size(nxt)
                if csize >= snake_len:
                    exits = self.simulate_move(nxt, direction_val, traverse)
                    safe_moves.append((exits, direction_val))

        if safe_moves:
            safe_moves.sort(reverse=True, key=lambda x: x[0])
            return safe_moves[0][1]

        # fallback if no safe moves
        return self.get_fallback_direction(snake_info)
    

    ##########################################################
    #                      Exploration                       #
    ##########################################################

    def explore(self, snake_info):
        """
        Explore the map.
        """
        head = tuple(snake_info["body"][0])
        w, h = self.map_knowledge.map_size
        distance_grid = self.distance_grid

        best_tile = None
        best_score = -1

        for x in range(w):
            for y in range(h):
                dist = distance_grid[x][y]
                if dist == -1:
                    continue
                # let's say region score = how rarely visited
                last_visit_step = self.map_knowledge.map[x][y][1]
                # higher is better
                tile_score = snake_info["step"] - last_visit_step
                if tile_score > best_score:
                    best_score = tile_score
                    best_tile = (x, y)

        if best_tile and best_tile != head:
            # use BFS-based path or simple direction
            return self.bfs_direction_to(head, best_tile, snake_info)

        return self.get_fallback_direction(snake_info)
    

    ##########################################################
    #                    Food Navigation                     #
    ##########################################################

    def navigate_to_food(self, snake_info):
        """
        Find the closest (by BFS) safe food tile. 
        """
        head = tuple(snake_info["body"][0])
        w,h = self.map_knowledge.map_size
        dist_grid = self.distance_grid

        best_food = None
        best_dist = 999999
        for x in range(w):
            for y in range(h):
                tile = self.map_knowledge.get_tile(x, y)
                if tile in (Tiles.FOOD.value, Tiles.SUPER.value):
                    # safe check
                    if not self.is_food_location_safe((x,y), snake_info):
                        continue
                    d = dist_grid[x][y]
                    if d != -1 and d < best_dist:
                        best_dist = d
                        best_food = (x,y)

        if best_food:
            return self.bfs_direction_to(head, best_food, snake_info)
        # fallback
        return self.explore(snake_info)


    ##########################################################
    #                Pathfinding and Heuristic               #
    ##########################################################

    def bfs_direction_to(self, start, goal, snake_info):
        """
        Get the direction to the goal using BFS.
        """
        dist_grid = self.distance_grid
        if dist_grid[goal[0]][goal[1]] == -1:
            return None
        path = []
        current = goal
        while current != start:
            path.append(current)
            cdist = dist_grid[current[0]][current[1]]
            if cdist == 0:
                break
            found_prev = False
            for dx, dy, _ in self.get_directions():
                px = current[0]-dx
                py = current[1]-dy
                # wrap or not
                if snake_info["traverse"]:
                    px %= self.map_knowledge.map_size[0]
                    py %= self.map_knowledge.map_size[1]
                else:
                    if not(0<=px<self.map_knowledge.map_size[0] and 0<=py<self.map_knowledge.map_size[1]):
                        continue

                if dist_grid[px][py] == cdist-1:
                    current = (px,py)
                    found_prev = True
                    break
            if not found_prev:
                # can't reconstruct properly
                return None

        path.reverse()
        if not path:
            return None
        # The first tile in 'path' is 'start' or the second tile is the actual next step
        next_pos = path[0]
        if next_pos == start and len(path)>1:
            next_pos = path[1]

        dx = next_pos[0]-start[0]
        dy = next_pos[1]-start[1]
        if snake_info["traverse"]:
            # might differ by wrap, but let's keep it simple
            if abs(dx)>1 and dx<0:
                dx += self.map_knowledge.map_size[0]
            elif abs(dx)>1 and dx>0:
                dx -= self.map_knowledge.map_size[0]
            if abs(dy)>1 and dy<0:
                dy += self.map_knowledge.map_size[1]
            elif abs(dy)>1 and dy>0:
                dy -= self.map_knowledge.map_size[1]

        for ddx, ddy, dval in self.get_directions():
            if ddx==dx and ddy==dy:
                return dval
        return None

    ##########################################################
    #                      Multiplayer                       #
    ##########################################################

    def attempt_kill(self, snake_info):
        """
        Attempt to kill 'another snake' found in the map_knowledge.
        """
        # 1) Identify 'our_body'
        our_body_set = set(tuple(part) for part in snake_info["body"])

        # 2) Find all tiles = SNAKE.value that are not in our_body
        w, h = self.map_knowledge.map_size
        other_snake_tiles = []
        for x in range(w):
            for y in range(h):
                tile = self.map_knowledge.get_tile(x,y)
                if tile == Tiles.SNAKE.value and (x,y) not in our_body_set:
                    other_snake_tiles.append((x,y))

        if not other_snake_tiles:
            return None  # no foreign snake parts found

        # 3) We BFS-group these tiles to find distinct "snake groups"
        visited = set()
        groups = []  # list of (group_tiles_list)
        for tile_pos in other_snake_tiles:
            if tile_pos in visited:
                continue
            # BFS from tile_pos
            queue = [tile_pos]
            visited.add(tile_pos)
            component = [tile_pos]
            while queue:
                cx, cy = queue.pop()
                # neighbors ignoring 'traverse' for adjacency
                for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if (nx, ny) not in visited:
                            t = self.map_knowledge.get_tile(nx, ny)
                            if t == Tiles.SNAKE.value and (nx, ny) not in our_body_set:
                                visited.add((nx, ny))
                                queue.append((nx, ny))
                                component.append((nx, ny))

            groups.append(component)

        # 4) Filter out groups with size <= 3
        big_groups = [g for g in groups if len(g) > 3]
        if not big_groups:
            return None  # no group large enough

        # 5) pick a group to intercept. 
        our_head = tuple(snake_info["body"][0])
        best_group = None
        best_dist = 999999
        for group in big_groups:
            for tile_pos in group:
                d = self.distance_grid[tile_pos[0]][tile_pos[1]]
                if d != -1 and d < best_dist:
                    best_dist = d
                    best_group = group

        if not best_group:
            return None

        # 6) We have 'best_group' with a BFS-dist; pick a tile within that group to approach
        best_tile = None
        best_tile_dist = 999999
        for tile_pos in best_group:
            d = self.distance_grid[tile_pos[0]][tile_pos[1]]
            if d != -1 and d < best_tile_dist:
                best_tile_dist = d
                best_tile = tile_pos

        if not best_tile:
            return None

        # 7) Reconstruct path => direction
        kill_dir = self.bfs_direction_to(our_head, best_tile, snake_info)
        if kill_dir:
            return kill_dir

        return None


    ##########################################################
    #                       Utils                            #
    ##########################################################

    def next_position(self, current, dxy, traverse):
        """
        Get the next position given a direction.
        """
        x, y = current
        dx, dy = dxy
        w, h = self.map_knowledge.map_size
        if traverse:
            return ((x + dx) % w, (y + dy) % h)
        else:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                return (nx, ny)
            return None
        

    def simulate_move(self, position, direction, traverse):
        """
        Simulate a move to a position and count the number of exits.
        """
        dxy = None
        for dx, dy, dval in self.get_directions():
            if dval == direction:
                dxy = (dx, dy)
                break
        if not dxy:
            return -1

        nxt = self.next_position(position, dxy, traverse)
        if not nxt:
            return -1
        if self.map_knowledge.is_collision(nxt, traverse):
            return -1

        # count possible exits
        exits = 0
        for dx2, dy2, _ in self.get_directions():
            adj = self.next_position(nxt, (dx2, dy2), traverse)
            if adj and not self.map_knowledge.is_collision(adj, traverse):
                exits += 1
        return exits


    def is_food_location_safe(self, food_position, snake_info):
        """
        Check if a food location is safe.
        """
        snake_length = len(snake_info["body"])
        area = self.map_knowledge.get_component_size(food_position)
        return area >= snake_length * 2
        

    @staticmethod
    def get_directions():
        """
        Get the directions in terms of dx, dy, and direction value.
        """
        return [
            (0, -1, Direction.NORTH.value),
            (0, 1, Direction.SOUTH.value),
            (-1, 0, Direction.WEST.value),
            (1, 0, Direction.EAST.value),
        ]