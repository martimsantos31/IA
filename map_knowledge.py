# Authors: 
# João Roldão - 113920
# Martim Santos - 114614
# Gonçalo Sousa - 108133

# Talked with
# Gabriel Silva - 113786

from consts import Tiles
from collections import deque

class MapKnowledge:
    def __init__(self, map_size=(48, 24), map_data=None):
        """
        Initialize MapKnowledge attributes.
        """
        # Initialize map with default values
        self.map_size = map_size
        self.map = [[(map_data[x][y] if map_data else Tiles.PASSAGE.value, 0)
                     for y in range(map_size[1])] for x in range(map_size[0])]
        self.visit_count = [[0 for _ in range(map_size[1])] for _ in range(map_size[0])]

        # Component labeling
        self.component_id = [[-1 for _ in range(map_size[1])] for _ in range(map_size[0])]
        self.component_size = {} 
        self.current_label = 0

        # Cache
        self.collision_cache = {}


    ##########################################################
    #                 Map Knowledge Update                   #
    ##########################################################

    def update_map(self, snake_info, current_step):
        """
        Update the map with the current snake information.
        """
        self.collision_cache.clear()
        traverse = snake_info.get("traverse", False)
        head_x, head_y = snake_info["body"][0]
        self.map[head_x][head_y] = (Tiles.SNAKE.value, current_step)

        # Update tiles from body
        for part in snake_info["body"]:
            if isinstance(part, list) and len(part) == 2:
                x, y = part
                self.map[x][y] = (Tiles.SNAKE.value, current_step)

        # Update tiles from sight
        for col, rows in snake_info.get("sight", {}).items():
            try:
                col = int(col)
                for row, tile_value in rows.items():
                    row = int(row)
                    if traverse:
                        if tile_value == Tiles.SUPER.value:
                            if snake_info["step"] > 2000:
                                self.map[col][row] = (tile_value, current_step)
                            elif snake_info["range"] > 4:
                                self.map[col][row] = (Tiles.SNAKE.value, current_step)
                            else:
                                self.map[col][row] = (tile_value, current_step)
                        else:
                            self.map[col][row] = (tile_value, current_step)
                    else:
                        self.map[col][row] = (tile_value, current_step)
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error updating sight in map: {e}")

        # After updating the map, recache BFS components
        self.compute_components(snake_info["traverse"])


    ##########################################################
    #                  Component Computing                   #
    ##########################################################

    def compute_components(self, traverse):
        """
        Compute connected components of the map.
        """
        self.component_id = [[-1 for _ in range(self.map_size[1])] for _ in range(self.map_size[0])]
        self.component_size.clear()
        label_counter = 0
        width, height = self.map_size

        for x in range(width):
            for y in range(height):
                if self.component_id[x][y] == -1 and not self.is_collision((x, y), traverse):
                    # BFS from (x, y) to label this entire connected component
                    queue = deque([(x, y)])
                    self.component_id[x][y] = label_counter
                    comp_cells = 1

                    while queue:
                        cx, cy = queue.popleft()
                        for nx, ny in self._neighbors(cx, cy, traverse):
                            if self.component_id[nx][ny] == -1 and not self.is_collision((nx, ny), traverse):
                                self.component_id[nx][ny] = label_counter
                                queue.append((nx, ny))
                                comp_cells += 1

                    self.component_size[label_counter] = comp_cells
                    label_counter += 1


    def _neighbors(self, x, y, traverse):
        """
        Get the neighbors of a cell (x, y) in the map.
        """
        directions = [(0,1), (0,-1), (1,0), (-1,0)]
        w, h = self.map_size
        for dx, dy in directions:
            if traverse:
                nx = (x + dx) % w
                ny = (y + dy) % h
            else:
                nx = x + dx
                ny = y + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
            yield (nx, ny)


    ##########################################################
    #                    BFS Computing                       #
    ##########################################################

    def compute_bfs_layers(self, start, traverse):
        """
        Single BFS from 'start', storing distance in distance_grid[x][y].
        If distance_grid[x][y] == -1, it's unreachable.
        """
        from collections import deque
        w, h = self.map_size
        distance_grid = [[-1]*h for _ in range(w)]
        queue = deque()
        queue.append(start)
        distance_grid[start[0]][start[1]] = 0

        while queue:
            cx, cy = queue.popleft()
            for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                if traverse:
                    nx = (cx+dx) % w
                    ny = (cy+dy) % h
                else:
                    nx, ny = cx+dx, cy+dy
                    if not (0<=nx<w and 0<=ny<h):
                        continue

                if distance_grid[nx][ny] == -1 and not self.is_collision((nx, ny), traverse):
                    distance_grid[nx][ny] = distance_grid[cx][cy] + 1
                    queue.append((nx, ny))

        return distance_grid        


    ##########################################################
    #                        Utils                           #
    ##########################################################

    def is_collision(self, position, traverse):
        """"
        Check if there is a collision at position (x, y).
        """
        cache_key = (position, traverse)
        if cache_key in self.collision_cache:
            return self.collision_cache[cache_key]

        x, y = position
        w, h = self.map_size
        if not traverse:
            if x<0 or x>=w or y<0 or y>=h:
                result = True
            else:
                tile = self.map[x][y][0]
                result = tile in (Tiles.STONE.value, Tiles.SNAKE.value)
        else:
            # wrapping
            tile = self.map[x][y][0]
            result = (tile == Tiles.SNAKE.value)

        self.collision_cache[cache_key] = result
        return result

    def is_danger_nearby(self, snake_info):
        """
        Check if there is danger nearby the snake.
        """
        head_x, head_y = snake_info["body"][0]
        body_set = {tuple(part) for part in snake_info["body"][1:]}  # Snake's own body

        # Adjacent directions (NORTH, SOUTH, EAST, WEST)
        adjacent_directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]

        for dx, dy in adjacent_directions:
            if snake_info["traverse"] == False:
                nx, ny = head_x + dx, head_y + dy
                if (nx, ny) in body_set:
                    continue
                if not (0 <= nx < self.map_size[0] and 0 <= ny < self.map_size[1]):
                    return True  # Danger: Outside map bounds
                if self.is_collision((nx, ny), snake_info["traverse"]):
                    return True  # Danger: Collision with wall or snake
            else:
                nx = (head_x + dx) % self.map_size[0]
                ny = (head_y + dy) % self.map_size[1]
                if (nx, ny) in body_set:
                    continue
                if self.get_tile(nx, ny) == Tiles.SNAKE.value:
                    return True  # Danger: Collision with another snake body

        return False


    def has_food(self):
        """
        Check if there is food in the map.
        """
        for x in range(self.map_size[0]):
            for y in range(self.map_size[1]):
                if self.map[x][y][0] in (Tiles.FOOD.value, Tiles.SUPER.value):
                    return True
        return False


    def get_tile(self, x, y):
        """
        Get the tile value in the map at position (x, y).
        """
        return self.map[x][y][0]


    def get_component_size(self, position):
        """
        Get the size of the connected component at position (x, y).
        """
        x, y = position
        label = self.component_id[x][y]
        if label == -1:
            return 0
        return self.component_size.get(label, 0)
