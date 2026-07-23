/**
 * CRM Event Processor Lambda - handles async event processing for the CRM pipeline.
 *
 * Processes events triggered by opportunity updates, account changes, and
 * pipeline stage transitions. Publishes processed results to downstream
 * consumers for reporting and notification delivery.
 */

export const handler = async (event: unknown) => {
    console.log('CRM event processor invoked', JSON.stringify(event));

    const records = Array.isArray(event) ? event : [event];
    for (const record of records) {
        const payload = typeof record === 'string' ? JSON.parse(record) : record;
        console.log(`Processing event type: ${payload.type || 'unknown'}`);
    }

    return { statusCode: 200, body: JSON.stringify({ processed: records.length }) };
};
