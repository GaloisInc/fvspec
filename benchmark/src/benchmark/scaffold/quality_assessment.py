import json

from inspect_ai.solver import TaskState


class QualityAssessment:
    model: str
    token_usage: int
    time: int
    num_messages: int
    num_generate_messages: int
    num_input_messages: int
    
    def __init__(self, state: TaskState):
        self.model = state.output.model
        self.token_usage = state.token_usage
        self.time = state.output.time
        self.num_messages = len(state.messages)
        self.num_generate_messages = sum(1 for sm in state.messages if sm.source == 'generate')
        self.num_input_messages = sum(1 for sm in state.messages if sm.source == 'input')
        

    def toJSON(self):
        return json.dumps(self.__dict__, indent=4)
