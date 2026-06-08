# Communication Manager API

Server runs on `localhost:9223`.

## Endpoints

### 1. Add new interaction
Adds a new interaction to the end of the queue.

- **URL:** `/api/interaction`
- **Method:** `POST`
- **Body:**
  ```json
  {
    "input_string": "The text to be sent to the LLM.",
    "client": "qwen" (optional, defaults to deepseek)
  }
  ```
- **Response:**
  ```json
  {
    "id": "unique-uuid",
    "status": "PENDING",
    "client": "qwen"
  }
  ```

### 2. Peek next interaction
Returns the interaction at the head of the queue. The interaction remains in the queue until it is updated to `CONSUMED`.

- **URL:** `/api/interaction/next`
- **Method:** `GET`
- **Response:** Interaction object or `null`.

### 3. Update interaction
Change response and status of the interaction at the head of the queue.

Note: The interaction is **only removed from the queue** when its status is updated to `CONSUMED`. Marking it as `COMPLETED` or `FAILED` keeps it at the head of the queue so the caller can retrieve the result via the Peek API.

- **URL:** `/api/interaction/next`
- **Method:** `PUT`
- **Body:**
  ```json
  {
    "status": "RUNNING",  // Or COMPLETED, FAILED, CONSUMED
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
- **Response:** Array of interaction objects.

### 5. List all interactions (Debug)
Returns all interactions currently in the queue.

- **URL:** `/api/interactions`
- **Method:** `GET`
- **Response:** Array of interaction objects.

### 6. Clear all interactions
Clears all interactions from the queue.

- **URL:** `/api/interactions`
- **Method:** `DELETE`
- **Response:** `{"status": "cleared"}`
