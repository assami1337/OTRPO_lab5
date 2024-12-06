# test_app.py

import requests

BASE_URL = "http://127.0.0.1:8000"
TOKEN = "12345"  # должен совпадать с LAB5_TOKEN из .env

def test_get_nodes():
    resp = requests.get(f"{BASE_URL}/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data

def test_get_nonexistent_node():
    resp = requests.get(f"{BASE_URL}/nodes/9999999")  # заведомо несуществующий
    assert resp.status_code == 404

def test_protected_endpoints_no_auth():
    resp = requests.post(f"{BASE_URL}/segments", json={"nodes":[],"relationships":[]})
    assert resp.status_code == 401

def test_protected_endpoints_with_auth():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    node_data = {
        "nodes": [
            {"label":"User", "id":12345, "attributes":{"name":"Test User","sex":1}}
        ],
        "relationships":[]
    }
    resp = requests.post(f"{BASE_URL}/segments", json=node_data, headers=headers)
    assert resp.status_code == 200

    resp_node = requests.get(f"{BASE_URL}/nodes/12345")
    assert resp_node.status_code == 200
    data = resp_node.json()
    assert data["node"]["attributes"]["name"] == "Test User"

    delete_data = {"node_ids":[12345]}
    resp_del = requests.delete(f"{BASE_URL}/segments", json=delete_data, headers=headers)
    assert resp_del.status_code == 200

    resp_node_after = requests.get(f"{BASE_URL}/nodes/12345")
    assert resp_node_after.status_code == 404
