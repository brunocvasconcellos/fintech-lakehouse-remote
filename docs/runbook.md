# Runbook – Execução do Projeto

## 1. Preparar variáveis e credenciais

1. Copie o `.env.example` para `.env` e preencha:
   - `SOURCE_POSTGRES_*` com os dados do PostgreSQL remoto.
   - `GCP_PROJECT_ID`, `GCS_BUCKET`, `BIGQUERY_DATASET`.
   - deixe `GOOGLE_APPLICATION_CREDENTIALS` como `/opt/airflow/creds/gcp-service-account.json`.

2. Crie a pasta de credenciais e coloque o JSON da service account:

```bash
mkdir -p creds
cp /caminho/local/da/service-account.json ./creds/gcp-service-account.json
```

## 2. Subir Airflow

```bash
docker compose up -d --build airflow-init
docker compose up -d airflow-webserver airflow-scheduler
```

Acesse http://localhost:8080 com `admin` / `admin`.

## 3. Criar schema e gerar dados no PostgreSQL remoto

No Airflow webserver:

```bash
docker compose exec airflow-webserver   python /opt/airflow/scripts/seed_remote_postgres.py
```

Isso irá:

- criar o schema (`customers`, `accounts`, `merchants`, `transactions`);
- popular dados sintéticos conforme parâmetros em `.env`.

## 4. Executar a DAG

No Airflow UI, ative e rode manualmente a DAG `fintech_lakehouse_daily`.

Ela irá:

1. extrair do PostgreSQL remoto para Parquet no GCS;
2. carregar as tabelas no BigQuery.

## 5. Criar views analíticas (opcional)

No BigQuery, ajuste `seu_projeto` e `seu_dataset` em `sql/bigquery/create_serving_views.sql` e execute o script.

## 6. Conectar Looker Studio

No Looker Studio:

- crie um novo relatório;
- adicione uma fonte de dados do tipo BigQuery;
- selecione o projeto/dataset/tabelas ou views criadas.
