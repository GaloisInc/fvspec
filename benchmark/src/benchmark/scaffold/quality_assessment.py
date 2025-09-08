import json

from inspect_ai.solver import TaskState


class QualityAssessment:
    model: str
    token_usage: int
    time: int
    num_itterations: int
    

    def __init__(self, state: TaskState):
        self.token_usage = state.token_usage
        self.usage = state.output.usage.total_tokens
        self.model = state.output.model
        self.time = state.output.time
        self.num_itterations = len(state.messages)

    def toJSON(self):
        return json.dumps(self.__dict__, indent=4)
