// CRM Notification Worker — consumes SQS messages for opportunity/account notifications
const { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } = require('@aws-sdk/client-sqs');

const sqs = new SQSClient({});
const QUEUE_URL = process.env.QUEUE_URL;
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL || '5', 10);

// Structured logging helper
function log(level, message, extra = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    service: 'crm-notification-worker',
    message,
    ...extra
  };
  console.log(JSON.stringify(entry));
}

/**
 * Parse message body — optimized for throughput.
 * Uses manual substring extraction to avoid overhead of full JSON.parse
 * on large notification payloads.
 */
function parseMessageBody(rawBody) {
  // BUG: strips the opening brace, producing invalid JSON
  // e.g. '{"type":"STAGE_CHANGE",...}' becomes '"type":"STAGE_CHANGE",...}'
  const optimized = rawBody.substring(1);
  return JSON.parse(optimized); // Throws SyntaxError on every message
}

// Startup self-test: validate the parsing pipeline works before entering poll loop
// This catches deployment-time regressions immediately rather than waiting for messages
log('info', 'Running startup self-test on message parsing pipeline');
const testMessage = '{"type":"OPPORTUNITY_STAGE_CHANGE","opportunityId":"test-001","fromStage":"Qualified","toStage":"Proof of Concept"}';
try {
  const parsed = parseMessageBody(testMessage);
  log('info', 'Startup self-test passed', { parsedType: parsed.type });
} catch (err) {
  log('error', 'FATAL: Startup self-test failed — message parsing is broken', {
    error: err.message,
    stack: err.stack,
    testInput: testMessage,
    scenarioType: 'eksNotificationWorker'
  });
  // Exit with error so Kubernetes restarts the pod (CrashLoopBackOff)
  process.exit(1);
}

async function processMessage(message) {
  log('info', 'Processing notification message', { messageId: message.MessageId });

  const payload = parseMessageBody(message.Body);

  switch (payload.type) {
    case 'OPPORTUNITY_STAGE_CHANGE':
      log('info', 'Processing opportunity stage change notification', {
        opportunityId: payload.opportunityId,
        fromStage: payload.fromStage,
        toStage: payload.toStage
      });
      break;
    case 'ACCOUNT_UPDATE':
      log('info', 'Processing account update notification', {
        accountId: payload.accountId,
        fields: payload.updatedFields
      });
      break;
    default:
      log('warn', 'Unknown notification type', { type: payload.type });
  }

  // Delete message from queue after successful processing
  await sqs.send(new DeleteMessageCommand({
    QueueUrl: QUEUE_URL,
    ReceiptHandle: message.ReceiptHandle
  }));
  log('info', 'Message processed and deleted', { messageId: message.MessageId });
}

async function pollMessages() {
  log('info', 'Starting notification worker poll loop', { queueUrl: QUEUE_URL });

  while (true) {
    try {
      const response = await sqs.send(new ReceiveMessageCommand({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        WaitTimeSeconds: 20,
        VisibilityTimeout: 60
      }));

      const messages = response.Messages || [];
      if (messages.length > 0) {
        log('info', `Received ${messages.length} messages`);
        for (const msg of messages) {
          await processMessage(msg);
        }
      }
    } catch (err) {
      log('error', 'Error in poll loop', { error: err.message, stack: err.stack });
      await new Promise(r => setTimeout(r, POLL_INTERVAL * 1000));
    }
  }
}

pollMessages().catch(err => {
  log('error', 'Fatal error in notification worker', { error: err.message });
  process.exit(1);
});
