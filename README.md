# Fintech Lakehouse – Remote PostgreSQL, GCS, BigQuery

Projeto completo de portfólio de engenharia de dados com:

- PostgreSQL remoto como origem transacional.
- Apache Airflow (Docker) como orquestrador.
- Extração em Python gravando arquivos Parquet diretamente em um bucket GCS.
- BigQuery como camada de serving.
- Looker Studio (ou SQL no BigQuery) como camada de visualização.

Qualquer pessoa pode rodar **Airflow + pipeline** apenas com Docker, desde que tenha:

- um PostgreSQL acessível via internet/rede privada;
- um projeto GCP com GCS + BigQuery + service account.

## Arquitetura

```text
PostgreSQL (remoto, origem)
   -> Airflow (Docker)
        -> Python ETL
             -> Parquet no GCS (data lake)
                  -> BigQuery (tabelas fact/dim)
                       -> Looker Studio / SQL
```

## Fluxo de alto nível

1. Airflow conecta em um PostgreSQL remoto (tabelas `customers`, `accounts`, `merchants`, `transactions`).
2. A DAG executa um script Python que lê essas tabelas e grava arquivos Parquet em um bucket GCS.
3. Em seguida, os mesmos arquivos Parquet são carregados em tabelas no BigQuery (uma por entidade).
4. Views analíticas podem ser criadas no BigQuery para exposição a Looker Studio.

O projeto **não sobe PostgreSQL em Docker**: ele assume que o banco de origem é um serviço remoto gerenciado (RDS, Cloud SQL, Aurora, on-prem etc.).

---

## Estrutura do repositório

```text
fintech-lakehouse-remote/
├── airflow/
│   ├── dags/
│   │   └── fintech_lakehouse_daily.py
│   ├── logs/
│   │   └── .gitkeep
│   └── plugins/
│       └── .gitkeep
├── common/
│   ├── bigquery_utils.py
│   └── gcs_utils.py
├── docs/
│   ├── architecture.md
│   └── runbook.md
├── ingestion/
│   └── postgres_to_gcs_parquet.py
├── scripts/
│   └── seed_remote_postgres.py
├── sql/
│   ├── bigquery/
│   │   └── create_serving_views.sql
│   └── postgres/
│       └── source_schema.sql
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Pré-requisitos

- Docker e Docker Compose.
- Projeto Google Cloud com:
  - BigQuery habilitado;
  - Cloud Storage habilitado;
  - uma service account com permissão em GCS e BigQuery;
  - arquivo JSON da service account.
- Um banco PostgreSQL remoto acessível via rede a partir da sua máquina/host Docker.

---

## Configuração

1. Copie o arquivo de variáveis de ambiente de exemplo:

```bash
cp .env.example .env
```

2. Preencha `.env` com:

- host, porta, database, usuário e senha do PostgreSQL remoto;
- id do projeto GCP;
- nome do bucket GCS;
- nome do dataset BigQuery;
- caminho do arquivo de credenciais da service account **dentro do container** (`/opt/airflow/creds/gcp-service-account.json`).

3. Coloque o JSON da service account na pasta `./creds` (que será montada em `/opt/airflow/creds` dentro dos containers).

---

## Subida rápida

```bash
cp .env.example .env
# edite .env com seus dados de PostgreSQL e GCP
mkdir -p creds
# coloque gcp-service-account.json em ./creds

# subir Airflow (webserver + scheduler)
docker compose up -d --build airflow-init
docker compose up -d airflow-webserver airflow-scheduler
```

Airflow ficará disponível em: <http://localhost:8080>

Usuário padrão:

- usuário: `admin`
- senha:  `admin`

---

## Pipeline diário

A DAG `fintech_lakehouse_daily` faz:

1. `extract_postgres_to_gcs_parquet`
   - lê tabelas do PostgreSQL remoto;
   - escreve arquivos Parquet temporários em `/opt/airflow/data/parquet`;
   - sobe esses arquivos para o bucket GCS `gs://$GCS_BUCKET/$GCS_PREFIX/`.

2. `load_parquet_to_bigquery`
   - cria/atualiza tabelas `customers`, `accounts`, `merchants`, `transactions` no BigQuery
     a partir dos arquivos Parquet no GCS.

3. (opcional) `create_serving_views`
   - cria views analíticas (por exemplo `vw_daily_transactions`) usadas no Looker Studio.

---

## Banco de origem – schema e seed

O repositório inclui:

- `sql/postgres/source_schema.sql`: DDL com o schema recomendado para o PostgreSQL remoto.
- `scripts/seed_remote_postgres.py`: script Python que gera dados sintéticos para esse schema
  usando Faker, conectando no PostgreSQL remoto via variáveis `SOURCE_POSTGRES_*`.

Você pode rodar esse seed **de dentro do container do Airflow** (conveniente para demonstração):

```bash
docker compose exec airflow-webserver \
  python /opt/airflow/scripts/seed_remote_postgres.py
```

Ou rodá-lo localmente, criando um virtualenv e instalando `requirements.txt`.

---

## BigQuery e Looker Studio

1. Após a execução do pipeline, haverá tabelas no BigQuery, por exemplo:
   - `fintech_lakehouse.customers`
   - `fintech_lakehouse.accounts`
   - `fintech_lakehouse.merchants`
   - `fintech_lakehouse.transactions`

2. Opcionalmente, rode o script `sql/bigquery/create_serving_views.sql` (ajustando `project` e `dataset`)
   para criar views analíticas.

3. No Looker Studio, conecte diretamente ao BigQuery usando o conector nativo e construa relatórios
   em cima das tabelas/views criadas.

---

## Publicação no GitHub

- Não commitar `.env` nem `./creds`.
- Deixe `.env.example` preenchido com valores de exemplo seguros.
- Documente no README os passos de configuração (já incluído neste arquivo).

Esse repositório foi pensado para ser um **case completo de engenharia de dados**, mostrando:

- ingestão batch de um sistema financeiro (fintech) em PostgreSQL;
- uso de Parquet em data lake (GCS);
- modelagem analítica no BigQuery;
- consumo via ferramenta de BI.


---

## Carga incremental e watermark

Este projeto implementa uma carga incremental de transações a cada 30 minutos.

- A DAG `fintech_lakehouse_30min` roda a cada 30 minutos e executa duas etapas: extração de PostgreSQL remoto para Parquet no GCS e carga em append no BigQuery.
- Para as tabelas de dimensão (`customers`, `accounts`, `merchants`), a carga é full simples por execução.
- Para a tabela fato `transactions`, a extração é incremental com base na coluna `transaction_ts`.
- O pipeline consulta uma tabela de watermark no BigQuery (por padrão `${BIGQUERY_DATASET}.watermarks`) para descobrir o último `transaction_ts` carregado.
- Se não houver watermark, a primeira carga considera todos os registros até o momento atual.
- Em seguida, cada execução lê apenas as transações com `transaction_ts` maior que o último watermark e menor ou igual ao horário da execução.
- Depois de carregar o delta de Parquet para o BigQuery com `WRITE_APPEND`, o pipeline atualiza a tabela de watermark usando o `MAX(transaction_ts)` da tabela de destino.

Esse padrão de high watermark é um desenho comum em pipelines de streaming batch / near real-time em data warehouses como o BigQuery, permitindo dashboards quase em tempo real sem recarga completa das tabelas.
