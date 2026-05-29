from root_agent.memory.retriever import MemoryRetriever
from root_agent.memory.store import MemoryStore


def test_store_append_and_read(tmp_path):
    store = MemoryStore(str(tmp_path / "G.md"), str(tmp_path / "L.md"))
    store.append("global", "alpha note")
    store.append("local", "beta note")
    assert "alpha note" in store.load_global()
    assert "beta note" in store.load_local()
    assert store.tiers_loaded()["global"] is True


def test_session_memory_is_scoped():
    store = MemoryStore("/no/such/G.md", "/no/such/L.md")
    store.append("session", "hello", conversation_id="c1")
    assert "hello" in store.session("c1")
    assert store.session("other") == ""
    assert store.session(None) == ""


def test_retriever_precedence(tmp_path):
    store = MemoryStore(str(tmp_path / "G.md"), str(tmp_path / "L.md"))
    store.append("global", "global pref")
    store.append("local", "local pref")
    store.append("session", "session pref", conversation_id="c1")
    ctx = MemoryRetriever(store, max_chars=4000).build_context("q", "c1")
    # Session is most specific and must come first, then local, then global.
    assert ctx.merged.index("Session") < ctx.merged.index("Local") < ctx.merged.index("Global")
    assert ctx.to_metadata()["memory_context"] == ctx.merged


def test_retriever_is_budget_bounded(tmp_path):
    store = MemoryStore(str(tmp_path / "G.md"), str(tmp_path / "L.md"))
    for i in range(50):
        store.append("global", f"topic {i} " + "x" * 40)
    ctx = MemoryRetriever(store, max_chars=200).build_context("topic 3", "c1")
    assert ctx.merged  # not empty
    assert len(ctx.merged) <= 400  # bounded near budget + headers
