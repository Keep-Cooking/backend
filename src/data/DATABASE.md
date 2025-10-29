# Database Schema

## Tables

### `auth` (users)

| Column     | Type (SQLAlchemy) | Constraints / Notes                                  |
| ---------- | ----------------- | ---------------------------------------------------- |
| `id`       | `Integer`         | **Primary Key**, `autoincrement=True`                |
| `username` | `String(64)`      | **UNIQUE**, **NOT NULL**, **INDEXED** |
| `email`    | `String(255)`     | **NOT NULL** (non-unique)                            |
| `password` | `String(512)`     | **NOT NULL** — stores full Argon2id encoded hash |
| `images`   | `Text`            | Defaults to `"[]"` (JSON string)                     |
| `points`   | `Integer`         | Defaults to `0`                                      |
| `level`    | `Integer`         | Defaults to `1`                                      |

## Model behavior

* **Creation (`User.create`)**
  Hashes the plaintext password with Argon2id and inserts the row.

* **Lookup (`User.by_username`)**
  Uses the indexed, unique `username` for fast retrieval.

* **Verification (`verify_and_maybe_rehash`)**

  * Verifies password with Argon2id.
  * If parameters are outdated, rehashes and commits the updated hash.

**Argon2id parameters (defaults here):**

* `time_cost=3`, `memory_cost=64_000 (KiB)`, `parallelism=2`.

## Engine / SQLite settings

On each connection:

* `PRAGMA journal_mode=WAL;`
* `PRAGMA synchronous=NORMAL;`

These improve concurrency and write performance for SQLite.

## Notes

* `email` is required but not unique.
* `password` stores the entire Argon2id string (includes algorithm, salt, params).
* `images` is a JSON-encoded array stored as text.
