import logging
from enum import Enum
from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task

logger = logging.getLogger("agent.executor")


class TaskType(Enum):
    CONTENT_WRITING = "content_writing"
    DATA_ANALYSIS = "data_analysis"
    TRANSLATION = "translation"
    CODE_GENERATION = "code_generation"
    RESEARCH = "research"
    SUMMARIZATION = "summarization"
    OTHER = "other"


class TaskExecutor:
    def __init__(self, brain: LLMBrain):
        self.brain = brain

    def classify_task(self, task: Task) -> TaskType:
        prompt = (
            f"Classify this task into one category:\n"
            f"- content_writing\n- data_analysis\n- translation\n"
            f"- code_generation\n- research\n- summarization\n- other\n\n"
            f"Task: {task.title}\n{task.description[:500]}\n\n"
            f"Respond with only the category name."
        )
        try:
            result = self.brain.think(prompt).strip().lower()
            return TaskType(result)
        except ValueError:
            return TaskType.OTHER

    def execute(self, task: Task) -> Optional[str]:
        task_type = self.classify_task(task)
        logger.info(f"Executing {task_type.value}: {task.title}")

        system_prompts = {
            TaskType.CONTENT_WRITING: "You are a professional content writer. "
            "Produce high-quality, original content that meets the brief exactly.",
            TaskType.DATA_ANALYSIS: "You are a data analyst. "
            "Analyze data carefully and present clear insights with evidence.",
            TaskType.TRANSLATION: "You are a professional translator. "
            "Translate accurately while preserving tone and meaning.",
            TaskType.CODE_GENERATION: "You are a senior software engineer. "
            "Write clean, well-structured, working code.",
            TaskType.RESEARCH: "You are a research analyst. "
            "Provide thorough, well-sourced analysis.",
            TaskType.SUMMARIZATION: "You are an expert summarizer. "
            "Distill key points while retaining all important information.",
            TaskType.OTHER: "You are a professional task completer. "
            "Deliver high-quality work that satisfies all requirements.",
        }

        prompt = (
            f"Complete this task:\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}\n"
        )
        if task.requirements:
            prompt += f"Requirements: {task.requirements}\n"

        return self.brain.think(
            prompt,
            system_prompt=system_prompts.get(
                task_type, system_prompts[TaskType.OTHER]
            ),
        )
