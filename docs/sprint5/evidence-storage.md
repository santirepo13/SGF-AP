# Almacenamiento privado de evidencias

```dotenv
EVIDENCE_UPLOADS_ENABLED=true
EVIDENCE_STORAGE_ROOT=/srv/sgf-ap/evidence-private
EVIDENCE_MAX_REPORT_PHOTOS=3
EVIDENCE_MAX_FILE_BYTES=10000000
EVIDENCE_MAX_IMAGE_PIXELS=40000000
EVIDENCE_MULTIPART_ENVELOPE_MAX_BYTES=65536
EVIDENCE_RECEIVING_LEASE_SECONDS=300
EVIDENCE_RECEIVING_MAX_SECONDS=900
EVIDENCE_READY_TTL_SECONDS=86400
EVIDENCE_ORPHAN_SAFETY_SECONDS=900
```

```sh
install -d -m 0700 -o sgfap -g sgfap /srv/sgf-ap/evidence-private
install -d -m 0700 -o sgfap -g sgfap /srv/sgf-ap/evidence-private/.staging
```

```sql
-- Aplicar manualmente en PostgreSQL remoto, en este orden:
\i db/migrations/005_04_evidence_uploads.sql
\i db/migrations/005_05_citizen_contributions.sql
```

- El volumen no pertenece al repositorio, directorio temporal, StaticFiles ni Flet.
- Todas las réplicas comparten el mismo volumen persistente.
- El respaldo incluye PostgreSQL y el volumen en una ventana coordinada.
- El barrido elimina solo temporales expirados o blobs no referenciados después del margen configurado.
- Ningún barrido elimina una clave referenciada por `evidences`.