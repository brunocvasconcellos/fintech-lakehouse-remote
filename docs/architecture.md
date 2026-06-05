# Arquitetura – Fintech Lakehouse Remoto

## Visão geral

```text
PostgreSQL (remoto, OLTP)
   -> Airflow (Docker, LocalExecutor)
        -> Python ETL
             -> Parquet no GCS (data lake)
                  -> BigQuery (camada analítica/serving)
                       -> Looker Studio / SQL
```

- PostgreSQL representa o sistema de origem (aplicação fintech, core bancário, etc.).
- Airflow orquestra jobs batch diários.
- Os dados são serializados em Parquet diretamente em um bucket GCS.
- BigQuery referencia esses arquivos Parquet e materializa tabelas analíticas.
- Looker Studio se conecta ao BigQuery para visualização.
