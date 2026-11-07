"""The single egress path off this device (PV-04 to PV-08). Not built yet (task A4).

This is the ONLY module allowed to import sentinel_contract.client or any HTTP library (tests enforce it).
It writes each payload to the outbox before sending, sends through SentinelClient, records egress_log from
SendResult, keeps SendRetryable payloads queued, and never retries SendRejected.
"""
