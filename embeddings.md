When standard databases return little or no evidence for a variant, we fall back to semantic search over a vector index of known actionable variants and clinical guidelines. Using biomedical embeddings (PubMedBERT), the system finds structurally similar variants with established tiers and retrieves relevant NCCN/ESMO guideline sections—so a novel BRAF V601E can draw on the strong evidence base for V600E, and rare variants aren't automatically relegated to "unknown significance" just because they lack exact database entries. This directly addresses the long-tail problem where most real-world variants have sparse coverage, while keeping retrieval grounded in curated, authoritative sources rather than noisy literature search.

1. Known Variant Index
Take every variant with established actionability—from your gold standard dataset, CIViC's curated entries, or a reference set you build over time. For each, create a text representation and embed it:

![alt text](image-1.png)

Include the gene, variant, tumor type, tier, associated drugs, functional annotations (domain, mutation effect)—whatever helps define similarity. Store the embedding alongside metadata (tier, evidence sources, therapies) in ChromaDB or similar.
2. Guideline Chunks Index
Take NCCN/ESMO guidelines, split into semantically coherent chunks (a few paragraphs each, roughly 500-1000 tokens), and embed each:
![alt text](image-2.png)

![alt text](image-3.png)

![alt text](image-4.png)

------------------------------------------

Embeddings are vector representations of text that capture semantic meaning—similar concepts end up close together in vector space. Here's how they'd be useful in TumorBoard:
1. Similar variant retrieval (most valuable for you)
When databases return nothing for a novel variant, embed the query (variant + tumor context) and find the nearest neighbors among variants you do have evidence for:
Query: "BRAF V601E melanoma" → embedding → search vector DB
Returns: "BRAF V600E melanoma" (0.94 similarity)
         "BRAF V600K melanoma" (0.91 similarity)
Now the LLM can reason: "No direct evidence for V601E, but structurally similar V600E in the same tumor type is Tier I with vemurafenib sensitivity." That's a meaningful fallback for rare variants.
2. Literature retrieval (RAG)
Embed PubMed abstracts into a vector database. When assessing a variant, embed the query and retrieve semantically relevant papers—not just keyword matches. This catches papers that discuss the variant differently than your query phrased it, or related variants in the same pathway.
3. Guideline section retrieval
Embed chunks of NCCN/ESMO guidelines. When a query comes in, pull the most relevant sections rather than stuffing entire guidelines into context.
4. Case similarity (your "Case Embedding" idea)
Embed the full clinical context—variant, tumor type, stage, co-mutations, prior therapy. Retrieve similar cases to see how analogous patients were managed. This is more ambitious but potentially useful for the patient-level analysis roadmap.
Practical stack:

Embeddings: PubMedBERT or BioBERT (domain-specific, much better than general-purpose for biomedical text)
Vector DB: ChromaDB (local, simple) or Pinecone (hosted, scales)
You embed once at index time, then query embeddings are computed on the fly

The key insight: embeddings let you find relevant information even when exact keywords don't match, which is exactly the problem with rare variants.