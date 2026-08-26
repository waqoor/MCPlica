# Milvus

The starter Compose topology pins `milvusdb/milvus:v3.0.0` with etcd and MinIO according to the Milvus 3.0.0 standalone Docker Compose model. Milvus is builder-side semantic infrastructure only and must never be required by generated MCP runtime containers.

Before production deployment, compare this pinned topology against the exact official compose file for the chosen Milvus patch release and update all dependency image pins together.
