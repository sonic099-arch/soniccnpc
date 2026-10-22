from uuid import UUID, uuid4
import pytest
from app.api.resources import RESOURCES

PATCHES = {
 "wells": {"name":"已修改"}, "well-configs":{"production_mode":"间歇"},
 "well-tools":{"tool_name":"已修改"}, "measurements":{"gas_temperature_c":12.5},
 "measure-events":{"notes":"已修改"}, "operation-events":{"reason":"已修改"},
 "fault-histories":{"notes":"已修改"}, "baselines":{"sample_count":25},
 "rules":{"name":"已修改"}, "analysis-runs":{"status":"已完成"},
 "anomalies":{"severity":"关注"}, "reviews":{"comment":"已修改"},
 "import-jobs":{"filename":"已修改.xlsx"}, "status-snapshots":{"screening_status":"工况待核实"},
}

@pytest.mark.parametrize("slug", [r[0] for r in RESOURCES])
def test_resource_full_crud(client, records, slug):
    create, _ = records
    row = create(slug)
    UUID(row["id"])
    path = "/api/v1/" + slug
    assert client.get(path + "/" + row["id"]).json()["id"] == row["id"]
    page = client.get(path, params={"limit":1}).json()
    assert page["total"] == 1 and len(page["items"]) == 1
    response = client.patch(path + "/" + row["id"], json=PATCHES[slug])
    assert response.status_code == 200, response.text
    for key, value in PATCHES[slug].items():
        assert response.json()[key] == value
    assert client.delete(path + "/" + row["id"]).status_code == 204
    assert client.get(path + "/" + row["id"]).status_code == 404

@pytest.mark.parametrize("slug", [r[0] for r in RESOURCES])
def test_resource_validation_and_not_found(client, slug):
    path = "/api/v1/" + slug
    response = client.post(path, json={"unexpected":"字段"})
    assert response.status_code == 422
    assert "请求参数无效" in response.json()["detail"]
    assert client.get(path + "/" + str(uuid4())).status_code == 404
    assert client.get(path, params={"limit":501}).status_code == 422

def test_well_id_stable_after_number_change(client, records):
    create, _ = records
    measurement = create("measurements")
    well = create("wells")
    response = client.patch("/api/v1/wells/" + well["id"], json={"well_number":"演示-新井号"})
    assert response.json()["id"] == well["id"]
    assert client.get("/api/v1/measurements/" + measurement["id"]).json()["well_id"] == well["id"]

def test_unique_well_number_and_transaction_recovery(client, records):
    create, _ = records
    create("wells")
    assert client.post("/api/v1/wells", json={"well_number":"演示-001", "area":"演示工区"}).status_code == 409
    assert client.post("/api/v1/wells", json={"well_number":"演示-002", "area":"演示工区"}).status_code == 201

def test_measurement_deduplication_constraint(client, records):
    create, payload = records
    create("measurements")
    assert client.post("/api/v1/measurements", json=payload("measurements")).status_code == 409
    assert client.get("/api/v1/measurements").json()["total"] == 1

def test_restrict_parent_delete(client, records):
    create, _ = records
    create("measure-events")
    assert client.delete("/api/v1/wells/" + create("wells")["id"]).status_code == 409

def test_foreign_key_rejects_orphan(client):
    response = client.post("/api/v1/measurements", json={"well_id":str(uuid4()), "measured_at":"2026-01-01T00:00:00Z"})
    assert response.status_code == 409

@pytest.mark.parametrize("slug", ["well-configs", "well-tools", "measure-events", "operation-events", "fault-histories"])
def test_effective_interval_validation(client, records, slug):
    create, payload = records
    data = payload(slug)
    data["effective_end"] = data["effective_start"]
    assert client.post("/api/v1/" + slug, json=data).status_code == 422
    row = create(slug)
    assert client.patch("/api/v1/" + slug + "/" + row["id"], json={"effective_end":"2025-01-01T00:00:00Z"}).status_code == 422
    assert client.patch("/api/v1/" + slug + "/" + row["id"], json={"effective_end":None}).status_code == 200

def test_requires_timezone_and_non_null_fields(client, records):
    create, payload = records
    data = payload("measurements")
    data["measured_at"] = "2026-01-01T00:00:00"
    assert client.post("/api/v1/measurements", json=data).status_code == 422
    well = create("wells")
    assert client.patch("/api/v1/wells/" + well["id"], json={"well_number":None}).status_code == 422

def test_normalizes_timezone_for_deduplication(client, records):
    create, payload = records
    create("measurements")
    data = payload("measurements")
    data["measured_at"] = "2026-01-01T08:00:00+08:00"
    assert client.post("/api/v1/measurements", json=data).status_code == 409

def test_evidence_and_event_association(client, records):
    create, _ = records
    anomaly = create("anomalies")
    event = create("measure-events")
    assert anomaly["well_id"] == event["well_id"]
    assert anomaly["evidence"]["unit"] == "m³/h"
    assert anomaly["rule_snapshot"]["version"] == "1.0"
    assert create("reviews")["anomaly_id"] == anomaly["id"]

def test_search_area_pagination(client, records):
    create, _ = records
    create("wells")
    assert client.get("/api/v1/wells", params={"search":"演示", "area":"演示工区"}).json()["total"] == 1
    assert client.get("/api/v1/wells", params={"search":"%"}).json()["total"] == 0
    assert client.get("/api/v1/wells", params={"area":"另一工区"}).json()["total"] == 0
    assert client.get("/api/v1/wells", params={"offset":1}).json()["items"] == []

def test_unknown_status_not_default_normal(client, records):
    create, _ = records
    assert create("status-snapshots")["screening_status"] == "数据待核实"
    assert create("status-snapshots")["production_state"] == "工况待核实"

def test_versioned_rules_and_unique_snapshot(client, records):
    create, payload = records
    create("rules")
    assert client.post("/api/v1/rules", json=payload("rules")).status_code == 409
    data = payload("rules"); data["version"] = "2.0"
    assert client.post("/api/v1/rules", json=data).status_code == 201
    create("status-snapshots")
    assert client.post("/api/v1/status-snapshots", json=payload("status-snapshots")).status_code == 409

def test_rejects_nonfinite_values(client, records):
    _, payload = records
    data = payload("measurements"); data["gas_temperature_c"] = "NaN"
    assert client.post("/api/v1/measurements", json=data).status_code == 422

def test_health_ready_and_openapi(client):
    assert client.get("/health").json()["stage"] == "任务3"
    assert client.get("/ready").json()["revision"] == "0002_analysis_results"
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "北田公司气井智能分析系统"
    for slug, _, _ in RESOURCES:
        assert "post" in schema["paths"]["/api/v1/" + slug]
