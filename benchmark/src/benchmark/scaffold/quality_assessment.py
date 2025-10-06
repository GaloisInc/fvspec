import json
import re

from inspect_ai.solver import TaskState


class QualityAssessment:
    sample_id: str
    sample_name: str
    datetime: str
    model: str
    token_usage: int
    time: int
    num_messages: int
    num_generate_messages: int
    num_input_messages: int
    success: bool
    num_sorries: int
    lines_pbt: int
    lines_code: int
    percent_lines_added: float | None #(lines code - lines pbt)/(lines pbt)
    faithfulness: float | None #defined by ai
    interest: float | None #defined by ai
    
    def __init__(self, state: TaskState):
        self.sample_id = state.metadata.get("datapoint").id
        self.sample_name = state.metadata.get("datapoint").pbt_name
        self.datetime = state.metadata.get("date_time")
        self.model = state.output.model
        self.token_usage = state.token_usage
        self.time = state.output.time
        self.num_messages = len(state.messages)
        self.num_generate_messages = sum(1 for sm in state.messages if sm.source == 'generate')
        self.num_input_messages = sum(1 for sm in state.messages if sm.source == 'input')
        self.lines_pbt = state.metadata.get("datapoint").pbt.count("\n")
        # code related metrics
        pattern = r"(?s)<code>(.*?)</code>"
        mtch = re.search(pattern, state.messages[-1].text)
        if not mtch:
            self.success = False
            self.num_sorries = 0
            self.lines_code = 0
            self.percent_lines_added = 0.0
        else:
            code_snippet = mtch.group(1)
            self.success = True
            self.num_sorries = code_snippet.count("sorry")
            self.lines_code = code_snippet.count("\n")
            self.percent_lines_added = (self.lines_code - self.lines_pbt)/self.lines_pbt
        # faithfulness metric
        f_pattern = r"Faithfulness.*:\s*([0-9]*.?[0-9]+)/([0-9]+)"
        f_mtch = re.search(f_pattern, state.messages[-1].text, re.IGNORECASE)
        if not f_mtch:
            self.faithfulness = None
        else:
            self.faithfulness = float(f_mtch.group(1))/float(f_mtch.group(2))*10.0
        # interest metric
        i_pattern = r"Interest.*:\s*([0-9]*.?[0-9]+)/([0-9]+)"
        i_mtch = re.search(i_pattern, state.messages[-1].text, re.IGNORECASE)
        if not i_mtch:
            self.interest = None
        else:
            self.interest = float(i_mtch.group(1))/float(i_mtch.group(2))*10.0


    def toJSON(self):
        return json.dumps(self.__dict__, indent=4)
