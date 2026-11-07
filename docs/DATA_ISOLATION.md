# Data isolation

Every project carries an owner ID. Repository/finding/task/scan access follows that project ownership on the backend. Jobs, usage and audit logs are owner-filtered. Unauthorized object IDs return 404. Credential serialization is excluded globally; sessions contain hashed opaque tokens, and OAuth tokens are encrypted under an ignored server-owned key.

Snapshots, workspaces and checkpoints use generated UUID directories inside a managed root. File previews, patches, mounts and cleanup resolve absolute boundaries and reject traversal, symlinks and secret directories. Model context caches include owner/task identity in their hash; they are not shared across owners. Local source never goes to a model provider when LOCAL_ONLY is enabled.

Project deletion refuses active jobs, deletes dependent DB rows and owned source/checkpoints, and retains audit history. Intelligence caches contain public advisory responses. Model caches may contain source-derived responses and currently persist until operator retention cleanup; automatic retention and cryptographic secure erasure are not implemented. Protect volumes, the credential key and backups with host access controls; Windows ACL inheritance is a deployment responsibility.
