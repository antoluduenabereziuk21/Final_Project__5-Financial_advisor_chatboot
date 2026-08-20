# PR Checklist - Chat Persistence, History, and Feedback

## Scope included
- Backend chat persistence with PostgreSQL-compatible schema.
- Feedback endpoints integrated with persisted messages.
- Conversation history endpoints for restoring previous chats.
- Frontend data layer and Home chat integration for feedback/sources/history.

## Required DB migration
Run the migration SQL before deploying backend to Supabase/Postgres:
- `backend/sql/001_chat_persistence_schema.sql`

## Environment
Set backend runtime variable:
- `DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>?sslmode=require`

## API smoke tests
- `GET /health` returns `{"status":"ok"}`
- `POST /api/chat` returns `conversation_id`, `message_id`, `sources`
- `POST /api/chat/feedback` returns `201` and `feedback_id`
- `GET /api/chat/feedback?conversation_id=<id>` returns items and total
- `GET /api/chat/conversations` returns recent conversations
- `GET /api/chat/conversations/{conversation_id}` returns messages with sources

## Frontend smoke tests
- Open app and start conversation.
- Send multiple prompts and verify messages render without overlap.
- Confirm references are visible under assistant messages.
- Submit Helpful/Not helpful feedback.
- Reload page and verify previous conversation is restored.

## Local verification executed
- `backend`: `python -m pytest tests/test_chat_api.py -q`
- `frontend`: `npx tsc -b`

## Suggested PR description template
### What changed
- Added DB-backed chat persistence for conversations/messages/sources/feedback.
- Added conversation history endpoints.
- Added frontend chat API integration and persisted conversation restore.
- Improved source reference rendering and feedback flow in chat UI.

### Why
- Align chat behavior with persistent storage and support feedback analytics.
- Prepare deployment compatibility with Supabase/Postgres.

### Deployment notes
- Run `backend/sql/001_chat_persistence_schema.sql` before backend rollout.
- Ensure `DATABASE_URL` points to target Supabase/Postgres instance.
