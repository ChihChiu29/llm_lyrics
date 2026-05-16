# Communication Manager API

Server runs on `localhost:8080`.

## Endpoints

### 1. Add new interaction
Adds a new interaction to the end of the queue.

- **URL:** `/api/interaction`
- **Method:** `POST`
- **Body:**
  ```json
  {
    "input_string": "The text to be sent to the LLM."
  }
  ```
- **Response:**
  ```json
  {
    "id": "unique-uuid",
    "status": "PENDING"
  }
  ```

### 2. Peek next interaction
Returns the next interaction in the queue (the oldest one with status PENDING).

- **URL:** `/api/interaction/next`
- **Method:** `GET`
- **Response:**
  ```json
  {
    "id": "unique-uuid",
    "input_string": "The text to be sent to the LLM.",
    "output_string": null,
    "status": "PENDING"
  }
  ```
  Returns `404` or `null` if no pending interactions.

### 3. Update interaction
Change response and status of the next interaction in the queue. Only the next one in the queue is modifiable. If the status is updated to `COMPLETED` or `FAILED`, it will be automatically removed from the queue.

- **URL:** `/api/interaction/next`
- **Method:** `PUT`
- **Body:**
  ```json
  {
    "status": "RUNNING",  // Or COMPLETED, FAILED
    "output_string": "Optional output string."
  }
  ```
- **Response:**
  ```json
  {
    "id": "unique-uuid",
    "input_string": "The text to be sent to the LLM.",
    "output_string": "Optional output string.",
    "status": "RUNNING"
  }
  ```

### 4. List all interactions (Debug)
Returns all interactions currently in the queue.

- **URL:** `/api/interactions`
- **Method:** `GET`
- **Response:**
  ```json
  [
    {
      "id": "unique-uuid",
      "input_string": "...",
      "output_string": null,
      "status": "PENDING"
    }
  ]
  ```
