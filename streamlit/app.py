"""TumorBoard Streamlit Application - Clean single-container variant assessment tool."""
import streamlit as st
import pandas as pd
import asyncio
import json
from streamlit_searchbox import st_searchbox
from backend import assess_variant, batch_assess_variants, validate_gold_standard, fetch_tumor_type_suggestions

st.set_page_config(page_title="TumorBoard", page_icon="🧬", layout="wide")
st.title("🧬 TumorBoard: Variant Actionability Assessment")

MODELS = {
    "OpenAI GPT-4o-mini": "gpt-4o-mini",
    "OpenAI GPT-4o": "gpt-4o",
    "Anthropic Claude 3 Haiku": "claude-3-haiku-20240307",
    "Google Gemini 1.5 Pro": "gemini/gemini-1.5-pro",
    "Groq Llama 3.1 70B": "groq/llama-3.1-70b-versatile"
}

tab1, tab2, tab3 = st.tabs(["🔬 Single Variant", "📊 Batch Upload", "✅ Validation"])

# TAB 1: Single Variant
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Input")

        # Initialize session state for form fields if not exists
        if 'input_gene' not in st.session_state:
            st.session_state['input_gene'] = "BRAF"
        if 'input_variant' not in st.session_state:
            st.session_state['input_variant'] = "V600E"
        if 'input_tumor' not in st.session_state:
            st.session_state['input_tumor'] = "Melanoma"

        gene = st.text_input("Gene Symbol", value=st.session_state['input_gene'], help="e.g., BRAF, EGFR, TP53", key="gene_input")
        variant = st.text_input("Variant", value=st.session_state['input_variant'], help="e.g., V600E, L858R", key="variant_input")

        # Fetch tumor type suggestions when gene and variant are provided
        tumor_suggestions = []
        if gene and variant and (gene != st.session_state.get('last_gene') or variant != st.session_state.get('last_variant')):
            with st.spinner("Fetching tumor types..."):
                tumor_suggestions = asyncio.run(fetch_tumor_type_suggestions(gene, variant))
                st.session_state['tumor_suggestions'] = tumor_suggestions
                st.session_state['last_gene'] = gene
                st.session_state['last_variant'] = variant
        elif 'tumor_suggestions' in st.session_state:
            tumor_suggestions = st.session_state['tumor_suggestions']

        # Show tumor type input with typeahead search
        if tumor_suggestions:
            st.info(f"💡 Found {len(tumor_suggestions)} tumor types. Start typing to search.")

            # Define search function that has access to tumor_suggestions
            def search_tumor_types(searchterm: str):
                """Search function for typeahead widget."""
                if not searchterm:
                    # Show top 20 suggestions when no query
                    return tumor_suggestions[:20]

                # Filter suggestions that match the search term (case-insensitive)
                searchterm_upper = searchterm.upper()
                matches = [
                    item for item in tumor_suggestions
                    if searchterm_upper in item.upper()
                ]
                return matches[:20]  # Limit to 20 results

            tumor = st_searchbox(
                search_tumor_types,
                label="Tumor Type (optional)",
                placeholder="Type to search (e.g., NSCLC, Melanoma)...",
                key="tumor_searchbox",
                clear_on_submit=False
            )
        else:
            tumor = st.text_input("Tumor Type (optional)", value=st.session_state['input_tumor'], help="e.g., Melanoma, Lung Adenocarcinoma", key="tumor_input")
            st.caption("⚠️ The tumor type should exactly match values from the OncoTree ontology or CIViC database")

        model_name = st.selectbox("LLM Model", list(MODELS.keys()))
        temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.05)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            assess_btn = st.button("🔍 Assess Variant", type="primary", use_container_width=True)
        with col_btn2:
            clear_btn = st.button("🔄 Clear/Reset", use_container_width=True)

        if clear_btn:
            # Reset all input fields to default values
            st.session_state['input_gene'] = "BRAF"
            st.session_state['input_variant'] = "V600E"
            st.session_state['input_tumor'] = "Melanoma"

            # Clear cache
            for key in ['tumor_suggestions', 'last_gene', 'last_variant']:
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()

    with col2:
        if assess_btn:
            if not gene or not variant:
                st.error("Gene and variant are required")
            else:
                # Validate variant type before processing
                from tumorboard.utils.variant_normalization import normalize_variant, VariantNormalizer
                normalized = normalize_variant(gene, variant)
                variant_type = normalized['variant_type']

                if variant_type not in VariantNormalizer.ALLOWED_VARIANT_TYPES:
                    st.error(
                        f"❌ Unsupported variant type: **{variant_type}**\n\n"
                        f"Only **SNPs and small indels** are supported:\n"
                        f"- Missense mutations (e.g., V600E)\n"
                        f"- Nonsense mutations (e.g., R172*)\n"
                        f"- Small insertions (e.g., ins)\n"
                        f"- Small deletions (e.g., del)\n"
                        f"- Frameshift mutations (e.g., fs)\n\n"
                        f"Your variant '{variant}' is classified as '{variant_type}'."
                    )
                else:
                    with st.spinner(f"🔬 Analyzing {gene} {variant}... Fetching evidence from CIViC, ClinVar, and COSMIC databases"):
                        result = asyncio.run(assess_variant(gene, variant, tumor or None, MODELS[model_name], temperature))
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.success(f"✅ Assessment Complete: {result['assessment']['tier']}")
                            metrics_col = st.columns(4)
                            metrics_col[0].metric("Tier", result['assessment']['tier'])
                            metrics_col[1].metric("Confidence", f"{result['assessment']['confidence']:.1%}")
                            metrics_col[2].metric("Evidence", result['assessment'].get('evidence_strength', 'N/A'))
                            metrics_col[3].metric("Therapies", len(result.get('recommended_therapies', [])))
                            st.subheader("Complete Assessment")
                            st.json(result)
                            st.download_button("📥 Download JSON", json.dumps(result, indent=2),
                                             f"{gene}_{variant}_assessment.json", "application/json")
                            # Future features placeholders
                            with st.expander("🧬 Protein Structure (Coming Soon)"):
                                st.info("ESMFold visualization will be added here")
                            with st.expander("🤖 Agent Workflow (Coming Soon)"):
                                st.info("Multi-agent analysis pipeline will be added here")

# TAB 2: Batch Upload
with tab2:
    st.subheader("Batch Variant Analysis")
    st.markdown("**CSV Format:** Must contain `gene`, `variant`, and optionally `tumor_type` columns")
    col1, col2 = st.columns([1, 1])
    with col1:
        model_name_batch = st.selectbox("LLM Model", list(MODELS.keys()), key="batch_model")
    with col2:
        temperature_batch = st.slider("Temperature", 0.0, 1.0, 0.1, 0.05, key="batch_temp")

    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head(), use_container_width=True)
        if st.button("🚀 Process Batch", type="primary"):
            if 'gene' not in df.columns or 'variant' not in df.columns:
                st.error("CSV must contain 'gene' and 'variant' columns")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                variants = [{"gene": row.get('gene'), "variant": row.get('variant'),
                           "tumor_type": row.get('tumor_type', None)} for _, row in df.iterrows()]
                results = asyncio.run(batch_assess_variants(variants, MODELS[model_name_batch],
                          temperature_batch, lambda i, t: (progress_bar.progress(i/t),
                          status_text.text(f"Processing {i}/{t}..."))))
                status_text.text("✅ Batch processing complete!")
                progress_bar.progress(1.0)
                results_df = pd.DataFrame([{"Gene": r['variant']['gene'], "Variant": r['variant']['variant'],
                    "Tumor": r['variant'].get('tumor_type', 'N/A'), "Tier": r['assessment']['tier'],
                    "Confidence": f"{r['assessment']['confidence']:.1%}",
                    "Therapies": len(r.get('recommended_therapies', []))} for r in results if 'error' not in r])
                st.dataframe(results_df, use_container_width=True)
                st.download_button("📥 Download Results CSV", results_df.to_csv(index=False),
                                 "batch_results.csv", "text/csv")
                st.download_button("📥 Download Full JSON", json.dumps(results, indent=2),
                                 "batch_results.json", "application/json")

# TAB 3: Validation
with tab3:
    st.subheader("Gold Standard Validation")
    st.markdown("""Run validation against the 50-case gold standard dataset to benchmark LLM accuracy.
    **Metrics:** Overall accuracy, per-tier precision/recall/F1, confusion matrix, failure analysis""")
    col1, col2 = st.columns([1, 2])
    with col1:
        model_name_val = st.selectbox("LLM Model", list(MODELS.keys()), key="val_model")
        temperature_val = st.slider("Temperature", 0.0, 1.0, 0.1, 0.05, key="val_temp")
        gold_standard_path = st.text_input("Gold Standard Path", value="/app/benchmarks/gold_standard.json")
        validate_btn = st.button("▶️ Run Validation", type="primary", use_container_width=True)

    with col2:
        if validate_btn:
            with st.spinner("Running validation..."):
                validation_results = asyncio.run(validate_gold_standard(gold_standard_path,
                                                 MODELS[model_name_val], temperature_val))
                if "error" in validation_results:
                    st.error(validation_results["error"])
                else:
                    st.success(f"✅ Validation Complete: {validation_results['overall_accuracy']:.1%} accuracy")
                    metrics = st.columns(3)
                    metrics[0].metric("Accuracy", f"{validation_results['overall_accuracy']:.1%}")
                    metrics[1].metric("Total Cases", validation_results['total_cases'])
                    metrics[2].metric("Correct", validation_results['correct_predictions'])
                    st.subheader("Per-Tier Performance")
                    tier_df = pd.DataFrame(validation_results['per_tier_metrics']).T
                    st.dataframe(tier_df, use_container_width=True)
                    st.download_button("📥 Download Validation Report",
                                     json.dumps(validation_results, indent=2),
                                     "validation_results.json", "application/json")