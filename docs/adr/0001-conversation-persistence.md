# ADR 0001: Persistencia de conversaciones y feedback en Postgres

## Estado

Aceptado.

## Contexto

`ConversationService` y parte de `ChatService` guardaban historial de chat,
feedback por mensaje y un índice de fuentes citadas en diccionarios de
proceso (`dict` en memoria). Esto viola el principio de servicios stateless:
los datos se pierden en cada reinicio del backend y no se comparten entre
réplicas si el servicio escala horizontalmente.

El schema para persistir esto (`conversations`, `chat_messages`) ya existía
en `rag/vector_store/init_db.sql`, pero nunca se conectó.

Hubo un intento previo (PR #16, reverteado en PR #18 / commit `ad04386`) que
tenía dos problemas de diseño:

1. Abría una **segunda conexión/pool** a Postgres (`VectorDbClient` adicional)
   en paralelo a la ya usada para pgvector, contra la misma base de datos.
2. El `conversation_id` se generaba en el **frontend** y el backend
   normalizaba cualquier string no-UUID hasheándolo (`uuid5`) a un UUID
   determinista — un id de cliente arbitrario podía remapearse a una
   conversación ajena.

## Decisión

- **Reutilizar el pool existente.** `ConversationRepository` recibe el mismo
  `VectorDbClient` que ya conecta `backend/app/main.py` para pgvector
  (`db_client`), en vez de abrir uno propio.
- **El `conversation_id` nunca se genera ni se interpreta del lado del
  cliente.** Si el valor recibido no es un UUID válido, se trata como
  ausente y se genera uno nuevo (`gen_random_uuid()` en Postgres) — sin
  hashing determinista de strings arbitrarios.
- **Alcance limitado al camino de Postgres directo.** Cuando el retrieval
  usa Supabase (`rag/vector_store/supabase_repository.py`, cliente HTTPS/RPC
  de solo lectura, sin endpoints de escritura) o no hay backend conectado,
  `ConversationService`/`ChatService` mantienen el fallback en memoria
  actual — mismo patrón de degradación que ya usa el resto de la app
  (`RAGService.generate_answer` sin adapter). Persistir también en modo
  Supabase queda fuera de alcance: no hay precedente de escritura vía ese
  cliente en este código.
- **El detalle de una fuente (`GET /api/sources/{chunk_id}`) no usa un caché
  en memoria.** `chunk_id` en `sources[]` es `rag_chunks.id`
  (`rag/retrieval/retriever.py`), y `VectorRepository.get_by_id` ya existe.
  `ChatService.get_source_detail` consulta ese dato real cuando el repo
  vectorial lo soporta, en vez de mantener un índice de proceso — dato
  consistente entre reinicios y réplicas. (Efecto colateral: esto también
  corrige un bug latente donde el índice en memoria nunca se poblaba para
  tráfico real, porque solo indexaba `chunk_id` de tipo `str`, y el valor
  real es `int`).
- **Nueva tabla `message_feedback`** (no existía) para persistir el feedback
  por mensaje, siguiendo el mismo patrón idempotente de
  `rag/vector_store/init_db.sql`.

## Consecuencias

- El historial de conversación y el feedback sobreviven a un reinicio del
  backend cuando Postgres está conectado directamente.
- No se agrega una segunda conexión ni un segundo esquema de ids.
- En modo Supabase, el comportamiento no cambia (sigue en memoria) — es una
  limitación conocida y documentada, no una regresión.
- El frontend no requiere cambios: ya reenvía únicamente el `conversation_id`
  emitido por el servidor (`frontend/src/presentation/hooks/useChat.ts`).
