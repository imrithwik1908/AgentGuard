from enum import StrEnum


class RunStatus(StrEnum):
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class SpanType(StrEnum):
    AGENT = "AGENT"
    LLM = "LLM"
    RETRIEVER = "RETRIEVER"
    TOOL = "TOOL"
    CHAIN = "CHAIN"
    EMBEDDING = "EMBEDDING"
    RERANKER = "RERANKER"
    CUSTOM = "CUSTOM"


class EvaluationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class EvaluationMethod(StrEnum):
    DETERMINISTIC_BEHAVIORAL = "DETERMINISTIC_BEHAVIORAL"
    DETERMINISTIC_OPERATIONAL = "DETERMINISTIC_OPERATIONAL"
    RETRIEVAL = "RETRIEVAL"
    LLM_JUDGE = "LLM_JUDGE"
    INSTRUMENTATION_ONLY = "INSTRUMENTATION_ONLY"


class EvaluationJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class EvaluationJobCaseStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
