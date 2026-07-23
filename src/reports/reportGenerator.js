const express = require('express');
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3001;

const pool = new Pool({
  host: process.env.RDS_ENDPOINT,
  database: process.env.DB_NAME || 'crmdb',
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  port: 5432,
  max: 5,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000
});

// Structured logging helper
function log(level, message, extra = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    service: 'crm-report-generator',
    message,
    ...extra
  };
  console.log(JSON.stringify(entry));
}

app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'healthy', service: 'crm-report-generator' });
});

/**
 * Generate pipeline report using a single efficient JOIN query.
 * Aggregates opportunity data by account in one round-trip to the database.
 */
app.get('/generate', async (_req, res) => {
  const start = Date.now();
  log('info', 'Starting report generation');

  try {
    const result = await pool.query(`
      SELECT
        a.id AS account_id,
        a.name AS account_name,
        a.industry,
        COUNT(o.id) AS total_opportunities,
        COALESCE(SUM(o.amount), 0) AS total_pipeline,
        COUNT(CASE WHEN o.stage = 'Closed Won' THEN 1 END) AS closed_won,
        CASE
          WHEN COUNT(o.id) > 0
          THEN ROUND((COUNT(CASE WHEN o.stage = 'Closed Won' THEN 1 END)::numeric / COUNT(o.id)) * 100)
          ELSE 0
        END AS health_score
      FROM accounts a
      LEFT JOIN opportunities o ON o.account_id = a.id
      GROUP BY a.id, a.name, a.industry
      ORDER BY total_pipeline DESC
    `);

    const report = result.rows.map(row => ({
      accountId: row.account_id,
      accountName: row.account_name,
      industry: row.industry,
      totalOpportunities: parseInt(row.total_opportunities, 10),
      totalPipeline: parseFloat(row.total_pipeline),
      closedWon: parseInt(row.closed_won, 10),
      healthScore: parseInt(row.health_score, 10)
    }));

    const elapsed = Date.now() - start;
    log('info', 'Report generation complete', { elapsed, accountCount: report.length });

    res.status(200).json({
      generatedAt: new Date().toISOString(),
      elapsedMs: elapsed,
      accountCount: report.length,
      accounts: report
    });
  } catch (err) {
    const elapsed = Date.now() - start;
    log('error', 'Report generation failed', { error: err.message, elapsed });
    res.status(500).json({ error: 'Report generation failed', message: err.message });
  }
});

app.listen(PORT, () => {
  log('info', `Report generator started on port ${PORT}`, { port: PORT });
});

module.exports = app;
