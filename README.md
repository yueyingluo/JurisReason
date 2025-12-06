# JurisReason - Legal Reasoning Pipeline with Retrieval-Augmented Generation

A sophisticated system for solving Chinese judicial examination questions using Large Language Models (LLMs) with retrieval-augmented generation (RAG) and iterative self-correction.

## Overview

This repository implements an intelligent legal reasoning pipeline that combines:
- **LLM-based reasoning** using DeepSeek-V3 and DeepSeek-R1 models
- **Retrieval-Augmented Generation (RAG)** for accessing relevant legal articles
- **Iterative self-correction** with automatic verification and revision
- **Structured Chain-of-Thought (CoT)** output generation

## System Architecture

The pipeline follows a multi-stage process (see `pipeline.jpg` for visual reference):

### 1. **Initial Query & Law Identification** (`init_query`)
- Analyzes the legal question and identifies potentially relevant law articles
- Uses DeepSeek-V3 to extract the reasoning process and generate queries
- Output: Thinking process + list of relevant law articles to retrieve

### 2. **Retrieval** (`retrieve`)
- Fetches full text of relevant laws from a local knowledge base via API
- Uses BM25 or semantic search to find the most relevant legal provisions
- Deduplicates results for efficiency
- Requires `retrieve_api.py` running on `localhost:5000`

### 3. **Judgment & Answer Generation** (`judge_and_answer`)
- Evaluates which retrieved laws are applicable to the case
- Uses DeepSeek-R1 for deep reasoning through each option
- Filters out irrelevant laws and explains the reasoning
- Output: Structured reasoning process + final answer

### 4. **Verification** (`verify_answer`)
- Compares the generated answer against ground truth
- Extracts answer letters (A-D) using pattern matching
- Determines if revision is needed

### 5. **Revision** (`revise`) - *If answer is incorrect*
- Analyzes previous reasoning to identify errors
- Two revision strategies:
  - **Law error**: Identifies missing/incorrect laws and retrieves new ones
  - **Reasoning error**: Re-analyzes with existing laws
- Iterates up to 3 times for correction

### 6. **Output Formatting** (`save_answer`)
- Consolidates the reasoning chain into a structured format
- Generates clean Chain-of-Thought output with tags:
  - `<think>`: Reasoning process
  - `<search>`: Retrieval queries
  - `<information>`: Retrieved law articles
  - `<answer>`: Final answer


## Installation

### Prerequisites
- Python 3.8+
- Volcengine ARK SDK for DeepSeek models

### Setup

```bash
pip install volcengine-python-sdk[ark]
pip install requests
```


## Use Cases

This system is designed for:

- Generating training data for legal reasoning models
- Automated legal question answering systems
- Educational tools for judicial examination preparation
- Research on LLM reasoning capabilities in specialized domains

### Notes
- Local Retrieval Required: The retrieval API must be running for the pipeline to function

## Contributing
Contributions are welcome! Please feel free to submit issues or pull requests.
