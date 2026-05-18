import streamlit as st
import requests
import time
import plotly.graph_objects as go

API = "http://localhost:8000"

st.set_page_config(page_title="CacheLayer", page_icon="⚡", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #02040a; }
[data-testid="metric-container"] {
    background: #090d1c; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 16px;
}
</style>
""", unsafe_allow_html=True)

st.title("⚡ CacheLayer")
st.caption("Semantic caching proxy for LLM APIs")

auto_refresh = st.sidebar.toggle("Auto refresh", value=True)
threshold = st.sidebar.slider("Similarity threshold", 0.60, 0.99, 0.80, 0.01)
st.sidebar.caption("Higher = stricter matching. 0.80 is recommended.")

if auto_refresh:
    time.sleep(2)
    st.rerun()

try:
    stats = requests.get(f"{API}/stats", timeout=2).json()
except:
    st.error("Proxy not running. Start it with: uvicorn src.proxy:app --port 8000")
    st.stop()

# Metrics row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Queries",  stats["total_queries"])
col2.metric("Cache Hits",     stats["cache_hits"])
col3.metric("Hit Rate",       f"{stats['hit_rate']*100:.1f}%")
col4.metric("Cost Saved",     f"${stats['cost_saved_usd']:.4f}")

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Hit Rate Gauge")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=stats["hit_rate"] * 100,
        title={"text": "Cache Hit Rate %"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#4f7cff"},
            "steps": [
                {"range": [0, 40],  "color": "#0d1222"},
                {"range": [40, 70], "color": "#111827"},
                {"range": [70, 100],"color": "#0f1929"},
            ],
            "threshold": {"line": {"color": "#00e5a0", "width": 3}, "value": 80}
        }
    ))
    fig.update_layout(
        paper_bgcolor="#02040a", font_color="#e8eeff", height=280
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Savings Summary")
    tokens = stats["tokens_saved"]
    cost   = stats["cost_saved_usd"]
    entries = stats["entries"]
    st.markdown(f"""
    | Metric | Value |
    |--------|-------|
    | Tokens Saved | {tokens:,} |
    | Cost Saved (GPT-4o rate) | ${cost:.4f} |
    | Cached Entries | {entries} |
    | Tokens per Entry avg | {tokens//max(entries,1)} |
    """)

    if stats.get("top_queries"):
        st.subheader("Most Requested")
        for item in stats["top_queries"]:
            st.markdown(f"**{item['hits']}x** — {item['query'][:60]}")

st.divider()
st.subheader("Test the Cache")
test_query = st.text_input("Enter a query to test")
if st.button("Test") and test_query:
    try:
        resp = requests.post(f"{API}/v1/chat/completions",
            json={"model":"gpt-4o","messages":[{"role":"user","content":test_query}]},
            headers={"Authorization":"Bearer test"}, timeout=30)
        data = resp.json()
        if data.get("cached"):
            st.success(f"✅ Cache HIT — {data['choices'][0]['message']['content']}")
        else:
            st.info("Cache miss — forwarded to OpenAI")
    except Exception as e:
        st.error(str(e))