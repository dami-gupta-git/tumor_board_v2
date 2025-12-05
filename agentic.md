## 🤖 Tumor Board Agentic Architecture (v2)

This project implements a multi-layered, context-aware agent system designed to emulate and enhance the decision-making process of a real-world multi-disciplinary Tumor Board.

The architecture focuses on two core innovations: **Semantic State Management** and **Protocol Governance** to ensure safe, auditable, and efficient clinical recommendations.

---

### 1. Multi-Layered Agent Structure

The system uses a hierarchical design for specialized analysis and conflict resolution:

| Layer | Agent Role(s) | Function |
| :--- | :--- | :--- |
| **L3: Escalation** | **Chairperson Agent** | Final decision authority. Resolves conflicts escalated from L2 using the full case context and explicit protocols. |
| **L2: MDT Debate** | Specialist Agents (Oncologist, Surgeon, Radiologist, Pathologist) | Engage in dynamic debate, simulating consensus-building and specialized analysis of the case. |
| **L1: Triage & Routing** | **Orchestrator Agent** | Initial intake and control. Uses the Case Embedding to assess complexity and route the case to the appropriate layer (L2 for complex, or a fast-track Guideline Check for simple). |

### 2. Core Architectural Components

The agentic approach is driven by two novel mechanisms that flow through all layers:

#### A. Persistent Semantic State: The Case Embedding

A dense vector representation of the entire patient record (pathology, imaging reports, history) is generated and stored. This vector serves three critical purposes:

1.  **Semantic Routing:** The L1 Orchestrator compares the case embedding against standard protocol embeddings to determine complexity and the necessary agent layer.
2.  **RAG Grounding:** Used to perform highly relevant retrieval from a knowledge base (similar past cases, guidelines) to ground agent recommendations.
3.  **Context Flow:** Ensures that every agent has access to the full, non-diluted meaning of the case, even as conversation history grows long.

#### B. Protocol Governance: Meta-Parameters

A set of explicit rules that dictate how the agents interact and when to involve human oversight. These parameters transform the debate into a clinically governed process:

* **Escalation Logic:** Defines the `conflict_threshold` (e.g., $70\%$ disagreement) that automatically triggers the Chairperson Agent (L3).
* **Conversation Protocol:** Sets the `turn_limit`, `speaker_order`, and `required_consensus` level for the MDT debate.
* **Authority Hierarchy:** Establishes which agent's input (e.g., Pathologist's diagnosis) carries weighted authority in the final synthesis.

---

### 💡 Outcome

This architecture ensures the system is not only intelligent but also **safe, auditable, and aligned with clinical protocols**, moving AI from simple decision support toward governed, autonomous process management.