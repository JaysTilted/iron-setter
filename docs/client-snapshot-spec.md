# Iron Setter — Client Snapshot Specification

## Overview

Every new iron-setter client needs GHL assets (custom fields, tags, pipeline) + webhook workflows.
The portal's "Go Live" button provisions fields/tags/pipeline via API.
Workflows must be installed via GHL Snapshot (no API for workflow creation).

## What the portal provisions automatically (API)

### Custom Fields (20)
System fields the AI engine reads/writes on contacts:
- smartfollowup_timer, smartfollowup_reason
- qualification_status, qualification_notes
- ai_processing, chathistory, last_ai_channel, last_activity_datetime
- agent_type_new, channel, lead_source, form_service_interest
- next_ai_follow_up, ai_bot
- response, response2, response3, response4, response5
- response1_media_url

### Tags (9)
- stop-bot, AI Test Mode, human_handover
- DNC, DNC - No Reply, DNC - Stop
- Booked, Qualified, Closed Won

### Pipeline
- Sales Pipeline: Engaged → Booked → Closed Won

## What the snapshot provides (manual install)

### Core Webhook Workflows (5 required)

These fire webhooks to the iron-setter backend. Without them, the AI has no triggers.

| # | Workflow Name | GHL Trigger | Webhook Endpoint | Purpose |
|---|---|---|---|---|
| 1 | Receive & Process DMs | Customer Replied (SMS) | `/webhook/reply` | Routes inbound messages to AI reply pipeline |
| 2 | Log Booking + Reminders | Appointment Status | `/webhook/log-booking` | Logs bookings, schedules reminders |
| 3 | Call Event Handler | Call Status | `/webhook/call-event` | Missed call textback + answered call bot pause |
| 4 | Human Activity Sync | Contact Tag (stop bot added by staff) OR Custom webhook from manual message | `/webhook/human-activity` | Pauses bot when staff manually messages |
| 5 | Bot On/Off Sync | Contact Changed (AI Bot field) | `/webhook/reply` with ai_bot field check | Syncs the AI Bot dropdown toggle |

### Optional Workflows (depends on client needs)

| Workflow | GHL Trigger | Webhook Endpoint | Purpose |
|---|---|---|---|
| Form Submission → Outreach | Form Submitted | `/webhook/resolve-outreach` | Resolves outreach template, schedules drip |
| DNC Auto-Actions | Contact Tag (DNC tags) | N/A (GHL-native) | Removes contact from all workflows on DNC tag |
| Booking Confirmation + Reminders | Customer Booked Appointment | N/A (GHL-native) | SMS/email confirmation + reminder drip |
| No-Show Handler | Appointment Status = No Show | N/A (GHL-native) | Rebooking SMS drip |

## Webhook URL pattern

All webhook URLs follow: `https://{backend_url}/webhook/reply`

The backend resolves the entity from the `location.id` field in the standard GHL webhook payload.
No entity ID in the URL path is needed (though `/webhook/{entity_ref}/reply` also works).

Backend URL for Iron Automations: `https://rg-backend.23.88.127.9.sslip.io`

## Snapshot creation checklist

1. In GHL Iron Automations sub-account, create a Snapshot containing:
   - The 5 core workflows listed above
   - Optionally the 4 additional workflows
   - Custom fields (or let the portal provision them — snapshot may duplicate)
   - Tags (same — portal provisions, snapshot may duplicate)
   - Sales Pipeline (same)
2. Export snapshot from Settings → Company → Snapshots → Share Link
3. New client installs snapshot into their sub-account
4. Client runs the portal wizard which:
   - Provisions any missing fields/tags/pipeline (idempotent — checks existence first)
   - Creates the entity + system_config in Supabase
   - Links the OAuth install to the entity
5. Client updates the webhook URLs in the 5 core workflows to point at THEIR backend URL
   (or if all clients share the same backend, URLs are already correct)

## Alternative: Workflow Templates (future)

GHL's Workflow AI Builder or manual workflow duplication could replace the snapshot.
The portal's "Go Live" could eventually create workflows via the private API
(using the SDK at `/home/jay/automation-platform/tools/ghl_private_sdk/`),
but this is fragile and the private API is unstable.

For now, snapshot is the reliable path.
