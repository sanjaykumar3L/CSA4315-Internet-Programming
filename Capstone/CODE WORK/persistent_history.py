"""Persistent audit records backed by a private Vercel Blob store.

This is an append-only document repository for the academic workbench, not a
relational database. Each immutable record has its own path, so concurrent
test executions don't overwrite one another. Avoid storing real credentials
or sensitive user data in these demonstration records.
"""
import json
import secrets
import time
from datetime import datetime, timezone

from vercel.blob.sync import put_blob, query_blobs, get_blob
from vercel.blob.errors import BlobNotFoundError

PREFIX = "capstone-records/v1/"


def create_record(payload):
    # IDs remain safely representable by JavaScript as integers.
    # Wall-clock ms + 3 random digits; collision-resistant pathname uses UUID.
    import uuid
    record_id = int(time.time() * 1000) * 1000 + secrets.randbelow(1000)
    pathname = f"{PREFIX}{record_id}-{uuid.uuid4().hex}.json"
    record = {
        "id": record_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        **payload,
    }
    # Never silently claim success if durable storage failed.
    put_blob(pathname, json.dumps(record, ensure_ascii=False).encode("utf-8"),
             access="private", content_type="application/json",
             add_random_suffix=False)
    return record_id


def _read_blob(path):
    try:
        result = get_blob(path, access="private")
    except BlobNotFoundError:
        return None
    if result is None:
        return None
    return json.loads(result.body.decode("utf-8"))


def list_records(limit=100):
    # The current Vercel Python SDK yields a paginated iterator of blob entries.
    candidates = list(query_blobs(prefix=PREFIX, page_size=1000))
    candidates.sort(key=lambda blob: blob.pathname, reverse=True)
    records = []
    for blob in candidates[:max(1, limit)]:
        record = _read_blob(blob.pathname)
        if record is not None:
            record["validation_errors_list"] = record.get("validation_errors_list", [])
            records.append(record)
    return records


def get_record(record_id):
    target = str(int(record_id)) + "-"
    for blob in query_blobs(prefix=PREFIX + target, page_size=20):
        record = _read_blob(blob.pathname)
        if record and int(record.get("id", -1)) == int(record_id):
            record["validation_errors_list"] = record.get("validation_errors_list", [])
            return record
    return None


SERVICE_PREFIX = "capstone-services/v1/"


def create_service(service_name, target_namespace, endpoint_url, wsdl_content):
    import uuid
    service_id = int(time.time() * 1000) * 1000 + secrets.randbelow(1000)
    pathname = f"{SERVICE_PREFIX}{service_id}-{uuid.uuid4().hex}.json"
    document = {
        "id": service_id,
        "service_name": str(service_name)[:200],
        "target_namespace": str(target_namespace)[:500],
        "endpoint_url": str(endpoint_url)[:1000],
        "wsdl_content": str(wsdl_content)[:150000],
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    put_blob(pathname, json.dumps(document, ensure_ascii=False).encode("utf-8"),
             access="private", content_type="application/json",
             add_random_suffix=False)
    return service_id


def list_services(limit=100):
    entries = list(query_blobs(prefix=SERVICE_PREFIX, page_size=1000))
    entries.sort(key=lambda blob: blob.pathname, reverse=True)
    records = []
    for entry in entries[:max(1, limit)]:
        doc = _read_blob(entry.pathname)
        if doc is not None:
            # Keep WSDL content in private storage; return metadata to UI.
            doc.pop("wsdl_content", None)
            records.append(doc)
    return records

