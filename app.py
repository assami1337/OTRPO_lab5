import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, Header
from pydantic import BaseModel
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
AUTH_TOKEN = os.getenv("LAB5_TOKEN", "secret")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

app = FastAPI(
    title="Lab 5 - REST API for Neo4j Graph",
    description="REST API для доступа к графу пользователей и групп, созданному в лабах 3-4",
    version="1.0.0"
)


# ---------------------------
# Модели данных
# ---------------------------

class NodeCreate(BaseModel):
    label: str
    id: int
    attributes: Optional[Dict[str, Any]] = None


class RelationshipCreate(BaseModel):
    type: str
    from_id: int
    to_id: int


class SegmentCreate(BaseModel):
    nodes: Optional[List[NodeCreate]] = []
    relationships: Optional[List[RelationshipCreate]] = []


class SegmentDelete(BaseModel):
    node_ids: Optional[List[int]] = []


# ---------------------------
# Авторизация
# ---------------------------

def check_authorization(authorization: str = Header(None)):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split("Bearer ")[1]
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return True


# ---------------------------
# Функции для работы с Neo4j
# ---------------------------

def get_all_nodes():
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN n, labels(n) as lbls")
        nodes = []
        for rec in result:
            n = rec["n"]
            lbls = rec["lbls"]
            label = lbls[0] if lbls else "Unknown"
            nodes.append({"id": n["id"], "label": label})
        return nodes


def get_node_and_relationships(node_id: int):
    with driver.session() as session:
        node_res = session.run("MATCH (n) WHERE n.id=$id RETURN n, labels(n) as lbls", id=node_id)
        node_record = node_res.single()
        if not node_record:
            return None
        main_node = node_record["n"]
        main_label = node_record["lbls"][0] if node_record["lbls"] else "Unknown"

        rel_res = session.run("""
            MATCH (n {id:$id})-[r]-(m)
            RETURN TYPE(r) as rel_type, r, m, labels(m) as lbls
        """, id=node_id)
        relationships = []
        connected_nodes = []
        for rec in rel_res:
            rel_type = rec["rel_type"]
            rel = rec["r"]
            m = rec["m"]
            lbls = rec["lbls"]
            connected_label = lbls[0] if lbls else "Unknown"
            relationships.append({
                "type": rel_type,
                "start_id": rel.start_node["id"],
                "end_id": rel.end_node["id"],
            })
            connected_nodes.append({
                "id": m["id"],
                "label": connected_label,
                "attributes": {k: v for k, v in m.items() if k != 'id'}
            })

        node_data = {
            "id": main_node["id"],
            "label": main_label,
            "attributes": {k: v for k, v in main_node.items() if k != 'id'}
        }

        return {
            "node": node_data,
            "relationships": relationships,
            "connected_nodes": connected_nodes
        }


def create_segment(segment: SegmentCreate):
    with driver.session() as session:
        for node in segment.nodes:
            label = node.label.capitalize()
            attrs = node.attributes or {}
            set_str = ", ".join([f"n.{k} = $param_{k}" for k in attrs.keys()])
            if set_str:
                set_str = ", " + set_str
            params = {"id": node.id}
            for k, v in attrs.items():
                params[f"param_{k}"] = v
            query = f"""
                MERGE (n:{label} {{id: $id}})
                SET n.id = $id{set_str}
            """
            session.run(query, **params)

        for rel in segment.relationships:
            rel_type = rel.type
            query = f"""
                MATCH (a {{id:$from_id}}), (b {{id:$to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
            """
            session.run(query, from_id=rel.from_id, to_id=rel.to_id)


def delete_segment(segment: SegmentDelete):
    with driver.session() as session:
        if segment.node_ids:
            session.run("MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=segment.node_ids)


# ---------------------------
# Эндпоинты
# ---------------------------

@app.get("/nodes")
def get_nodes():
    """
    Получить все узлы с атрибутами id, label
    """
    nodes = get_all_nodes()
    return {"nodes": nodes}


@app.get("/nodes/{node_id}")
def get_node(node_id: int):
    """
    Получить узел и все его связи со всеми атрибутами
    """
    data = get_node_and_relationships(node_id)
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return data


@app.post("/segments")
def post_segment(segment: SegmentCreate, authorized: bool = Depends(check_authorization)):
    """
    Добавить узлы и связи (или сегмент графа)
    Требует авторизации.
    """
    create_segment(segment)
    return {"status": "success"}


@app.delete("/segments")
def delete_nodes(segment: SegmentDelete, authorized: bool = Depends(check_authorization)):
    """
    Удалить узлы (и их связи)
    Требует авторизации.
    """
    delete_segment(segment)
    return {"status": "deleted"}

