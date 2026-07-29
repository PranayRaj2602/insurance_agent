"""
Downloads all P&C Insurance PDFs from Foundry media set into ./data/
"""

import os
import requests

FOUNDRY_HOST = "https://echospilot.usw-23.palantirfoundry.com"
TOKEN = os.environ.get("FOUNDRY_TOKEN", "")  # set in .env or environment
DATASET_RID = "ri.foundry.main.dataset.ad832b62-04f8-4de0-af74-e65ddf150c48"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")

HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def query_dataset():
    """Fetch all (path, media_item_rid) pairs via Foundry SQL."""
    url = f"{FOUNDRY_HOST}/foundry-sql-server/api/queries"
    sql = f"SELECT path, media_item_rid, claim_id, file_type FROM `{DATASET_RID}` LIMIT 1000"
    resp = requests.post(url, headers=HEADERS, json={"query": sql}, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    # Response format: {"columns": [...], "rows": [[...], ...]}
    columns = [c["name"] for c in data["columns"]]
    rows = data["rows"]
    return [dict(zip(columns, row)) for row in rows]


def download_media_item(media_item_rid: str, filename: str, output_dir: str):
    """Download a single media item to output_dir/filename."""
    # Try v1 endpoint first, fall back to v2
    for endpoint in [
        f"{FOUNDRY_HOST}/api/v1/mediaItems/{media_item_rid}/content",
        f"{FOUNDRY_HOST}/api/v2/mediaItems/{media_item_rid}/content",
        f"{FOUNDRY_HOST}/media/api/mediaItems/{media_item_rid}/content",
    ]:
        resp = requests.get(endpoint, headers=HEADERS, stream=True, timeout=60)
        if resp.status_code == 200:
            out_path = os.path.join(output_dir, filename)
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True, endpoint
        if resp.status_code not in (404, 405):
            resp.raise_for_status()
    return False, None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Querying dataset for file list...")
    try:
        files = query_dataset()
    except Exception as e:
        print(f"SQL query failed ({e}), falling back to hardcoded list from earlier query.")
        files = HARDCODED_FILES

    print(f"Found {len(files)} files to download.\n")

    success, failed = 0, []
    for i, row in enumerate(files, 1):
        path = row.get("path") or row.get("filename", "unknown.pdf")
        rid = row.get("media_item_rid")
        claim_id = row.get("claim_id", "")
        file_type = row.get("file_type", "")

        if not rid:
            print(f"[{i}/{len(files)}] SKIP {path} — no media_item_rid")
            continue

        # Organise by claim_id subfolder
        claim_dir = os.path.join(OUTPUT_DIR, claim_id) if claim_id else OUTPUT_DIR
        os.makedirs(claim_dir, exist_ok=True)

        filename = os.path.basename(path)
        out_path = os.path.join(claim_dir, filename)

        if os.path.exists(out_path):
            print(f"[{i}/{len(files)}] EXISTS  {claim_id}/{filename}")
            success += 1
            continue

        print(f"[{i}/{len(files)}] Downloading  {claim_id}/{filename} ({file_type})...", end=" ", flush=True)
        ok, used_endpoint = download_media_item(rid, filename, claim_dir)
        if ok:
            size = os.path.getsize(out_path)
            print(f"OK ({size:,} bytes)")
            success += 1
        else:
            print(f"FAILED (all endpoints returned 404/405)")
            failed.append(path)

    print(f"\nDone. {success}/{len(files)} downloaded.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            print(f"  {f}")


# Fallback list from SQL query (used if live query fails)
HARDCODED_FILES = [
    {"claim_id": "CLM-00000001", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0135-73f6-988e-c2106c54b1ce"},
    {"claim_id": "CLM-00000001", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1e77-72a5-84fe-83f94f1af1e3"},
    {"claim_id": "CLM-00000001", "file_type": "Fnol", "path": "fnol_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0c35-7b8f-a491-a388ff370350"},
    {"claim_id": "CLM-00000001", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f1a5-7eae-aab8-97382fecff05"},
    {"claim_id": "CLM-00000001", "file_type": "Policy", "path": "policy_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-797f-7ec2-bbf3-e9ec458560a2"},
    {"claim_id": "CLM-00000001", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1222-7a37-a62c-91abdc2fe406"},
    {"claim_id": "CLM-00000001", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000001.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-d4fb-7c50-8ef4-4d89a2d18983"},
    {"claim_id": "CLM-00000002", "file_type": "Reserve Analysis", "path": "reserve_analysis_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-242b-7fde-a7cb-38b1aba52b6c"},
    {"claim_id": "CLM-00000002", "file_type": "Fnol", "path": "fnol_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0c35-7b8f-a491-a388ff37034f"},
    {"claim_id": "CLM-00000002", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-d4fa-780e-8ee2-3823d361c481"},
    {"claim_id": "CLM-00000002", "file_type": "Payment Authorization", "path": "payment_authorization_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1b54-75ad-8214-ec32ff18c647"},
    {"claim_id": "CLM-00000002", "file_type": "Reopening Notice", "path": "reopening_notice_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-242b-7fde-a7cb-38b1aba52b6a"},
    {"claim_id": "CLM-00000002", "file_type": "Final Settlement", "path": "final_settlement_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0af0-7056-9045-a2334faeaa97"},
    {"claim_id": "CLM-00000002", "file_type": "Policy", "path": "policy_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-73ca-759d-a276-3a3cc7c4eee6"},
    {"claim_id": "CLM-00000002", "file_type": "Settlement Agreement", "path": "settlement_agreement_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-26e5-7dd5-8835-cf7b71326967"},
    {"claim_id": "CLM-00000002", "file_type": "Closure Summary", "path": "closure_summary_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-02b2-7e2d-98c3-22cbd31f25cb"},
    {"claim_id": "CLM-00000002", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-02b2-7e2d-98c3-22cbd31f25cd"},
    {"claim_id": "CLM-00000002", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-141b-7b6a-910d-9b8d373ea25a"},
    {"claim_id": "CLM-00000002", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f1a5-7eae-aab8-97382fecff06"},
    {"claim_id": "CLM-00000002", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000002.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1e77-72a5-84fe-83f94f1af1e4"},
    {"claim_id": "CLM-00000003", "file_type": "Claim Proof Of Loss", "path": "claim_proof_of_loss_CLM-00000003.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-e962-7a10-83c3-a68488f76b17"},
    {"claim_id": "CLM-00000003", "file_type": "Claim Fnol", "path": "claim_fnol_CLM-00000003.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-de89-7aeb-85dd-3495684bd483"},
    {"claim_id": "CLM-00000003", "file_type": "Policy", "path": "policy_CLM-00000003.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-797f-7ec2-bbf3-e9ec4585609f"},
    {"claim_id": "CLM-00000003", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000003.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f1a5-7eae-aab8-97382fecff03"},
    {"claim_id": "CLM-00000004", "file_type": "Fnol", "path": "fnol_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0c35-7b8f-a491-a388ff37034e"},
    {"claim_id": "CLM-00000004", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-d4fb-7c50-8ef4-4d89a2d18985"},
    {"claim_id": "CLM-00000004", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-155c-7e74-ba9e-0abdd6cb762e"},
    {"claim_id": "CLM-00000004", "file_type": "Policy", "path": "policy_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-797f-7ec2-bbf3-e9ec458560a0"},
    {"claim_id": "CLM-00000004", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-05b9-7a55-b4d6-a77a6472161c"},
    {"claim_id": "CLM-00000004", "file_type": "Final Settlement", "path": "final_settlement_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0c35-7b8f-a491-a388ff370351"},
    {"claim_id": "CLM-00000004", "file_type": "Reserve Analysis", "path": "reserve_analysis_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-22fd-74d1-afa7-69945c6b7c7e"},
    {"claim_id": "CLM-00000004", "file_type": "Settlement Agreement", "path": "settlement_agreement_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-26e5-7dd5-8835-cf7b71326965"},
    {"claim_id": "CLM-00000004", "file_type": "Payment Authorization", "path": "payment_authorization_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1b54-75ad-8214-ec32ff18c649"},
    {"claim_id": "CLM-00000004", "file_type": "Closure Summary", "path": "closure_summary_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-02b2-7e2d-98c3-22cbd31f25ce"},
    {"claim_id": "CLM-00000004", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1e77-72a5-84fe-83f94f1af1e5"},
    {"claim_id": "CLM-00000004", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000004.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f1a5-7eae-aab8-97382fecff02"},
    {"claim_id": "CLM-00000005", "file_type": "Fnol", "path": "fnol_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0dc5-721c-8858-c362032cbf0b"},
    {"claim_id": "CLM-00000005", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-05b9-7a55-b4d6-a77a6472161b"},
    {"claim_id": "CLM-00000005", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1d42-7706-aae9-bd71ba97ff3d"},
    {"claim_id": "CLM-00000005", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-cf4b-74f4-bff8-5a8ffab4006d"},
    {"claim_id": "CLM-00000005", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f1a5-7eae-aab8-97382fecff04"},
    {"claim_id": "CLM-00000005", "file_type": "Policy", "path": "policy_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-797f-7ec2-bbf3-e9ec458560a1"},
    {"claim_id": "CLM-00000005", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000005.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-155c-7e74-ba9e-0abdd6cb762f"},
    {"claim_id": "CLM-00000006", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0465-7213-b562-ffe90e37f44b"},
    {"claim_id": "CLM-00000006", "file_type": "Policy", "path": "policy_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-7e7e-7dba-ae0d-2cc435f5735a"},
    {"claim_id": "CLM-00000006", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1e77-72a5-84fe-83f94f1af1e2"},
    {"claim_id": "CLM-00000006", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f407-7d80-95e6-d6f5452af51c"},
    {"claim_id": "CLM-00000006", "file_type": "Fnol", "path": "fnol_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0f04-7798-87f5-3d784144b6bd"},
    {"claim_id": "CLM-00000006", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-d4fb-7c50-8ef4-4d89a2d18984"},
    {"claim_id": "CLM-00000006", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000006.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-155c-7e74-ba9e-0abdd6cb762d"},
    {"claim_id": "CLM-00000007", "file_type": "Policy", "path": "policy_CLM-00000007.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-7e7e-7dba-ae0d-2cc435f57359"},
    {"claim_id": "CLM-00000008", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-155c-7e74-ba9e-0abdd6cb7630"},
    {"claim_id": "CLM-00000008", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-2026-7bb6-bd43-4c1864fbdeae"},
    {"claim_id": "CLM-00000008", "file_type": "Fnol", "path": "fnol_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0f04-7798-87f5-3d784144b6bf"},
    {"claim_id": "CLM-00000008", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-da03-736f-aa2b-ee9efd664483"},
    {"claim_id": "CLM-00000008", "file_type": "Reserve Analysis", "path": "reserve_analysis_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-26e5-7dd5-8835-cf7b71326966"},
    {"claim_id": "CLM-00000008", "file_type": "Policy", "path": "policy_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-7e7e-7dba-ae0d-2cc435f5735c"},
    {"claim_id": "CLM-00000008", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f407-7d80-95e6-d6f5452af51e"},
    {"claim_id": "CLM-00000008", "file_type": "Settlement Agreement", "path": "settlement_agreement_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-25cc-7731-846d-fae6aec0c3bc"},
    {"claim_id": "CLM-00000008", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-05b9-7a55-b4d6-a77a6472161d"},
    {"claim_id": "CLM-00000008", "file_type": "Payment Authorization", "path": "payment_authorization_CLM-00000008.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1b54-75ad-8214-ec32ff18c648"},
    {"claim_id": "CLM-00000009", "file_type": "Policy", "path": "policy_CLM-00000009.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-7e7e-7dba-ae0d-2cc435f5735b"},
    {"claim_id": "CLM-00000010", "file_type": "Policy", "path": "policy_CLM-00000010.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-7e7e-7dba-ae0d-2cc435f5735d"},
    {"claim_id": "CLM-00000011", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-2151-7526-9634-39b419601671"},
    {"claim_id": "CLM-00000011", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f407-7d80-95e6-d6f5452af51b"},
    {"claim_id": "CLM-00000011", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1854-7f22-8f6f-6daeb17477f1"},
    {"claim_id": "CLM-00000011", "file_type": "Fnol", "path": "fnol_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0f04-7798-87f5-3d784144b6c0"},
    {"claim_id": "CLM-00000011", "file_type": "Policy", "path": "policy_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8302-7956-b6e2-e45f39bb4257"},
    {"claim_id": "CLM-00000011", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-05b9-7a55-b4d6-a77a6472161e"},
    {"claim_id": "CLM-00000011", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000011.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-da03-736f-aa2b-ee9efd664486"},
    {"claim_id": "CLM-00000012", "file_type": "Claim Proof Of Loss", "path": "claim_proof_of_loss_CLM-00000012.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-e962-7a10-83c3-a68488f76b18"},
    {"claim_id": "CLM-00000012", "file_type": "Claim Fnol", "path": "claim_fnol_CLM-00000012.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-de89-7aeb-85dd-3495684bd482"},
    {"claim_id": "CLM-00000012", "file_type": "Policy", "path": "policy_CLM-00000012.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8303-7658-b8e8-3914b6f4cca1"},
    {"claim_id": "CLM-00000012", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000012.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f407-7d80-95e6-d6f5452af51d"},
    {"claim_id": "CLM-00000013", "file_type": "Policy", "path": "policy_CLM-00000013.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8303-7658-b8e8-3914b6f4cca4"},
    {"claim_id": "CLM-00000014", "file_type": "Policy", "path": "policy_CLM-00000014.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8303-7658-b8e8-3914b6f4cca2"},
    {"claim_id": "CLM-00000015", "file_type": "Policy", "path": "policy_CLM-00000015.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8303-7658-b8e8-3914b6f4cca3"},
    {"claim_id": "CLM-00000016", "file_type": "Policy", "path": "policy_CLM-00000016.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8706-7807-a0c1-daa939990bd7"},
    {"claim_id": "CLM-00000017", "file_type": "Coverage Determination", "path": "coverage_determination_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-08ee-7810-93d8-c6c553b4d188"},
    {"claim_id": "CLM-00000017", "file_type": "Proof Of Loss", "path": "proof_of_loss_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-2151-7526-9634-39b419601672"},
    {"claim_id": "CLM-00000017", "file_type": "Payment Authorization", "path": "payment_authorization_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1b54-75ad-8214-ec32ff18c64a"},
    {"claim_id": "CLM-00000017", "file_type": "Settlement Agreement", "path": "settlement_agreement_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-28c2-77ba-83fa-5601cc8f4b9c"},
    {"claim_id": "CLM-00000017", "file_type": "Investigation Report", "path": "investigation_report_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-1716-77d7-a030-b3de872fdc85"},
    {"claim_id": "CLM-00000017", "file_type": "Fnol", "path": "fnol_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-0f04-7798-87f5-3d784144b6be"},
    {"claim_id": "CLM-00000017", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f407-7d80-95e6-d6f5452af51a"},
    {"claim_id": "CLM-00000017", "file_type": "Policy", "path": "policy_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8706-7807-a0c1-daa939990bd8"},
    {"claim_id": "CLM-00000017", "file_type": "Reserve Analysis", "path": "reserve_analysis_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab854-26e5-7dd5-8835-cf7b71326968"},
    {"claim_id": "CLM-00000017", "file_type": "Adjuster Notes", "path": "adjuster_notes_CLM-00000017.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-da03-736f-aa2b-ee9efd664482"},
    {"claim_id": "CLM-00000018", "file_type": "Policy", "path": "policy_CLM-00000018.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8706-7807-a0c1-daa939990bd9"},
    {"claim_id": "CLM-00000019", "file_type": "Claim Fnol", "path": "claim_fnol_CLM-00000019.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-de89-7aeb-85dd-3495684bd481"},
    {"claim_id": "CLM-00000019", "file_type": "Claim Proof Of Loss", "path": "claim_proof_of_loss_CLM-00000019.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-e962-7a10-83c3-a68488f76b15"},
    {"claim_id": "CLM-00000019", "file_type": "Claimant Statement", "path": "claimant_statement_CLM-00000019.pdf", "media_item_rid": "ri.mio.main.media-item.019ab853-f834-7fbe-9430-c0b926b9bb8a"},
    {"claim_id": "CLM-00000019", "file_type": "Policy", "path": "policy_CLM-00000019.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8706-7807-a0c1-daa939990bda"},
    {"claim_id": "CLM-00000020", "file_type": "Policy", "path": "policy_CLM-00000020.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8706-7807-a0c1-daa939990bdb"},
    {"claim_id": "CLM-00000021", "file_type": "Policy", "path": "policy_CLM-00000021.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8a98-75ca-87f7-ad867cca8445"},
    {"claim_id": "CLM-00000022", "file_type": "Policy", "path": "policy_CLM-00000022.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8a98-75ca-87f7-ad867cca8449"},
    {"claim_id": "CLM-00000023", "file_type": "Policy", "path": "policy_CLM-00000023.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8a98-75ca-87f7-ad867cca8448"},
    {"claim_id": "CLM-00000024", "file_type": "Policy", "path": "policy_CLM-00000024.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8a98-75ca-87f7-ad867cca8446"},
    {"claim_id": "CLM-00000025", "file_type": "Policy", "path": "policy_CLM-00000025.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8a98-75ca-87f7-ad867cca8447"},
    {"claim_id": "CLM-00000026", "file_type": "Policy", "path": "policy_CLM-00000026.pdf", "media_item_rid": "ri.mio.main.media-item.019ab8af-8dd7-755d-bf0a-ff491634b826"},
]


if __name__ == "__main__":
    main()
