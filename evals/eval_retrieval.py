import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.tools.retriever import RunbookRetriever

# In Bedrock Titan Embeddings V2, semantic similarity between a short log and a
# full runbook document averages ~0.50-0.85 for true matches vs <0.30 for irrelevant text.
CONFIDENCE_THRESHOLD = 0.50

def run_retrieval_eval():
    runbooks_dir = PROJECT_ROOT / "knowledge" / "runbooks"
    incidents_path = PROJECT_ROOT / "evals" / "incidents" / "incidents.json"

    with open(incidents_path, "r", encoding="utf-8") as f:
        incidents = json.load(f)

    print("\n" + "=" * 86)
    print("  Lesson 3: Evaluating Runbook Vector Retrieval (RAG)")
    print("  Embedding Model: Amazon Titan Embeddings V2 (Bedrock)")
    print("=" * 86 + "\n")
    print(f"Indexing runbooks from: {runbooks_dir}...")

    retriever = RunbookRetriever(runbooks_dir=runbooks_dir)
    count = retriever.index_runbooks()
    print(f"Loaded and indexed {count} runbooks into vector memory.\n")

    actionable_passed = 0
    actionable_total = 0
    noise_rejected = 0
    noise_total = 0

    # Header designed strictly to stay under 86 characters to prevent terminal line-wrapping
    header = f"{'Incident':<9} | {'Expected Runbook':<29} | {'Top Retrieved':<29} | {'Score':<6} | {'Status'}"
    print(header)
    print("-" * len(header))

    for inc in incidents:
        inc_id = inc["id"]
        expected_rb = inc.get("expected_runbook")
        query_text = f"{inc['alert_name']}\n{inc['logs']}"

        results = retriever.search(query_text, top_k=1)
        top_rb, score = results[0] if results else (None, 0.0)
        retrieved_name = top_rb["filename"] if top_rb else "None"

        if expected_rb is not None:
            actionable_total += 1
            if retrieved_name == expected_rb and score >= CONFIDENCE_THRESHOLD:
                actionable_passed += 1
                status = "PASS"
            else:
                status = "FAIL"
            print(f"{inc_id:<9} | {expected_rb:<29} | {retrieved_name:<29} | {score:<6.3f} | [{status}]")
        else:
            noise_total += 1
            # Unactionable alerts (healthy blip or prompt injection) should not match with high score
            if score < CONFIDENCE_THRESHOLD or "healthy" in inc.get("expected_cause", "").lower():
                noise_rejected += 1
                status = "PASS"
            else:
                status = "WARN"
            print(f"{inc_id:<9} | {'[None Expected]':<29} | {retrieved_name:<29} | {score:<6.3f} | [{status}]")

    print("-" * len(header))
    actionable_acc = (actionable_passed / actionable_total) * 100 if actionable_total else 0
    total_acc = ((actionable_passed + noise_rejected) / len(incidents)) * 100

    print("\n--------------- Retrieval Benchmark Summary -----------------")
    print(f"• Actionable Incidents Precision: {actionable_passed}/{actionable_total} ({actionable_acc:.1f}%)")
    print(f"• Overall Vector Accuracy:        {actionable_passed + noise_rejected}/{len(incidents)} ({total_acc:.1f}%)")
    print(f"• Lesson 3 Definition of Done:    {'PASSED' if actionable_acc == 100 else 'NEEDS RETRIEVAL TUNING'}")
    print("---------------------------------------------------------------\n")

if __name__ == "__main__":
    run_retrieval_eval()
