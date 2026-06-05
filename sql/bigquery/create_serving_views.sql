-- Ajuste `seu_projeto` e `seu_dataset` antes de executar

CREATE OR REPLACE VIEW `seu_projeto.seu_dataset.vw_daily_transactions` AS
SELECT
  DATE(transaction_ts) AS transaction_date,
  transaction_type,
  category,
  status,
  COUNT(*) AS transaction_count,
  SUM(amount) AS total_amount,
  SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS fraud_count
FROM `seu_projeto.seu_dataset.transactions`
GROUP BY 1,2,3,4;
