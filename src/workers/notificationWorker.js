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

async function processMessage(message) {
  log('info', 'Processing notification message', { messageId: message.MessageId });

  let payload;
  try {
    payload = JSON.parse(message.Body);
  } catch (err) {
    log('error', 'Failed to parse message body', {
      messageId: message.MessageId,
      error: err.message,
      bodyPreview: message.Body?.substring(0, 100)
    });
    return;
  }

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
