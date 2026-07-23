const express = require('express');
const { syncContact } = require('./src/services/contactService');

const app = express();
const PORT = process.env.PORT || 3000;
const CODE_VERSION = process.env.CODE_VERSION || 'good';

app.use(express.json());

// Structured logging helper
function log(level, message, extra = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    file: 'server.js',
    line: new Error().stack.split('\n')[2].match(/:(\d+):/)?.[1] || 'unknown',
    codeVersion: CODE_VERSION,
    ...extra
  };
  console.log(JSON.stringify(entry));
}

// Health check endpoint
app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'healthy', codeVersion: CODE_VERSION });
});

// Contact sync endpoint
app.post('/sync', async (req, res) => {
  const contact = req.body;
  log('info', 'Received contact sync request', { contact });

  try {
    const result = await syncContact(contact, CODE_VERSION);
    res.status(200).json(result);
  } catch (err) {
    log('error', 'Unhandled exception in /sync route', {
      error: err.message,
      stack: err.stack,
      scenarioType: 'ec2CodeFailure'
    });
    res.status(500).json({ error: 'Internal server error', message: err.message });
  }
});

app.listen(PORT, () => {
  log('info', `Contact Sync Service started on port ${PORT}`, { port: PORT });
});

module.exports = app;
