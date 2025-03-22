# Authors: 
# João Roldão - 113920
# Martim Santos - 114614
# Gonçalo Sousa - 108133

class StateManager:
    def __init__(self, map_knowledge):
        """
        Initialize StateManager attributes.
        """
        self.map_knowledge = map_knowledge
        self.current_state = None

    def evaluate_state(self, snake_info):
        """
        Evaluate the current state of the snake.
        """
        if self.map_knowledge.is_danger_nearby(snake_info):
            self.current_state = State.DANGER
        elif self.map_knowledge.has_food():
            self.current_state = State.TARGETING
        else:
            self.current_state = State.SAFE

        return self.current_state

class State:
    DANGER = "danger"
    TARGETING = "targeting"
    SAFE = "safe"
