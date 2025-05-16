# Legal Question Answering with LLM Reasoning and External Knowledge

## Pipeline
The system follows a structured pipeline:

### Initial Query: Analyzes the question and identifies potentially relevant laws
### Retrieval: Fetches the full text of relevant laws from a knowledge base
### Judgment: Determines which laws apply to the case and reasons through to an answer
### Verification: Checks if the answer matches the ground truth
### Revision: If incorrect, either revises the reasoning or retrieves additional laws
### Output: Produces a structured explanation with the final answer