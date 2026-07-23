const { Pool } = require('pg');

// Database connection pool
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
    message,
    file: 'contactService.js',
    line: new Error().stack.split('\n')[2].match(/:(\d+):/)?.[1] || 'unknown',
    ...extra
  };
  console.log(JSON.stringify(entry));
}

/**
 * Sync a contact to the RDS PostgreSQL database.
 * Good version: wraps INSERT in try/catch with structured error logging.
 * Bad version: no try/catch — null email throws unhandled exception.
 */
async function syncContact(contact, codeVersion) {
  log('info', 'Processing contact sync', { codeVersion, contactId: contact?.id });

  if (codeVersion === 'bad') {
    return syncContactBad(contact);
  }
  return syncContactGood(contact);
}

/**
 * Good version: RDS INSERT wrapped in try/catch with structured error logging.
 * Catches database constraint violations and returns a structured error response.
 */
async function syncContactGood(contact) {
  try {
    const result = await pool.query(
      'INSERT INTO contacts (id, name, email, phone, company) VALUES ($1, $2, $3, $4, $5) RETURNING *',
      [contact.id, contact.name, contact.email, contact.phone, contact.company]
    );
    log('info', 'Contact synced successfully', { contactId: contact?.id });
    return { success: true, contact: result.rows[0] };
  } catch (err) {
    log('error', 'Failed to sync contact to database', {
      error: err.message,
      code: err.code,
      contactId: contact?.id,
      scenarioType: 'ec2CodeFailure'
    });
    return { success: false, error: err.message, code: err.code };
  }
}

/**
 * Bad version: NO try/catch around RDS INSERT.
 * When contact.email is null, the NOT NULL constraint violation
 * throws an unhandled exception at this traceable line.
 */
async function syncContactBad(contact) {
  log('info', 'Processing contact sync (bad version)', { contactId: contact?.id });

  const result = await pool.query(
    'INSERT INTO contacts (id, name, email, phone, company) VALUES ($1, $2, $3, $4, $5) RETURNING *',
    [contact.id, contact.name, contact.email, contact.phone, contact.company]
  );
  log('info', 'Contact synced successfully (bad version)', { contactId: contact?.id });
  return { success: true, contact: result.rows[0] };
}

module.exports = { syncContact, syncContactGood, syncContactBad, pool, log };
