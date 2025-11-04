# Mongo-RAG (Natural Language to Mongo Query System with PII Masking)

## Overview

**Mongo-RAG** is a modular, locally processable AI system that converts **natural language queries** into **MongoDB aggregation queries**, executes them securely, and returns results with **PII masking and unmasking**.  
The system integrates **LangChain**, **LangGraph**, and custom MongoDB toolkits to ensure that all personally identifiable information (PII) is masked before it reaches any external LLM while maintaining contextual accuracy for users.

This architecture allows controlled, explainable, and air-gapped-compatible data access through natural language — without directly exposing sensitive data to large language models.

---

## Core Workflow

1. **User Input → Natural Language Query**
   - The user submits a natural language question.
   - The system initializes a LangGraph-based state machine (`langgraph_sample.py`) that manages the query context, user metadata, and intent.

2. **Query Interpretation and Rewriting**
   - Query modification functions analyze and refine the input based on HR or domain-specific logic.
   - A system prompt (`MONGODB_AGENT_SYS_PROMPT.py`) strictly instructs the LLM to produce **aggregation-only** MongoDB queries and to avoid any write or schema-altering operations.

3. **Query Generation via LLM**
   - `Mongo.py` creates a `ChatOpenAI` instance through LangChain and initializes a **React-style agent** using `langgraph.prebuilt.create_react_agent`.
   - The agent interacts with a **custom MongoDB toolkit**, generating an **MQL aggregation pipeline** that matches the natural language query.

4. **Secure MongoDB Execution with PII Masking**
   - The query is executed through a **PII-protected database toolkit** (`MogoDBDatabaseToolkitPii`).
   - This toolkit wraps the base `MongoDBDatabase` implementation and overrides execution methods to:
     - Intercept aggregation results.
     - Apply **regex and NLP-based PII masking** using `RegexPIIMasker` or `JSONPIIMasker`.
     - Return **masked data** to the LLM for reasoning.

5. **Agent Reasoning on Masked Data**
   - The LLM processes masked results, ensuring no sensitive content is ever exposed to the model.
   - The response generated contains masked placeholders (e.g., `<EMAIL_0>`, `<PHONE_2>`).

6. **PII Unmasking for Final Output**
   - Once the final agent output is ready, the same masker instance performs **reverse mapping** (`pii_masker.unmask()`).
   - The mapping dictionary maintained during masking ensures that all placeholders are replaced with original values before display.

---

## Major Components and File-Level Architecture

### 1. `Mongo.py`
- Central orchestration module.
- Initializes the **LangChain chat model** and builds the **LangGraph agent**.
- Defines the link between user queries, MongoDB toolkits, and the masking/unmasking pipeline.
- Handles final unmasking before returning responses.

### 2. `langgraph_sample.py`
- Implements **stateful query flow control** using LangGraph.
- Contains nodes for:
  - Query modification.
  - Intent classification.
  - Access management (HR example).
- Example state includes metadata fields like `email`, `department`, `region`, etc.
- Produces structured state updates for downstream LLM reasoning.

### 3. `MONGODB_AGENT_SYS_PROMPT.py`
- Defines the **system-level LLM prompt**.
- Enforces strict query generation rules:
  - Only aggregation queries.
  - No schema modification.
  - Limited field projections.
  - PII tokens must be preserved.
- Provides schema examples and stylistic constraints for generated queries.

### 4. `MogoDBDatabaseToolkitPii.py`
- Extends the standard LangChain Mongo toolkit with **PII masking capabilities**.
- Overrides the aggregation method to:
  - Run queries securely (`coll.aggregate()`).
  - Apply `piiMasker.mask()` on returned documents.
  - Return masked JSON data to the agent.
- Designed for integration with multiple masking implementations.

### 5. `MaskingMongoDBDatabase.py`
- Subclass of the base `MongoDBDatabase`.
- Adds masking capability for `_find()` and similar query results.
- Employs the `JSONPIIMasker` class for deep masking of nested fields and arrays.

### 6. `JSONPIIMasker.py`
- Full-featured JSON-aware PII masking engine.
- Uses **spaCy (`en_core_web_lg`)** for named-entity recognition combined with **regex-based** rules.
- Supports:
  - EMAIL, PHONE, SSN, CREDIT CARD, ADDRESS, and NAME masking.
  - Nested data structures.
  - Deterministic token replacement with mapping retention.
- Key Methods:
  - `mask(data: Any)` → Returns masked data and mapping.
  - `unmask(data: Any)` → Reverses masking based on stored mapping.
- Maintains internal `self.mapping` and `self.counter` to ensure consistent token assignment.

### 7. `RegexPIIMasker.py` and `FieldBasedPIIMasker.py`
- Lightweight alternatives to `JSONPIIMasker`.
- Use field-name heuristics and regex-only matching for faster masking.
- Suitable for tabular or structured JSON with predictable keys.

### 8. `Multimedia_with_img_table.py`, `Mutlimedia.py`, `xls_to_json.py`, `xls_cdv.py`
- Utility modules for **data extraction** from multimedia and spreadsheet files.
- Support conversion of image-based or tabular data into JSON/text for ingestion and processing.
- Currently implemented as helper utilities, used during data pre-processing stages.

---

## PII Masking Lifecycle

| Stage | Module | Description |
|--------|---------|-------------|
| **Masking** | `JSONPIIMasker` / `RegexPIIMasker` | Replaces PII with tokens before sending results to the LLM. |
| **Reasoning** | `ChatOpenAI` (LangChain) | LLM works entirely on masked data; tokens preserved in context. |
| **Unmasking** | `Mongo.py` / `pii_masker.unmask()` | Tokens replaced back with original values for display. |

The masking–unmasking mapping is kept **in-memory** per session to prevent data leaks and maintain referential consistency across interactions.

---

## System Characteristics

| Aspect | Implementation |
|--------|----------------|
| **LLM Framework** | LangChain + LangGraph |
| **Query Type** | Aggregation-only MongoDB queries |
| **PII Protection** | NLP + Regex masking (JSON-aware) |
| **Mongo Toolkit** | Custom extension with masking layer |
| **Prompt Control** | Hardcoded system prompt enforcing safety |
| **Execution Safety** | Aggregation-only mode, limited fields, masked data |
| **Extensibility** | Modular architecture — interchangeable maskers and agents |
| **Use Case Example** | HR / employee data retrieval (email, department, region, etc.) |

---

## Key Design Principles

- **Mask before model:** All sensitive data is masked before entering LLM context.
- **Aggregation-only logic:** Prevents data mutation and enforces read-only behavior.
- **Composable toolkits:** PII masking, Mongo querying, and agent logic are modular, allowing new maskers or domains to be plugged in easily.
- **Deterministic unmasking:** Every token corresponds to a stable original value per session.
- **Air-gapped compatibility:** Can run in restricted environments with minimal cloud dependency.

---

## Current Limitations

- Mapping is maintained **per instance** — concurrent requests require isolated masker instances.
- No persistent storage of mask mappings (ephemeral only).
- Some files contain placeholders (`...`) indicating partial implementations.
- No `requirements.txt` or environment setup script included yet.
- Logging currently uses `print` statements instead of structured logging.

---

## Summary

Mongo-RAG currently provides a complete **end-to-end natural language interface to MongoDB** with integrated **PII masking** and **controlled LLM interaction**.  
The system ensures data security through its **mask-before-model** design while remaining modular enough for future extensions such as:
- Advanced retrieval pipelines (RAG),
- Custom embedding-based search,
- Multimodal data processing (text + tables + images),
- Enhanced concurrency for multi-user or batch queries.

This project serves as a strong foundation for secure, explainable, and compliant AI-driven data access.
